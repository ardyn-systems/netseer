from __future__ import annotations

import ipaddress
import re
from typing import Any

from surveymap.models import GpsFix, Link, Node, SurveyGraph
from surveymap.oui import vendor_from_mac
from surveymap.services import CLIENT_SIDE_PORTS, WELL_KNOWN_SERVER_PORTS, format_port, service_for_port


def normalize_mac(mac: str | None) -> str | None:
    if not mac:
        return None
    raw = re.sub(r"[^0-9a-fA-F]", "", mac)
    if len(raw) != 12:
        return None
    parts = [raw[i : i + 2].lower() for i in range(0, 12, 2)]
    if parts == ["00"] * 6 or parts == ["ff"] * 6:
        return None
    if int(parts[0], 16) & 0x01:
        return None
    return ":".join(parts)


def mac_id(mac: str) -> str:
    return f"mac:{mac}"


def ip_id(ip: str) -> str:
    return f"ip:{ip}"


def subnet_id(network: str) -> str:
    return f"subnet:{network}"


def vlan_id(vlan: int) -> str:
    return f"vlan:{vlan}"


def _merge_unique(dst: list, values: list) -> None:
    for value in values:
        if value is not None and value not in dst:
            dst.append(value)


def _port_key(entry: dict[str, Any]) -> tuple:
    return (
        str(entry.get("proto") or "ip"),
        entry.get("port"),
        entry.get("sport"),
        entry.get("dport"),
        entry.get("role"),
        entry.get("service"),
    )


