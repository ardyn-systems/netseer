from __future__ import annotations

from surveymap.detect import sniff_format
from surveymap.exporters.drawio import export_drawio
from surveymap.exporters.visio import export_vdx, export_vsdx
from surveymap.generate_samples import write_all
from surveymap.ingest import ingest_files
from surveymap.samples import DATA_DIR, files_for_sample


def test_samples_exist_after_generate(tmp_path):
    dest = write_all(tmp_path)
    assert (dest / "office-lan.pcap").stat().st_size > 0
    assert (dest / "wifi-campus.pcapng").stat().st_size > 0


def test_office_lan_has_ports_and_services():
    if not (DATA_DIR / "office-lan.pcap").exists():
        write_all(DATA_DIR)
    graph = ingest_files(files_for_sample("office-lan"))
    services = {s for n in graph.nodes for s in n.services}
    assert "http" in services
    assert "dns" in services
    assert "ssh" in services
    assert "dhcp" in services
    listen = [p for n in graph.nodes for p in n.ports if p.get("role") == "listen"]
    ports = {p.get("port") for p in listen}
    assert 80 in ports
    assert 53 in ports
    assert 22 in ports
    cs = [e for e in graph.links if e.kind == "client-server"]
    assert cs
    labels = " ".join(e.label for e in cs)
    assert "http" in labels
    xml = export_drawio(graph)
    assert "http" in xml.lower()
    vdx = export_vdx(graph)
    assert "http" in vdx.lower() or "tcp/80" in vdx.lower()
    vsdx = export_vsdx(graph)
    assert vsdx[:2] == b"PK"


def test_kismet_and_airodump():
    if not (DATA_DIR / "kismet-walk.netxml").exists():
        write_all(DATA_DIR)
    kismet = ingest_files(files_for_sample("kismet-walk"))
    ssids = {s for n in kismet.nodes for s in n.ssids}
    assert "HQ-Secure" in ssids
    gps_nodes = [n for n in kismet.nodes if n.gps]
    assert gps_nodes
    dump = ingest_files(files_for_sample("airodump"))
    assert any(n.kind == "ap" for n in dump.nodes)
    assert any(e.kind == "wireless" for e in dump.links)


def test_unsupported_and_empty(tmp_path):
    assert sniff_format(b"\xd4\xc3\xb2\xa1", "x.pcap") == "pcap"
    try:
        ingest_files([("note.txt", b"hello world")])
        assert False, "expected unsupported"
    except Exception as exc:
        assert "Unsupported" in str(exc) or "unsupported" in str(exc).lower()
    try:
        ingest_files(files_for_sample("empty-capture"))
        assert False, "expected empty survey"
    except Exception as exc:
        assert "No hosts" in str(exc)
