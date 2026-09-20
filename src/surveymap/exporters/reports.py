from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import asdict, is_dataclass
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from surveymap.models import Link, Node, SurveyGraph

FIELD_ORDER = [
    ("id", "ID"),
    ("label", "Label"),
    ("kind", "Kind"),
    ("medium", "Medium"),
    ("roles", "Roles (server/client)"),
    ("vendor", "OUI manufacturer"),
    ("macs", "MAC addresses"),
    ("ips", "IP addresses"),
    ("vlans", "VLANs"),
    ("ssids", "SSIDs"),
    ("channels", "Wireless channels"),
    ("frequencies_mhz", "RF frequency (MHz)"),
    ("encryption", "Encryption"),
    ("signal_dbm", "Signal (dBm)"),
    ("signal_min_dbm", "Signal min (dBm)"),
    ("signal_max_dbm", "Signal max (dBm)"),
    ("services", "Services"),
    ("ports", "Ports"),
    ("gps", "GPS"),
    ("routing", "Routing"),
    ("extra", "Other extracted data"),
]


def _stringify(value: Any) -> str:
    if value is None or value == "" or value == [] or value == {}:
        return ""
    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, list):
        if value and isinstance(value[0], dict):
            parts = []
            for item in value:
                if item.get("display"):
                    extra = []
                    if item.get("role"):
                        extra.append(str(item["role"]))
                    if item.get("sport") is not None and item.get("dport") is not None:
                        extra.append(f"src {item['sport']} → dst {item['dport']}")
                    text = str(item["display"])
                    if extra:
                        text += f" ({', '.join(extra)})"
                    parts.append(text)
                else:
                    parts.append(json.dumps(item, ensure_ascii=False))
            return "; ".join(parts)
        return ", ".join(str(v) for v in value)
    if isinstance(value, dict):
        if {"lat", "lon"} <= set(value.keys()):
            lat, lon = value["lat"], value["lon"]
            alt = value.get("alt")
            text = f"{lat}, {lon}"
            if alt is not None:
                text += f", alt {alt}"
            return text
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value)


def related_links(graph: SurveyGraph, node_id: str) -> list[Link]:
    return [link for link in graph.links if link.source == node_id or link.target == node_id]


def device_properties(graph: SurveyGraph, node: Node) -> list[dict[str, str]]:
    """Every extracted field for a device, including empty ones, plus related links."""
    if is_dataclass(node) and not isinstance(node, type):
        raw = asdict(node)
    elif hasattr(node, "__dict__"):
        raw = dict(node.__dict__)
    else:
        raw = dict(node)
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for key, title in FIELD_ORDER:
        seen.add(key)
        value = raw.get(key)
        if key in {"routing", "extra"} and isinstance(value, dict) and value:
            rows.append({"name": title, "key": key, "value": _stringify(value)})
            for nested_key, nested_val in value.items():
                rows.append(
                    {
                        "name": f"{title} · {nested_key}",
                        "key": f"{key}.{nested_key}",
                        "value": _stringify(nested_val),
                    }
                )
            continue
        rows.append({"name": title, "key": key, "value": _stringify(value)})
    for key, value in raw.items():
        if key in seen:
            continue
        rows.append({"name": key.replace("_", " ").title(), "key": key, "value": _stringify(value)})
    for i, link in enumerate(related_links(graph, node.id), start=1):
        bits = [
            link.kind,
            link.label,
            f"{link.source} → {link.target}",
            _stringify(link.services),
            _stringify(link.ports),
        ]
        rows.append(
            {
                "name": f"Link {i}",
                "key": f"link.{i}",
                "value": " | ".join(b for b in bits if b),
            }
        )
    return rows


def device_plain_text(graph: SurveyGraph, node: Node) -> str:
    lines = [f"SurveyMap device: {node.label}", ""]
    for row in device_properties(graph, node):
        value = row["value"] or "—"
        lines.append(f"{row['name']}: {value}")
    return "\n".join(lines) + "\n"


def device_csv(graph: SurveyGraph, node: Node) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Field", "Value"])
    for row in device_properties(graph, node):
        writer.writerow([row["name"], row["value"]])
    return buf.getvalue()


def device_xml(graph: SurveyGraph, node: Node) -> str:
    props = "\n".join(
        f'    <property key="{escape(row["key"])}" name="{escape(row["name"])}">'
        f"{escape(row['value'])}</property>"
        for row in device_properties(graph, node)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<device id="{escape(node.id)}" label="{escape(node.label)}">\n'
        f"{props}\n"
        "</device>\n"
    )