def _merge_port_records(dst: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = {_port_key(item) for item in dst}
    for item in incoming:
        if not item:
            continue
        key = _port_key(item)
        if key in seen:
            continue
        dst.append(item)
        seen.add(key)
    return dst


def _link_service_label(rec: dict[str, Any], fallback: str) -> str:
    ports = rec.get("ports") or rec.get("extra", {}).get("ports") or []
    displays = []
    for item in ports:
        text = item.get("display")
        if text and text not in displays:
            displays.append(str(text))
    if displays:
        return ", ".join(displays[:4])
    services = rec.get("services") or rec.get("extra", {}).get("services") or []
    if services:
        return ", ".join(str(s) for s in services[:5])
    return fallback


def _undirected_id(kind: str, a: str, b: str) -> str:
    lo, hi = sorted((a, b))
    return f"{kind}:{lo}:{hi}"


class GraphBuilder:
    """Accumulate L2/L3/RF observations into a survey graph."""

    def __init__(self) -> None:
        self.devices: dict[str, dict[str, Any]] = {}
        self.ip_to_device: dict[str, str] = {}
        self.links: dict[str, dict[str, Any]] = {}
        self.subnets: dict[str, dict[str, Any]] = {}
        self.vlans: dict[int, dict[str, Any]] = {}
        self.netmasks: dict[str, int] = {}
        self.sources: list[str] = []
        self.packet_count = 0
        self.warnings: list[str] = []

    def note_source(self, name: str) -> None:
        if name not in self.sources:
            self.sources.append(name)

    def _device(self, node_id: str) -> dict[str, Any]:
        rec = self.devices.get(node_id)
        if rec is None:
            rec = {
                "id": node_id,
                "kind": "host",
                "label": node_id.split(":", 1)[-1],
                "medium": "wired",
                "macs": [],
                "ips": [],
                "ssids": [],
                "channels": [],
                "frequencies_mhz": [],
                "signal_dbm": None,
                "signal_min_dbm": None,
                "signal_max_dbm": None,
                "encryption": [],
                "vlans": [],
                "gps": None,
                "vendor": None,
                "roles": [],
                "services": [],
                "ports": [],
                "routing": {},
                "extra": {},
            }
            self.devices[node_id] = rec
        return rec

    def add_role(self, node_id: str, role: str) -> None:
        rec = self._device(node_id)
        if role not in rec["roles"]:
            rec["roles"].append(role)
        if role == "ap":
            rec["kind"] = "ap"
            rec["medium"] = "wireless"
        elif role == "gateway" and rec["kind"] == "host":
            rec["kind"] = "gateway"
        elif role == "server" and rec["kind"] in {"host", "client"}:
            rec["kind"] = "server"
        elif role == "station":
            rec["medium"] = "wireless"

    def observe_mac(
        self,
        mac: str | None,
        *,
        wireless: bool = False,
        vendor: str | None = None,
        label: str | None = None,
    ) -> str | None:
        mac = normalize_mac(mac)
        if not mac:
            return None
        node_id = mac_id(mac)
        rec = self._device(node_id)
        _merge_unique(rec["macs"], [mac])
        if wireless:
            rec["medium"] = "wireless"
        if vendor:
            rec["vendor"] = vendor
        elif rec["vendor"] is None:
            rec["vendor"] = vendor_from_mac(mac)
        if label and rec["label"] in {mac, node_id.split(":", 1)[-1]}:
            rec["label"] = label
        return node_id

    def observe_ip(self, ip: str | None, mac: str | None = None) -> str | None:
        if not ip:
            return None
        try:
            parsed = ipaddress.ip_address(ip)
        except ValueError:
            return None
        if parsed.is_unspecified or parsed.is_multicast or parsed.is_reserved:
            return None
        ip_s = str(parsed)
        node_id = None
        if mac:
            node_id = self.observe_mac(mac)
        if node_id is None:
            node_id = self.ip_to_device.get(ip_s) or ip_id(ip_s)
        rec = self._device(node_id)
        _merge_unique(rec["ips"], [ip_s])
        if rec["label"] in rec["macs"] or rec["label"].startswith("mac:") or rec["label"] == rec["id"].split(":", 1)[-1]:
            rec["label"] = ip_s
        self.ip_to_device[ip_s] = node_id
        return node_id

    def bind_ip_mac(self, ip: str | None, mac: str | None) -> str | None:
        mac_node = self.observe_mac(mac)
        ip_node = self.observe_ip(ip)
        if mac_node and ip_node and mac_node != ip_node:
            # Merge IP-only node into MAC node.
            src = self.devices.pop(ip_node, None)
            rec = self._device(mac_node)
            if src:
                _merge_unique(rec["ips"], src["ips"])
                _merge_unique(rec["roles"], src["roles"])
                _merge_unique(rec["vlans"], src["vlans"])
                _merge_unique(rec["services"], src.get("services") or [])
                rec["ports"] = _merge_port_records(rec.get("ports") or [], src.get("ports") or [])
                rec["routing"].update(src.get("routing") or {})
            for key, value in list(self.ip_to_device.items()):
                if value == ip_node:
                    self.ip_to_device[key] = mac_node
            for link in self.links.values():
                if link["source"] == ip_node:
                    link["source"] = mac_node
                if link["target"] == ip_node:
                    link["target"] = mac_node
            node_id = mac_node
        else:
            node_id = mac_node or ip_node
        if node_id and ip:
            self.observe_ip(ip, mac)
        return node_id

    def observe_vlan(self, vlan: int | None, node_id: str | None = None) -> None:
        if vlan is None:
            return
        try:
            vlan_n = int(vlan)
        except (TypeError, ValueError):
            return
        if vlan_n <= 0 or vlan_n >= 4095:
            return
        rec = self.vlans.setdefault(vlan_n, {"id": vlan_id(vlan_n), "label": f"VLAN {vlan_n}", "members": []})
        if node_id:
            device = self._device(node_id)
            _merge_unique(device["vlans"], [vlan_n])
            _merge_unique(rec["members"], [node_id])
            self._link(
                node_id,
                rec["id"],
                kind="vlan",
                label=f"VLAN {vlan_n}",
                medium="wired",
                vlans=[vlan_n],
            )

    def observe_subnet(self, ip: str | None, prefix: int | None = None) -> str | None:
        if not ip:
            return None
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return None
        if addr.is_link_local or addr.is_loopback or addr.is_multicast:
            return None
        if prefix is None:
            prefix = self.netmasks.get(str(addr))
        if prefix is None:
            prefix = 24 if addr.version == 4 else 64
        network = ipaddress.ip_network((addr, prefix), strict=False)
        net_s = str(network)
        rec = self.subnets.setdefault(
            net_s,
            {"id": subnet_id(net_s), "label": net_s, "members": [], "prefix": prefix},
        )
        node_id = self.ip_to_device.get(str(addr))
        if node_id:
            _merge_unique(rec["members"], [node_id])
            self._link(node_id, rec["id"], kind="subnet", label=net_s, medium="wired")
        return rec["id"]

    def observe_signal(self, node_id: str, dbm: float | None) -> None:
        if dbm is None:
            return
        rec = self._device(node_id)
        rec["signal_dbm"] = float(dbm)
        rec["signal_min_dbm"] = (
            float(dbm) if rec["signal_min_dbm"] is None else min(rec["signal_min_dbm"], float(dbm))
        )
        rec["signal_max_dbm"] = (
            float(dbm) if rec["signal_max_dbm"] is None else max(rec["signal_max_dbm"], float(dbm))
        )

    def observe_rf(
        self,
        node_id: str,
        *,
        ssid: str | None = None,
        channel: int | None = None,
        frequency_mhz: float | None = None,
        encryption: str | None = None,
        gps: GpsFix | None = None,
    ) -> None:
        rec = self._device(node_id)
        rec["medium"] = "wireless"
        if ssid:
            _merge_unique(rec["ssids"], [ssid])
            if rec["kind"] == "ap" or rec["label"] in rec["macs"]:
                rec["label"] = ssid
        if channel is not None:
            try:
                _merge_unique(rec["channels"], [int(channel)])
            except (TypeError, ValueError):
                pass
        if frequency_mhz is not None:
            try:
                _merge_unique(rec["frequencies_mhz"], [float(frequency_mhz)])
            except (TypeError, ValueError):
                pass
        if encryption:
            _merge_unique(rec["encryption"], [encryption])
        if gps:
            rec["gps"] = gps

    def observe_service(self, node_id: str, service: str | None) -> None:
        if not service:
            return
        rec = self._device(node_id)
        _merge_unique(rec["services"], [service])

    def observe_port(
        self,
        node_id: str,
        *,
        proto: str | None,
        port: int | None,
        role: str,
        service: str | None = None,
    ) -> None:
        if port is None:
            if service:
                self.observe_service(node_id, service)
            return
        rec = self._device(node_id)
        named = service or service_for_port(port, proto)
        if named and role == "listen":
            self.observe_service(node_id, named)
        entry = {
            "proto": (proto or "ip").lower(),
            "port": int(port),
            "role": role,
            "service": named,
            "display": format_port(proto, port, named),
        }
        rec["ports"] = _merge_port_records(rec.get("ports") or [], [entry])

    def observe_routing(self, node_id: str, **fields: Any) -> None:
        rec = self._device(node_id)
        for key, value in fields.items():
            if value in (None, "", [], {}):
                continue
            existing = rec["routing"].get(key)
            if isinstance(existing, list) and not isinstance(value, list):
                _merge_unique(existing, [value])
            elif isinstance(existing, list) and isinstance(value, list):
                _merge_unique(existing, value)
            else:
                rec["routing"][key] = value
            if key == "services":
                names = value if isinstance(value, list) else [value]
                _merge_unique(rec["services"], [str(v) for v in names if v])

    def _link(
        self,
        source: str,
        target: str,
        *,
        kind: str,
        label: str = "",
        medium: str = "wired",
        vlans: list[int] | None = None,
        directed: bool = False,
        extra: dict[str, Any] | None = None,
    ) -> None:
        if not source or not target or source == target:
            return
        link_id = f"{kind}:{source}:{target}" if directed else _undirected_id(kind, source, target)
        rec = self.links.get(link_id)
        if rec is None:
            rec = {
                "id": link_id,
                "source": source if directed else sorted((source, target))[0],
                "target": target if directed else sorted((source, target))[1],
                "kind": kind,
                "label": label,
                "medium": medium,
                "vlans": [],
                "services": [],
                "ports": [],
                "extra": {"count": 0},
            }
            if directed:
                rec["source"] = source
                rec["target"] = target
            self.links[link_id] = rec
        rec["extra"]["count"] = int(rec["extra"].get("count") or 0) + 1
        extra = dict(extra or {})
        incoming_ports = extra.pop("ports", None) or []
        incoming_services = extra.pop("services", None) or []
        single_service = extra.pop("service", None)
        if single_service:
            incoming_services = list(incoming_services) + [single_service]
        rec["ports"] = _merge_port_records(rec.get("ports") or [], incoming_ports)
        rec["extra"]["ports"] = rec["ports"]
        _merge_unique(rec["services"], incoming_services)
        rec["extra"]["services"] = rec["services"]
        if extra:
            rec["extra"].update(extra)
        rec["label"] = _link_service_label(rec, rec["label"] or label or kind)
        _merge_unique(rec["vlans"], vlans or [])

    def add_l2(self, src_mac: str | None, dst_mac: str | None, vlan: int | None = None) -> None:
        src = self.observe_mac(src_mac)
        dst = self.observe_mac(dst_mac)
        if src and dst:
            self._link(src, dst, kind="l2", label="L2", medium="wired", vlans=[vlan] if vlan else None)
        self.observe_vlan(vlan, src)
        self.observe_vlan(vlan, dst)

    def add_l3(
        self,
        src_ip: str | None,
        dst_ip: str | None,
        *,
        proto: str | None = None,
        sport: int | None = None,
        dport: int | None = None,
        src_mac: str | None = None,
        dst_mac: str | None = None,
        vlan: int | None = None,
        service: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        src = self.observe_ip(src_ip)
        dst = self.observe_ip(dst_ip)
        named = service or service_for_port(dport, proto) or service_for_port(sport, proto)
        dst_known = dport is not None and dport in WELL_KNOWN_SERVER_PORTS and dport not in CLIENT_SIDE_PORTS
        src_known = sport is not None and sport in WELL_KNOWN_SERVER_PORTS and sport not in CLIENT_SIDE_PORTS
        server, client = dst, src
        if (dport in CLIENT_SIDE_PORTS and src_known) or (src_known and not dst_known):
            server, client = src, dst
            listen_port, client_port = sport, dport
        else:
            listen_port, client_port = dport, sport

        port_entry = None
        if proto in {"tcp", "udp"} and (sport is not None or dport is not None):
            port_entry = {
                "proto": proto,
                "sport": sport,
                "dport": dport,
                "service": named,
                "display": format_port(proto, listen_port or dport or sport, named),
            }

        if src and dst:
            l3_label = named or (f"{proto}/{dport}" if proto and dport is not None else (proto or "IP").upper())
            extra: dict[str, Any] = {"proto": proto}
            if port_entry:
                extra["ports"] = [port_entry]
            if named:
                extra["services"] = [named]
            if metadata:
                extra.update(metadata)
            self._link(src, dst, kind="l3", label=l3_label, medium="wired", extra=extra)

        if src:
            if src == server and listen_port is not None:
                self.observe_port(src, proto=proto, port=listen_port, role="listen", service=named)
            elif client_port is not None and (
                client_port in WELL_KNOWN_SERVER_PORTS or client_port in CLIENT_SIDE_PORTS
            ):
                self.observe_port(src, proto=proto, port=client_port, role="client", service=named)
        if dst:
            if dst == server and listen_port is not None:
                self.observe_port(dst, proto=proto, port=listen_port, role="listen", service=named)
            elif dport is not None and dport in WELL_KNOWN_SERVER_PORTS:
                self.observe_port(dst, proto=proto, port=dport, role="dest", service=named)
        if named and server:
            self.observe_service(server, named)

        if (named or dst_known or src_known) and src and dst:
            self.add_role(server, "server")
            self.add_role(client, "client")
            cs_extra: dict[str, Any] = {}
            if named:
                cs_extra["services"] = [named]
            if port_entry:
                cs_extra["ports"] = [port_entry]
            if metadata:
                cs_extra.update(metadata)
            self._link(
                client,
                server,
                kind="client-server",
                label=named or format_port(proto, listen_port, named),
                directed=True,
                extra=cs_extra,
            )
        self.observe_vlan(vlan, src)
        self.observe_vlan(vlan, dst)

    def add_wireless_link(
        self,
        sta_mac: str | None,
        bssid: str | None,
        *,
        ssid: str | None = None,
        associated: bool = True,
    ) -> None:
        ap = self.observe_mac(bssid, wireless=True)
        sta = self.observe_mac(sta_mac, wireless=True)
        if ap:
            self.add_role(ap, "ap")
            if ssid:
                self.observe_rf(ap, ssid=ssid)
        if sta:
            self.add_role(sta, "station")
            if ssid:
                self.observe_rf(sta, ssid=ssid)
        if ap and sta:
            self._link(
                sta,
                ap,
                kind="wireless",
                label=ssid or "802.11",
                medium="wireless",
                extra={"associated": associated},
            )

    def add_ap(
        self,
        bssid: str | None,
        *,
        ssid: str | None = None,
        channel: int | None = None,
        frequency_mhz: float | None = None,
        encryption: str | None = None,
        signal_dbm: float | None = None,
        gps: GpsFix | None = None,
        vendor: str | None = None,
    ) -> str | None:
        node_id = self.observe_mac(bssid, wireless=True, vendor=vendor, label=ssid)
        if not node_id:
            return None
        self.add_role(node_id, "ap")
        self.observe_rf(
            node_id,
            ssid=ssid,
            channel=channel,
            frequency_mhz=frequency_mhz,
            encryption=encryption,
            gps=gps,
        )
        self.observe_signal(node_id, signal_dbm)
        return node_id

    def finalize(self) -> SurveyGraph:
        for ip, node_id in list(self.ip_to_device.items()):
            prefix = self.netmasks.get(ip)
            self.observe_subnet(ip, prefix)
            rec = self.devices.get(node_id)
            if rec and rec["label"] in rec["macs"] and rec["ips"]:
                rec["label"] = rec["ips"][0]
            if rec and rec["ssids"] and rec["kind"] == "ap":
                rec["label"] = rec["ssids"][0]

        nodes: list[Node] = []
        for rec in self.devices.values():
            gps = rec["gps"]
            nodes.append(
                Node(
                    id=rec["id"],
                    kind=rec["kind"],
                    label=rec["label"],
                    medium=rec["medium"],
                    macs=rec["macs"],
                    ips=rec["ips"],
                    ssids=rec["ssids"],
                    channels=rec["channels"],
                    frequencies_mhz=rec["frequencies_mhz"],
                    signal_dbm=rec["signal_dbm"],
                    signal_min_dbm=rec["signal_min_dbm"],
                    signal_max_dbm=rec["signal_max_dbm"],
                    encryption=rec["encryption"],
                    vlans=rec["vlans"],
                    gps=gps if isinstance(gps, GpsFix) else GpsFix(**gps) if gps else None,
                    vendor=rec["vendor"],
                    roles=rec["roles"],
                    services=rec["services"],
                    ports=rec["ports"],
                    routing=rec["routing"],
                    extra=rec["extra"],
                )
            )
        for net, rec in self.subnets.items():
            nodes.append(
                Node(
                    id=rec["id"],
                    kind="subnet",
                    label=rec["label"],
                    medium="wired",
                    extra={"members": rec["members"], "prefix": rec["prefix"]},
                )
            )
        for vid, rec in self.vlans.items():
            nodes.append(
                Node(
                    id=rec["id"],
                    kind="vlan",
                    label=rec["label"],
                    medium="wired",
                    vlans=[vid],
                    extra={"members": rec["members"]},
                )
            )

        node_ids = {n.id for n in nodes}
        links = [
            Link(
                id=rec["id"],
                source=rec["source"],
                target=rec["target"],
                kind=rec["kind"],
                label=rec["label"],
                medium=rec["medium"],
                vlans=rec["vlans"],
                services=rec.get("services") or rec["extra"].get("services") or [],
                ports=rec.get("ports") or rec["extra"].get("ports") or [],
                extra=rec["extra"],
            )
            for rec in self.links.values()
            if rec["source"] in node_ids and rec["target"] in node_ids
        ]
        return SurveyGraph(
            nodes=sorted(nodes, key=lambda n: n.id),
            links=sorted(links, key=lambda e: e.id),
            meta={
                "sources": self.sources,
                "packet_count": self.packet_count,
                "node_count": len(nodes),
                "link_count": len(links),
                "warnings": self.warnings,
            },
        )
