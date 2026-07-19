from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
SIMULATOR_DIR = REPO_ROOT / "simulator"


@dataclass
class Check:
    name: str
    passed: bool
    detail: str
    next_action: str = ""


def load_local_env() -> dict[str, str]:
    env = os.environ.copy()
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return env
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        env.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    return env


def command_text(args: list[str]) -> str:
    return " ".join(args)


def run_command(args: list[str], timeout: int = 20) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            args,
            cwd=REPO_ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
        return completed.returncode == 0, (completed.stdout or "").strip()
    except FileNotFoundError:
        return False, f"Command not found: {args[0]}"
    except subprocess.TimeoutExpired:
        return False, f"Timed out: {command_text(args)}"


def check_tcp(name: str, host: str, port: int) -> Check:
    try:
        with socket.create_connection((host, port), timeout=3):
            return Check(name, True, f"{host}:{port} reachable")
    except OSError as exc:
        return Check(
            name,
            False,
            f"{host}:{port} not reachable ({exc})",
            "Start Docker Desktop, then run `docker compose up -d` from the repo root.",
        )


def check_http_json(name: str, url: str, expected: str) -> Check:
    last_error = ""
    for _ in range(5):
        try:
            with urlopen(url, timeout=5) as response:
                payload = response.read().decode("utf-8")
            return Check(name, expected in payload, payload[:200], f"Check {url} and container logs.")
        except (OSError, URLError) as exc:
            last_error = str(exc)
            time.sleep(2)
    return Check(name, False, last_error, "Confirm the service container is running and listening.")


def check_python_imports() -> Check:
    required = ["paho.mqtt.client", "influxdb_client"]
    for module in required:
        ok, output = run_command([sys.executable, "-c", f"import {module}"], timeout=10)
        if not ok:
            return Check(
                "Python dependencies",
                False,
                output,
                "Run `python -m pip install -r requirements.txt`.",
            )
    return Check("Python dependencies", True, "paho-mqtt and influxdb-client import correctly")


def check_provisioning_files() -> list[Check]:
    datasource = REPO_ROOT / "config" / "grafana" / "provisioning" / "datasources" / "influxdb.yaml"
    dashboard = REPO_ROOT / "config" / "grafana" / "provisioning" / "dashboards" / "dashboard-A1_DT.json"
    checks: list[Check] = []

    datasource_text = datasource.read_text(encoding="utf-8")
    checks.append(
        Check(
            "Grafana datasource UID",
            "uid: influxdb_sensors" in datasource_text,
            "Datasource UID is stable" if "uid: influxdb_sensors" in datasource_text else "Missing stable UID",
            "Add `uid: influxdb_sensors` to the InfluxDB datasource provisioning file.",
        )
    )

    try:
        dashboard_json = json.loads(dashboard.read_text(encoding="utf-8"))
        dashboard_text = json.dumps(dashboard_json)
        ok = dashboard_json.get("uid") == "sutd-lab-connected-dt" and "influxdb_sensors" in dashboard_text
        checks.append(
            Check(
                "Grafana dashboard model",
                ok,
                "Dashboard JSON uses stable datasource UID" if ok else "Dashboard UID/datasource reference is unstable",
                "Replace generated datasource IDs with `influxdb_sensors`.",
            )
        )
    except json.JSONDecodeError as exc:
        checks.append(Check("Grafana dashboard model", False, str(exc), "Fix dashboard JSON syntax."))

    return checks


