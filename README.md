# Project 1: The Connected Digital Twin (Foundational)
**Course:** Journey of the Digital Twins | SUTD  
**Student:** Emmanuel Kevin  
**Due Date:** 19 July 2026

---

## Overview
A Connected Digital Twin of a virtual SUTD lab room, built using simulated sensor data streams flowing through a full 6-layer Digital Twin architecture into a live Grafana dashboard.

## Stack
- **Python** - Sensor simulator and MQTT bridge
- **MQTT / Eclipse Mosquitto** - Messaging protocol and broker
- **InfluxDB v2** - Time-series data storage
- **Grafana** - Live dashboard and threshold alerting
- **Docker** - Container orchestration

## How to Run

**Start the services:**
```bash
docker compose up -d
```

**Install Python dependencies:**
```bash
pip install -r requirements.txt
```

**Start the MQTT bridge (Terminal 1):**
```bash
python simulator/mqtt_bridge.py
```

**Start the sensor simulator (Terminal 2):**
```bash
python simulator/sensor_simulator.py
```

**Open the dashboard:**  
Go to http://localhost:3000 (login: admin / admin)

## Deliverables
- `Architecture_Diagram.png` - 6-layer Digital Twin architecture diagram
- `A1_Technical_Summary.pdf` - Messaging protocol justification and system description
- Live Grafana dashboard with real-time sensor readings and 30 degrees C threshold alert
