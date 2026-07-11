"""
MQTT → InfluxDB Bridge — Connectivity + Computational Layers
Subscribes to all sensor topics and writes readings into InfluxDB.
"""

import json
import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

BROKER_HOST  = "localhost"
BROKER_PORT  = 1883
SUBSCRIBE_TOPIC = "lab/sensors/#"

INFLUX_URL    = "http://localhost:8086"
INFLUX_TOKEN  = "sutd-dt-token-2026"
INFLUX_ORG    = "sutd-dt"
INFLUX_BUCKET = "sensors"

influx_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
write_api = influx_client.write_api(write_options=SYNCHRONOUS)

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT broker")
        client.subscribe(SUBSCRIBE_TOPIC)
        print(f"Subscribed to {SUBSCRIBE_TOPIC}")
    else:
        print(f"Connection failed with code {rc}")

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
        sensor = data["sensor"]
        value  = data["value"]

        point = (
            Point("lab_sensors")
            .tag("sensor", sensor)
            .tag("location", "sutd-lab-room-1")
            .field("value", float(value))
        )
        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
        print(f"Stored: {sensor} = {value}")

    except Exception as e:
        print(f"Error processing message: {e}")

def main():
    client = mqtt.Client(client_id="mqtt-influx-bridge")
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)

    print("Bridge running — press Ctrl+C to stop")
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("\nBridge stopped.")
        client.disconnect()
        influx_client.close()

if __name__ == "__main__":
    main()
