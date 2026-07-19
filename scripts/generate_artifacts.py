from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image as ReportImage,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
ASSET_MODEL_PATH = REPO_ROOT / "config" / "lab_asset_model.json"
DIAGRAM_PATH = REPO_ROOT / "Architecture_Diagram.png"
SUMMARY_PATH = REPO_ROOT / "Assignment1_Technical_Summary.pdf"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def rounded_box(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: str, outline: str = "#20242b") -> None:
    draw.rounded_rectangle(box, radius=16, fill=fill, outline=outline, width=2)


def centered_text(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    text_font: ImageFont.ImageFont,
    fill: str = "#101418",
) -> None:
    lines = text.split("\n")
    heights = []
    widths = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=text_font)
        widths.append(bbox[2] - bbox[0])
        heights.append(bbox[3] - bbox[1])
    total_height = sum(heights) + (len(lines) - 1) * 8
    y = box[1] + ((box[3] - box[1] - total_height) / 2)
    for line, width, height in zip(lines, widths, heights):
        x = box[0] + ((box[2] - box[0] - width) / 2)
        draw.text((x, y), line, fill=fill, font=text_font)
        y += height + 8


def draw_arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], label: str = "") -> None:
    draw.line((start, end), fill="#475569", width=4)
    x1, y1 = start
    x2, y2 = end
    if y2 < y1:
        points = [(x2, y2), (x2 - 8, y2 + 18), (x2 + 8, y2 + 18)]
    else:
        points = [(x2, y2), (x2 - 8, y2 - 18), (x2 + 8, y2 - 18)]
    draw.polygon(points, fill="#475569")
    if label:
        label_font = font(18, bold=True)
        bbox = draw.textbbox((0, 0), label, font=label_font)
        x = (x1 + x2) / 2 - (bbox[2] - bbox[0]) / 2
        y = (y1 + y2) / 2 - 22
        draw.rounded_rectangle((x - 10, y - 5, x + bbox[2] - bbox[0] + 10, y + 25), radius=8, fill="#ffffff")
        draw.text((x, y), label, font=label_font, fill="#334155")


