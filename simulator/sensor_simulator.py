"""
Sensor Simulator — Physical + Data Acquisition Layers
Simulates a lab room with 3 sensors publishing to MQTT every 5 seconds.
"""

import json
import time
import random
import math
import paho.mqtt.client as mqtt

BROKER_HOST = "localhost"
BROKER_PORT = 1883
PUBLISH_INTERVAL = 5  # seconds

TOPICS = {
    "temperature": "lab/sensors/temperature",
    "humidity":    "lab/sensors/humidity",
    "occupancy":   "lab/sensors/occupancy",
}

def generate_temperature(t):
    """Realistic lab temperature: baseline ~24°C, slow drift, occasional spikes above 30°C."""
    base = 24 + 3 * math.sin(t / 60)
    noise = random.gauss(0, 0.5)
    spike = 8 if random.random() < 0.08 else 0  # 8% chance of a heat spike
    return round(base + noise + spike, 2)

def generate_humidity(t):
    """Lab humidity: 50-70% with slow oscillation."""
    base = 60 + 10 * math.sin(t / 120 + 1)
    noise = random.gauss(0, 1.5)
    return round(max(30, min(90, base + noise)), 2)

def generate_occupancy(t):
    """People count: 0-12, higher during working hours (simulated by sine wave)."""
    base = 6 + 6 * math.sin(t / 90)
    return max(0, min(12, int(base + random.randint(-2, 2))))

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT broker")
    else:
        print(f"Connection failed with code {rc}")

def main():
    client = mqtt.Client(client_id="sensor-simulator")
    client.on_connect = on_connect
    client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
    client.loop_start()

    print(f"Publishing sensor data every {PUBLISH_INTERVAL}s — press Ctrl+C to stop\n")
    t = 0

    try:
        while True:
            readings = {
                "temperature": generate_temperature(t),
                "humidity":    generate_humidity(t),
                "occupancy":   generate_occupancy(t),
                "timestamp":   time.time(),
            }

            for sensor, topic in TOPICS.items():
                payload = json.dumps({
                    "sensor": sensor,
                    "value":  readings[sensor],
                    "unit":   {"temperature": "°C", "humidity": "%", "occupancy": "people"}[sensor],
                    "timestamp": readings["timestamp"],
                })
                client.publish(topic, payload, qos=1)

            temp = readings["temperature"]
            alert = " ⚠ ALERT: temp > 30°C" if temp > 30 else ""
            print(
                f"[t={t:04d}s] Temp: {readings['temperature']}°C | "
                f"Humidity: {readings['humidity']}% | "
                f"Occupancy: {readings['occupancy']} people{alert}"
            )

            t += PUBLISH_INTERVAL
            time.sleep(PUBLISH_INTERVAL)

    except KeyboardInterrupt:
        print("\nSimulator stopped.")
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()
