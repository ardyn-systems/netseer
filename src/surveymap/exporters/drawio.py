from __future__ import annotations

from xml.sax.saxutils import escape

from surveymap.exporters.layout import layout_positions
from surveymap.models import SurveyGraph
from surveymap.services import node_service_caption

KIND_STYLE = {
    "ap": "rounded=0;whiteSpace=wrap;html=1;shape=hexagon;fillColor=#422006;strokeColor=#FBBF24;fontColor=#FEF3C7;fontStyle=1;",
    "gateway": "rounded=1;whiteSpace=wrap;html=1;fillColor=#2E1065;strokeColor=#C4B5FD;fontColor=#F5F3FF;fontStyle=1;",
    "server": "rounded=1;whiteSpace=wrap;html=1;fillColor=#082F49;strokeColor=#38BDF8;fontColor=#E0F2FE;fontStyle=1;",
    "host": "rounded=1;whiteSpace=wrap;html=1;fillColor=#042F2E;strokeColor=#5EEAD4;fontColor=#CCFBF1;",
    "subnet": "rounded=1;whiteSpace=wrap;html=1;dashed=1;fillColor=#111827;strokeColor=#9CA3AF;fontColor=#E5E7EB;",
    "vlan": "rounded=1;whiteSpace=wrap;html=1;dashed=1;fillColor=#1E1B4B;strokeColor=#A78BFA;fontColor=#EDE9FE;",
}

EDGE_STYLE = {
    "l2": "endArrow=none;strokeColor=#5EEAD4;strokeWidth=2;",
    "l3": "endArrow=none;strokeColor=#86EFAC;strokeWidth=2;dashed=1;",
    "wireless": "endArrow=none;strokeColor=#FBBF24;strokeWidth=2;dashed=1;dashPattern=8 8;",
    "vlan": "endArrow=none;strokeColor=#C4B5FD;strokeWidth=1;dashed=1;",
    "subnet": "endArrow=none;strokeColor=#9CA3AF;strokeWidth=1;dashed=1;",
    "client-server": "endArrow=block;strokeColor=#38BDF8;strokeWidth=2;",
}


def _label(node) -> str:
    parts = [escape(node.label)]
    if node.ips:
        parts.append(escape(node.ips[0]))
    if node.macs and node.kind in {"ap", "host", "gateway", "server"}:
        parts.append(escape(node.macs[0]))
    extras = []
    if node.ssids and node.kind != "ap":
        extras.append("SSID " + escape(node.ssids[0]))
    if node.channels:
        extras.append("ch " + ",".join(str(c) for c in node.channels))
    if node.signal_dbm is not None:
        extras.append(f"{node.signal_dbm:.0f} dBm")
    caption = node_service_caption(node)
    if caption:
        extras.append(caption)
    if extras:
        parts.append(escape(" · ".join(extras)))
    return "&#xa;".join(parts)


def export_drawio(graph: SurveyGraph, title: str = "Survey map") -> str:
    positions = layout_positions(graph)
    cells: list[str] = ['        <mxCell id="0"/>', '        <mxCell id="1" parent="0"/>']
    for node in graph.nodes:
        x, y = positions[node.id]
        style = KIND_STYLE.get(node.kind, KIND_STYLE["host"])
        if node.medium == "wireless" and node.kind == "host":
            style = KIND_STYLE["ap"].replace("hexagon", "mxgraph.networks.computer")
            style = "rounded=1;whiteSpace=wrap;html=1;fillColor=#451A03;strokeColor=#FBBF24;fontColor=#FEF3C7;"
        w, h = (180, 88) if node.kind != "ap" else (170, 90)
        if node_service_caption(node):
            h += 16
        cells.append(
            f'        <mxCell id="{escape(node.id)}" value="{_label(node)}" style="{style}" '
            f'vertex="1" parent="1"><mxGeometry x="{x:.1f}" y="{y:.1f}" width="{w}" height="{h}" as="geometry"/>'
            f"</mxCell>"
        )
    for link in graph.links:
        style = EDGE_STYLE.get(link.kind, EDGE_STYLE["l2"])
        label = escape(link.label or link.kind)
        if link.ports:
            displays = []
            for item in link.ports:
                text = item.get("display")
                if text and text not in displays:
                    displays.append(str(text))
            if displays:
                label = escape(", ".join(displays[:4]))
        cells.append(
            f'        <mxCell id="{escape(link.id)}" value="{label}" style="{style}" edge="1" parent="1" '
            f'source="{escape(link.source)}" target="{escape(link.target)}">'
            f'<mxGeometry relative="1" as="geometry"/></mxCell>'
        )
    body = "\n".join(cells)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<mxfile host="SurveyMap" modified="2026-09-20" agent="SurveyMap" version="22.1.0">\n'
        f'  <diagram id="survey" name="{escape(title)}">\n'
        '    <mxGraphModel dx="1200" dy="800" grid="1" gridSize="10" guides="1" tooltips="1" '
        'connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1600" pageHeight="1100" math="0" shadow="0">\n'
        "      <root>\n"
        f"{body}\n"
        "      </root>\n"
        "    </mxGraphModel>\n"
        "  </diagram>\n"
        "</mxfile>\n"
    )
