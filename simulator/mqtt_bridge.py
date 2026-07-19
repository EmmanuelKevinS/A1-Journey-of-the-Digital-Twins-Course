from datetime import datetime, timezone
import json
import time

import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from twin_model import (
    derive_twin_state,
    env_int,
    env_str,
    load_asset_model,
    temperature_threshold,
)


def point_time(timestamp: float) -> datetime:
    return datetime.fromtimestamp(float(timestamp), timezone.utc)


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT broker")
        client.subscribe(userdata["subscribe_topic"], qos=userdata["qos"])
        print(f"Subscribed to {userdata['subscribe_topic']}")
    else:
        print(f"Connection failed with code {rc}")


def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
        sensor_type = data["sensor_type"]
        value = float(data["value"])
        timestamp = float(data.get("timestamp", time.time()))

        point = (
            Point("lab_sensor_readings")
            .tag("room_id", data["room_id"])
            .tag("run_id", data.get("run_id", "manual"))
            .tag("sensor_id", data["sensor_id"])
            .tag("sensor_type", sensor_type)
            .tag("zone", data["zone"])
            .tag("quality", data.get("quality", "UNKNOWN"))
            .field("value", value)
            .field("unit", data["unit"])
            .time(point_time(timestamp), WritePrecision.NS)
        )
        userdata["write_api"].write(bucket=userdata["bucket"], org=userdata["org"], record=point)

        userdata["latest_readings"][sensor_type] = data
        if {"temperature", "humidity", "occupancy"}.issubset(userdata["latest_readings"]):
            state = derive_twin_state(userdata["asset_model"], userdata["latest_readings"], timestamp=timestamp)
            state_point = (
                Point("lab_twin_state")
                .tag("room_id", state["room_id"])
                .tag("run_id", data.get("run_id", "manual"))
                .tag("room_name", state["room_name"])
                .tag("comfort_status", state["comfort_status"])
                .tag("occupancy_level", state["occupancy_level"])
                .field("temperature", state["temperature"])
                .field("humidity", state["humidity"])
                .field("occupancy", float(state["occupancy"]))
                .field("alert_active", state["alert_active"])
                .field("alert_active_numeric", state["alert_active_numeric"])
                .field("alert_message", state["alert_message"])
                .field("temperature_threshold", state["temperature_threshold"])
                .time(point_time(state["timestamp"]), WritePrecision.NS)
            )
            userdata["write_api"].write(bucket=userdata["bucket"], org=userdata["org"], record=state_point)

            if state["alert_active"] and not userdata["alert_active"]:
                alert_point = (
                    Point("lab_alert_events")
                    .tag("room_id", state["room_id"])
                    .tag("run_id", data.get("run_id", "manual"))
                    .tag("event_type", "temperature_threshold")
                    .tag("severity", "critical")
                    .tag("sensor_id", userdata["latest_readings"]["temperature"]["sensor_id"])
                    .tag("zone", userdata["latest_readings"]["temperature"]["zone"])
                    .field("value", state["temperature"])
                    .field("threshold", temperature_threshold(userdata["asset_model"]))
                    .field("message", state["alert_message"])
                    .field("active", 1)
                    .time(point_time(state["timestamp"]), WritePrecision.NS)
                )
                userdata["write_api"].write(bucket=userdata["bucket"], org=userdata["org"], record=alert_point)
                print(f"ALERT EVENT: {state['alert_message']}")

            userdata["alert_active"] = state["alert_active"]
            print(
                "Twin state: "
                f"{state['temperature']:.1f} degC, {state['humidity']:.1f}%, "
                f"{state['occupancy']} people, {state['comfort_status']}"
            )
        else:
            print(f"Stored raw reading: {sensor_type} = {value:g} {data['unit']}")

    except Exception as e:
        print(f"Error processing message: {e}")


def main():
    asset_model = load_asset_model()
    influx_client = InfluxDBClient(
        url=env_str("INFLUX_URL", "http://localhost:8086"),
        token=env_str("INFLUXDB_TOKEN", "sutd-dt-token-2026"),
        org=env_str("INFLUXDB_ORG", "sutd-dt"),
    )
    userdata = {
        "asset_model": asset_model,
        "write_api": influx_client.write_api(write_options=SYNCHRONOUS),
        "org": env_str("INFLUXDB_ORG", "sutd-dt"),
        "bucket": env_str("INFLUXDB_BUCKET", "sensors"),
        "subscribe_topic": f"{env_str('MQTT_TOPIC_PREFIX', 'lab/sensors')}/#",
        "qos": env_int("MQTT_QOS", 1),
        "latest_readings": {},
        "alert_active": False,
    }

    client = mqtt.Client(client_id=env_str("MQTT_BRIDGE_CLIENT_ID", "mqtt-influx-bridge"), userdata=userdata)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(
        env_str("MQTT_BROKER_HOST", "localhost"),
        env_int("MQTT_BROKER_PORT", 1883),
        keepalive=60,
    )

    print("Bridge running; press Ctrl+C to stop")
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("\nBridge stopped.")
    finally:
        client.disconnect()
        influx_client.close()


if __name__ == "__main__":
    main()
