import json
import math
import random
import time

import paho.mqtt.client as mqtt

from twin_model import (
    build_sensor_payload,
    env_bool,
    env_float,
    env_int,
    env_str,
    load_asset_model,
    sensors_by_type,
    temperature_threshold,
    topic_for_sensor,
)


def generate_temperature(t: int, asset_model: dict, force_alert: bool, spike_probability: float) -> float:
    """Realistic lab temperature with optional forced heat event for demos."""
    base = 24 + 3 * math.sin(t / 60)
    noise = random.gauss(0, 0.5)
    if force_alert and t == 0:
        return round(temperature_threshold(asset_model) + 3.5, 2)
    spike = 8 if random.random() < spike_probability else 0
    return round(base + noise + spike, 2)


def generate_humidity(t: int) -> float:
    """Lab humidity: 50-70% with slow oscillation."""
    base = 60 + 10 * math.sin(t / 120 + 1)
    noise = random.gauss(0, 1.5)
    return round(max(30, min(90, base + noise)), 2)


def generate_occupancy(t: int, capacity: int) -> int:
    """People count varies with simulated lab activity."""
    base = capacity / 2 + (capacity / 2) * math.sin(t / 90)
    return max(0, min(capacity, int(base + random.randint(-2, 2))))


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT broker")
    else:
        print(f"Connection failed with code {rc}")


def main():
    asset_model = load_asset_model()
    sensor_map = sensors_by_type(asset_model)
    broker_host = env_str("MQTT_BROKER_HOST", "localhost")
    broker_port = env_int("MQTT_BROKER_PORT", 1883)
    publish_interval = env_float("SIM_PUBLISH_INTERVAL", 5.0)
    run_seconds = env_float("SIM_RUN_SECONDS", 0.0)
    qos = env_int("MQTT_QOS", 1)
    spike_probability = env_float("SIM_HEAT_SPIKE_PROBABILITY", 0.12)
    force_alert = env_bool("SIM_FORCE_ALERT", False)
    seed = env_str("SIM_RANDOM_SEED", "")
    if seed:
        random.seed(seed)

    client = mqtt.Client(client_id=env_str("MQTT_SIMULATOR_CLIENT_ID", "sensor-simulator"))
    client.on_connect = on_connect
    client.connect(broker_host, broker_port, keepalive=60)
    client.loop_start()

    print(f"Publishing enriched sensor data every {publish_interval:g}s; press Ctrl+C to stop\n")
    t = 0
    sequence = 1
    started_at = time.time()

    try:
        while True:
            timestamp = time.time()
            capacity = int(asset_model["room"]["capacity_people"])
            readings = {
                "temperature": generate_temperature(t, asset_model, force_alert, spike_probability),
                "humidity": generate_humidity(t),
                "occupancy": generate_occupancy(t, capacity),
            }

            for sensor_type, sensor in sensor_map.items():
                payload = build_sensor_payload(
                    asset_model,
                    sensor_type,
                    readings[sensor_type],
                    sequence,
                    timestamp=timestamp,
                )
                client.publish(topic_for_sensor(sensor), json.dumps(payload), qos=qos)

            temp = readings["temperature"]
            alert = " ALERT: temp exceeds threshold" if temp > temperature_threshold(asset_model) else ""
            print(
                f"[t={t:04d}s] Temp: {readings['temperature']} degC | "
                f"Humidity: {readings['humidity']}% | "
                f"Occupancy: {readings['occupancy']} people{alert}"
            )

            sequence += 1
            t += int(publish_interval)
            if run_seconds and (time.time() - started_at) >= run_seconds:
                break
            time.sleep(publish_interval)

    except KeyboardInterrupt:
        print("\nSimulator stopped.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
