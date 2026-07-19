# Project 1: The Connected Digital Twin

**Course:** Journey of the Digital Twins | SUTD

## Overview

This repository implements a connected digital twin of a virtual SUTD lab room. Simulated
temperature, humidity, and occupancy sensors publish enriched JSON readings to MQTT. A bridge
subscribes to those readings, stores raw data in InfluxDB, derives the current room twin state,
and records temperature alert events. Grafana displays the live digital thread from sensor data
to dashboard.

## Submission Highlights

- Explicit asset virtualization: `config/lab_asset_model.json` defines room metadata, zones,
  sensor IDs, sensor locations, units, and thresholds.
- Complete digital thread: MQTT payloads carry sensor, zone, quality, timestamp, and run ID
  metadata from simulator to InfluxDB.
- Real twin-state layer: the bridge writes `lab_twin_state` records with comfort status,
  occupancy level, and active alert status.
- Alert evidence: forced or natural heat events create `lab_alert_events` records and show up in
  the dashboard history panel.
- Embedded 3D model: the Grafana dashboard includes a self-contained 3D lab-room view showing
  room zones and sensor placement.
- Repeatable validation: `scripts/validate_demo.py` starts a short forced-alert run and verifies
  raw readings, twin state, alert events, service health, and Grafana provisioning.

## Stack

- **Python** - Sensor simulator, MQTT bridge, validation, and artifact generation
- **MQTT / Eclipse Mosquitto** - Publish-subscribe messaging layer
- **InfluxDB v2** - Time-series storage for raw readings, twin state, and alerts
- **Grafana 13.1.0** - Provisioned live dashboard
- **Nginx** - Local static service for the embedded 3D lab-room model
- **Docker Compose** - Local demo orchestration

## Quick Start

1. Copy the example environment file if you want to customize settings:

```powershell
Copy-Item .env.example .env
```

2. Start Docker Desktop, then start services:

```powershell
docker compose up -d
```

3. Install Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

4. Run the full validation loop:

```powershell
python scripts/validate_demo.py
```

5. Open Grafana:

[http://localhost:3000](http://localhost:3000)

Default login is `admin` / `admin`. Open the **SUTD Lab Connected Digital Twin** dashboard.
The embedded 3D model is served at [http://localhost:8050](http://localhost:8050) and appears
inside the top dashboard panel.

## Manual Demo Mode

Run the bridge in one terminal:

```powershell
python simulator/mqtt_bridge.py
```

Run the simulator in another terminal:

```powershell
python simulator/sensor_simulator.py
```

To force an immediate high-temperature alert for recording:

```powershell
$env:SIM_FORCE_ALERT="1"
python simulator/sensor_simulator.py
```

## Data Model

Raw readings are stored in `lab_sensor_readings` with tags for `room_id`, `run_id`, `sensor_id`,
`sensor_type`, `zone`, and `quality`.

Derived room state is stored in `lab_twin_state` with fields for temperature, humidity,
occupancy, comfort status, occupancy level, active alert state, and threshold.

Alert events are stored in `lab_alert_events` when the twin enters an overheated state above
30 degC.

## Deliverables

- `Architecture_Diagram.png` - Updated 6-layer architecture, room layout, digital thread, and
  alert loop diagram
- `Assignment1_Technical_Summary.pdf` - Refreshed summary with schema, rubric mapping, and
  validation evidence
- `config/grafana/provisioning/dashboards/dashboard-A1_DT.json` - Reproducible Grafana dashboard
- `scripts/validate_demo.py` - Repeatable submission validation loop
- `web/3d-lab/index.html` - Embedded 3D lab-room model used by the Grafana dashboard