def _styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "SurveyTitle",
            parent=base["Heading1"],
            fontSize=16,
            textColor=colors.HexColor("#0b1220"),
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "SurveyH2",
            parent=base["Heading2"],
            fontSize=12,
            textColor=colors.HexColor("#153246"),
            spaceBefore=10,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "SurveyBody",
            parent=base["BodyText"],
            fontSize=9,
            leading=12,
        ),
        "cell": ParagraphStyle(
            "SurveyCell",
            parent=base["BodyText"],
            fontSize=8,
            leading=10,
        ),
        "muted": ParagraphStyle(
            "SurveyMuted",
            parent=base["BodyText"],
            fontSize=8,
            textColor=colors.HexColor("#64748b"),
        ),
    }


def _property_table(rows: list[dict[str, str]], styles: dict) -> Table:
    data = [[Paragraph("<b>Field</b>", styles["cell"]), Paragraph("<b>Value</b>", styles["cell"])]]
    for row in rows:
        data.append(
            [
                Paragraph(escape(row["name"]), styles["cell"]),
                Paragraph(escape(row["value"] or "—").replace("\n", "<br/>"), styles["cell"]),
            ]
        )
    table = Table(data, colWidths=[1.7 * inch, 5.3 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#153246")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#eef6f8")),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#94a3b8")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def device_pdf(graph: SurveyGraph, node: Node, title: str | None = None) -> bytes:
    buf = io.BytesIO()
    styles = _styles()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        title=title or f"Device {node.label}",
        author="SurveyMap",
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
    )
    story = [
        Paragraph(escape(title or "SurveyMap device details"), styles["title"]),
        Paragraph(escape(node.label), styles["h2"]),
        _property_table(device_properties(graph, node), styles),
    ]
    doc.build(story)
    return buf.getvalue()


def map_report_pdf(graph: SurveyGraph, title: str = "Survey map report") -> bytes:
    buf = io.BytesIO()
    styles = _styles()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        title=title,
        author="SurveyMap",
        leftMargin=0.55 * inch,
        rightMargin=0.55 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
    )
    meta = graph.meta or {}
    story: list = [
        Paragraph(escape(title), styles["title"]),
        Paragraph(
            escape(
                f"Devices: {len(graph.nodes)} · Links: {len(graph.links)} · "
                f"Packets: {meta.get('packet_count', '—')} · "
                f"Sources: {', '.join(meta.get('sources') or []) or '—'}"
            ),
            styles["body"],
        ),
        Spacer(1, 8),
        Paragraph("Inventory", styles["h2"]),
    ]
    inventory = [[
        Paragraph("<b>Device</b>", styles["cell"]),
        Paragraph("<b>Kind</b>", styles["cell"]),
        Paragraph("<b>OUI manufacturer</b>", styles["cell"]),
        Paragraph("<b>IPs</b>", styles["cell"]),
        Paragraph("<b>Services</b>", styles["cell"]),
    ]]
    for node in graph.nodes:
        inventory.append(
            [
                Paragraph(escape(node.label), styles["cell"]),
                Paragraph(escape(f"{node.kind} / {node.medium}"), styles["cell"]),
                Paragraph(escape(node.vendor or "—"), styles["cell"]),
                Paragraph(escape(_stringify(node.ips) or "—"), styles["cell"]),
                Paragraph(escape(_stringify(node.services) or "—"), styles["cell"]),
            ]
        )
    inv = Table(inventory, colWidths=[1.6 * inch, 1.15 * inch, 1.7 * inch, 1.35 * inch, 1.2 * inch])
    inv.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#153246")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#94a3b8")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(inv)
    story.append(PageBreak())
    for i, node in enumerate(graph.nodes):
        story.append(Paragraph(escape(node.label), styles["h2"]))
        story.append(_property_table(device_properties(graph, node), styles))
        if i != len(graph.nodes) - 1:
            story.append(Spacer(1, 10))
    if graph.links:
        story.append(PageBreak())
        story.append(Paragraph("Links", styles["h2"]))
        link_rows = [[
            Paragraph("<b>Kind</b>", styles["cell"]),
            Paragraph("<b>From</b>", styles["cell"]),
            Paragraph("<b>To</b>", styles["cell"]),
            Paragraph("<b>Services / ports</b>", styles["cell"]),
        ]]
        for link in graph.links:
            ports = _stringify(link.ports) or _stringify(link.services) or link.label
            link_rows.append(
                [
                    Paragraph(escape(link.kind), styles["cell"]),
                    Paragraph(escape(link.source), styles["cell"]),
                    Paragraph(escape(link.target), styles["cell"]),
                    Paragraph(escape(ports or "—"), styles["cell"]),
                ]
            )
        links_table = Table(link_rows, colWidths=[1.2 * inch, 2.1 * inch, 2.1 * inch, 1.6 * inch])
        links_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#153246")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#94a3b8")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(links_table)
    doc.build(story)
    return buf.getvalue()


def safe_filename(name: str, suffix: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or "surveymap"
    return f"{stem[:80]}{suffix}"