def run_short_demo(env: dict[str, str]) -> tuple[Check, str]:
    run_id = f"validate-{int(time.time())}"
    demo_env = env.copy()
    demo_env.update(
        {
            "PYTHONUNBUFFERED": "1",
            "SIM_RUN_ID": run_id,
            "SIM_RUN_SECONDS": "8",
            "SIM_PUBLISH_INTERVAL": "1",
            "SIM_FORCE_ALERT": "1",
            "SIM_RANDOM_SEED": "42",
        }
    )

    bridge = subprocess.Popen(
        [sys.executable, str(SIMULATOR_DIR / "mqtt_bridge.py")],
        cwd=REPO_ROOT,
        env=demo_env,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        time.sleep(3)
        simulator = subprocess.run(
            [sys.executable, str(SIMULATOR_DIR / "sensor_simulator.py")],
            cwd=REPO_ROOT,
            env=demo_env,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=20,
        )
        time.sleep(2)
        bridge.terminate()
        bridge_output = bridge.communicate(timeout=8)[0] or ""
    except Exception as exc:
        bridge.kill()
        bridge_output = bridge.communicate(timeout=5)[0] or ""
        return (
            Check(
                "Short live demo run",
                False,
                f"{exc}\nBridge output:\n{bridge_output[-1000:]}",
                "Confirm Docker services are up, then rerun validation.",
            ),
            run_id,
        )

    output = f"Simulator:\n{simulator.stdout[-1200:]}\nBridge:\n{bridge_output[-1200:]}"
    ok = simulator.returncode == 0 and "ALERT EVENT" in bridge_output
    return (
        Check(
            "Short live demo run",
            ok,
            f"Run ID {run_id}; alert event observed" if ok else output,
                "Check MQTT/Influx connectivity and bridge logs.",
        ),
        run_id,
    )


def query_count(env: dict[str, str], measurement: str, field: str, run_id: str, extra_filter: str = "") -> int:
    from influxdb_client import InfluxDBClient

    bucket = env.get("INFLUXDB_BUCKET", "sensors")
    org = env.get("INFLUXDB_ORG", "sutd-dt")
    token = env.get("INFLUXDB_TOKEN", "sutd-dt-token-2026")
    url = env.get("INFLUX_URL", "http://localhost:8086")
    query = f'''
from(bucket: "{bucket}")
  |> range(start: -10m)
  |> filter(fn: (r) => r._measurement == "{measurement}")
  |> filter(fn: (r) => r._field == "{field}")
  |> filter(fn: (r) => r.run_id == "{run_id}")
{extra_filter}
  |> count()
'''
    with InfluxDBClient(url=url, token=token, org=org) as client:
        tables = client.query_api().query(query=query, org=org)
    total = 0
    for table in tables:
        for record in table.records:
            total += int(record.get_value() or 0)
    return total


def check_influx_records(env: dict[str, str], run_id: str) -> list[Check]:
    checks: list[Check] = []
    targets = [
        ("Raw temperature records", "lab_sensor_readings", "value", '|> filter(fn: (r) => r.sensor_type == "temperature")'),
        ("Raw humidity records", "lab_sensor_readings", "value", '|> filter(fn: (r) => r.sensor_type == "humidity")'),
        ("Raw occupancy records", "lab_sensor_readings", "value", '|> filter(fn: (r) => r.sensor_type == "occupancy")'),
        ("Twin-state records", "lab_twin_state", "temperature", ""),
        ("Alert event records", "lab_alert_events", "active", ""),
    ]
    for name, measurement, field, extra_filter in targets:
        try:
            count = query_count(env, measurement, field, run_id, extra_filter)
            checks.append(
                Check(
                    name,
                    count > 0,
                    f"{count} records for run_id={run_id}",
                    "Rerun validation and inspect bridge output for write errors.",
                )
            )
        except Exception as exc:
            checks.append(
                Check(
                    name,
                    False,
                    str(exc),
                    "Confirm InfluxDB token/org/bucket settings match docker-compose.yml.",
                )
            )
    return checks


def print_report(checks: list[Check]) -> int:
    print("\nConnected Digital Twin validation report")
    print("=" * 47)
    failures = 0
    for check in checks:
        status = "PASS" if check.passed else "FAIL"
        print(f"[{status}] {check.name}: {check.detail}")
        if not check.passed:
            failures += 1
            if check.next_action:
                print(f"       Next: {check.next_action}")
    print("=" * 47)
    if failures:
        print(f"{failures} check(s) failed.")
        return 1
    print("All checks passed. The demo is ready to record.")
    return 0


def main() -> int:
    env = load_local_env()
    checks: list[Check] = []
    docker_ok, docker_output = run_command(["docker", "compose", "ps"], timeout=15)
    checks.append(
        Check(
            "Docker Compose status",
            docker_ok,
            docker_output if docker_output else "Docker Compose responded",
            "Start Docker Desktop, then run `docker compose up -d`.",
        )
    )

    checks.extend(
        [
            check_tcp("Mosquitto TCP", "localhost", int(env.get("MQTT_BROKER_PORT", "1883"))),
            check_tcp("InfluxDB TCP", "localhost", 8086),
            check_tcp("Grafana TCP", "localhost", 3000),
            check_tcp("3D model TCP", "localhost", 8050),
            check_http_json("InfluxDB health", "http://localhost:8086/health", "pass"),
            check_http_json("Grafana health", "http://localhost:3000/api/health", "ok"),
            check_http_json("3D model page", "http://localhost:8050/", "SUTD Lab Room 3D Twin"),
            check_python_imports(),
        ]
    )
    checks.extend(check_provisioning_files())

    service_ready = all(check.passed for check in checks if check.name in {
        "Mosquitto TCP",
        "InfluxDB TCP",
        "Grafana TCP",
        "InfluxDB health",
        "Grafana health",
        "3D model TCP",
        "3D model page",
        "Python dependencies",
    })
    if service_ready:
        demo_check, run_id = run_short_demo(env)
        checks.append(demo_check)
        if demo_check.passed:
            checks.extend(check_influx_records(env, run_id))
    else:
        checks.append(
            Check(
                "Short live demo run",
                False,
                "Skipped because services or dependencies are not ready",
                "Fix failed readiness checks above, then rerun validation.",
            )
        )

    return print_report(checks)


if __name__ == "__main__":
    raise SystemExit(main())