def generate_architecture_diagram() -> None:
    asset = json.loads(ASSET_MODEL_PATH.read_text(encoding="utf-8"))
    image = Image.new("RGB", (1900, 1200), "#f8fafc")
    draw = ImageDraw.Draw(image)

    title_font = font(52, bold=True)
    subtitle_font = font(24)
    heading_font = font(26, bold=True)
    body_font = font(21)
    small_font = font(18, bold=True)

    draw.rectangle((0, 0, 1900, 110), fill="#0f172a")
    draw.text((70, 28), "Connected Digital Twin - SUTD Lab Room", font=title_font, fill="#ffffff")
    draw.text((70, 82), "Digital thread: sensors -> MQTT -> InfluxDB -> twin state -> Grafana + alert event", font=subtitle_font, fill="#cbd5e1")

    lab_box = (70, 160, 700, 560)
    rounded_box(draw, lab_box, "#e0f2fe", "#0284c7")
    draw.text((95, 185), "Asset Virtualization", font=heading_font, fill="#0c4a6e")
    draw.text((95, 225), asset["room"]["name"], font=body_font, fill="#0f172a")
    draw.text((95, 258), f"Capacity: {asset['room']['capacity_people']} people | Area: {asset['room']['area_sqm']} sqm", font=body_font, fill="#0f172a")

    room = (125, 310, 645, 520)
    draw.rounded_rectangle(room, radius=10, fill="#ffffff", outline="#0369a1", width=3)
    zone_boxes = [
        ((145, 330, 305, 490), "North\nWorkbench", "#fde68a"),
        ((330, 330, 470, 490), "Central\nArea", "#bbf7d0"),
        ((495, 330, 625, 490), "South\nWall", "#fecaca"),
    ]
    for box, label, color in zone_boxes:
        draw.rounded_rectangle(box, radius=8, fill=color, outline="#64748b", width=2)
        centered_text(draw, box, label, small_font)

    sensor_colors = {"temperature": "#ef4444", "humidity": "#2563eb", "occupancy": "#16a34a"}
    marker_labels = {"temperature": "T", "humidity": "H", "occupancy": "O"}
    for sensor in asset["sensors"]:
        x = room[0] + int(sensor["position"]["x"] * (room[2] - room[0]))
        y = room[1] + int(sensor["position"]["y"] * (room[3] - room[1]))
        if sensor["sensor_type"] == "occupancy":
            y += 36
        color = sensor_colors[sensor["sensor_type"]]
        draw.ellipse((x - 16, y - 16, x + 16, y + 16), fill=color, outline="#ffffff", width=3)
        centered_text(draw, (x - 16, y - 16, x + 16, y + 16), marker_labels[sensor["sensor_type"]], font(16, bold=True), "#ffffff")
    draw.text((130, 530), "T TEMP-NB-01  |  O OCC-CR-01  |  H HUM-SW-01", font=font(16, bold=True), fill="#0f172a")

    layers = [
        ("Layer 2 - Data Acquisition", "Python simulator emits enriched JSON every 5s", "#bfdbfe"),
        ("Layer 3 - Connectivity", "MQTT topics lab/sensors/# with QoS 1", "#bbf7d0"),
        ("Layer 4 - Computational", "Bridge writes raw readings, twin state, alert events", "#ddd6fe"),
        ("Layer 5 - Modelling and Simulation", "Current room state: comfort, occupancy level, alert status", "#fed7aa"),
        ("Layer 6 - Application", "Grafana dashboard: live readings, twin state, alert history", "#fecaca"),
    ]
    x1, x2 = 820, 1780
    y = 175
    previous_center = None
    for title, desc, color in layers:
        box = (x1, y, x2, y + 120)
        rounded_box(draw, box, color)
        centered_text(draw, (x1 + 20, y + 15, x2 - 20, y + 105), f"{title}\n{desc}", body_font)
        center = ((x1 + x2) // 2, y + 60)
        if previous_center:
            draw_arrow(draw, (previous_center[0], previous_center[1] + 60), (center[0], center[1] - 60))
        previous_center = center
        y += 175

    draw_arrow(draw, (700, 360), (820, 235), "Sensor JSON")
    draw.line((1780, 935, 1850, 935, 1850, 785, 1780, 785), fill="#475569", width=4)
    draw.polygon([(1780, 785), (1798, 775), (1798, 795)], fill="#475569")
    draw.rounded_rectangle((1772, 835, 1885, 875), radius=8, fill="#ffffff", outline="#cbd5e1")
    draw.text((1788, 845), "Alert loop", font=small_font, fill="#334155")

    legend_y = 610
    draw.text((85, legend_y), "Sensor payload fields:", font=heading_font, fill="#0f172a")
    payload = "reading_id, room_id, run_id, sensor_id, sensor_type, zone, value, unit, quality, timestamp"
    draw.text((85, legend_y + 40), "reading_id, room_id, run_id, sensor_id, sensor_type, zone,", font=body_font, fill="#334155")
    draw.text((85, legend_y + 72), "value, unit, quality, timestamp", font=body_font, fill="#334155")
    draw.text((85, legend_y + 122), "Submission evidence:", font=heading_font, fill="#0f172a")
    proof = [
        "Stable Grafana provisioning UID",
        "Explicit lab asset model and sensor placement",
        "Derived twin state stored as dedicated time-series data",
        "Temperature alert events persist for demo evidence",
        "Validation script proves services, data, alerts, and dashboard setup",
    ]
    for idx, item in enumerate(proof):
        draw.text((105, legend_y + 177 + idx * 34), f"- {item}", font=body_font, fill="#334155")

    image.save(DIAGRAM_PATH)


def para(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(text, style)


def generate_summary_pdf() -> None:
    styles = getSampleStyleSheet()
    styles["Title"].fontName = "Helvetica-Bold"
    styles["Title"].fontSize = 22
    styles["Title"].leading = 26
    styles["Heading2"].fontName = "Helvetica-Bold"
    styles["Heading2"].fontSize = 14
    styles["Heading2"].spaceBefore = 12
    styles["Heading2"].spaceAfter = 6
    body = styles["BodyText"]
    body.fontName = "Helvetica"
    body.fontSize = 10
    body.leading = 14

    doc = SimpleDocTemplate(
        str(SUMMARY_PATH),
        pagesize=A4,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.55 * inch,
    )
    story = [
        para("The Connected Digital Twin", styles["Title"]),
        para("Group Assignment 1 - Technical Summary", styles["Heading2"]),
        para(
            "This project implements a connected digital twin of a virtual SUTD lab room. "
            "The system establishes a live digital thread from simulated room sensors through "
            "MQTT, InfluxDB, a derived twin-state layer, and a Grafana dashboard with persistent "
            "temperature alert evidence.",
            body,
        ),
        Spacer(1, 8),
        para("Implementation Enhancements", styles["Heading2"]),
        ListFlowable(
            [
                ListItem(para("Asset virtualization is explicit: room metadata, zones, sensor IDs, positions, units, and thresholds are stored in config/lab_asset_model.json.", body)),
                ListItem(para("Sensor payloads are enriched with run ID, room ID, sensor ID, sensor type, zone, quality, unit, value, and timestamp.", body)),
                ListItem(para("The bridge writes three evidence streams: raw readings, derived lab_twin_state, and lab_alert_events.", body)),
                ListItem(para("Grafana provisioning now uses a stable InfluxDB datasource UID so the dashboard survives fresh setup.", body)),
                ListItem(para("scripts/validate_demo.py performs a forced-alert run and verifies services, dependencies, data, alerts, and dashboard config.", body)),
            ],
            bulletType="bullet",
            leftIndent=14,
        ),
        para("Architecture", styles["Heading2"]),
        para(
            "The 6-layer architecture maps as follows: physical layer is the virtual SUTD lab; "
            "data acquisition is the Python simulator; connectivity is MQTT through Mosquitto; "
            "the computational layer is the MQTT bridge and InfluxDB; modelling and simulation "
            "is the explicit twin-state derivation; the application layer is Grafana with live "
            "state and alert history.",
            body,
        ),
        Spacer(1, 8),
        ReportImage(str(DIAGRAM_PATH), width=7.0 * inch, height=4.65 * inch),
        PageBreak(),
        para("Messaging Protocol Choice", styles["Heading2"]),
        para(
            "MQTT is used because the publish-subscribe model cleanly decouples simulated sensors "
            "from downstream consumers. It is lightweight, suitable for frequent IoT sensor messages, "
            "supports Quality of Service, and naturally extends to real physical sensors or cloud IoT "
            "platforms. Compared with HTTP polling, MQTT reduces unnecessary request overhead and gives "
            "the digital twin a live event stream.",
            body,
        ),
        para("Payload Schema", styles["Heading2"]),
    ]

    schema_table = Table(
        [
            ["Field", "Purpose"],
            ["reading_id", "Unique reading identifier for traceability"],
            ["room_id / room_name", "Links reading to the virtualized asset"],
            ["run_id", "Separates validation/demo runs from older data"],
            ["sensor_id / sensor_type", "Identifies source sensor and measurement type"],
            ["zone", "Connects data to a lab room location"],
            ["value / unit / quality", "Carries measured value with interpretation metadata"],
            ["timestamp", "Preserves the digital thread timing from generation to dashboard"],
        ],
        colWidths=[1.8 * inch, 4.9 * inch],
    )
    schema_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#94a3b8")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ]
        )
    )
    story.extend([schema_table, Spacer(1, 8)])

    rubric = Table(
        [
            ["Assignment Criterion", "Implemented Evidence"],
            ["Asset Virtualization", "Lab asset model, zones, sensor IDs, sensor positions, thresholds"],
            ["Synthetic Data Ingestion", "Python simulator publishes enriched JSON to MQTT topics"],
            ["Architecture Mapping", "Updated 6-layer diagram with digital thread and alert loop"],
            ["Dashboard Development", "Grafana dashboard shows live streams, current twin state, and alert events"],
            ["Technical Summary", "Protocol rationale, schema, rubric mapping, and validation workflow"],
        ],
        colWidths=[2.0 * inch, 4.7 * inch],
    )
    rubric.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dcfce7")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#94a3b8")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ]
        )
    )
    story.extend(
        [
            para("Rubric Mapping", styles["Heading2"]),
            rubric,
            para("Validation Loop", styles["Heading2"]),
            para(
                "The project includes a repeatable validation command: python scripts/validate_demo.py. "
                "It checks Docker service status, TCP/HTTP health, Python imports, Grafana provisioning, "
                "then runs the simulator with SIM_FORCE_ALERT=1. The script queries InfluxDB using the "
                "fresh validation run ID and fails if any raw reading, twin-state record, or alert event "
                "is missing.",
                body,
            ),
            para("Conclusion", styles["Heading2"]),
            para(
                "The final prototype goes beyond a basic live chart by making the asset model, sensor "
                "metadata, derived room state, alert evidence, and validation loop explicit. This creates "
                "a demonstrable connected digital twin rather than only a sensor dashboard.",
                body,
            ),
        ]
    )

    doc.build(story)


def main() -> None:
    generate_architecture_diagram()
    generate_summary_pdf()
    print(f"Wrote {DIAGRAM_PATH}")
    print(f"Wrote {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
