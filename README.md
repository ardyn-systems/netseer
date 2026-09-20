# SurveyMap

Turn Layer 2 / Layer 3 network surveys into an interactive map, then export **draw.io** and **Visio**.

This is a web preview (not a compiled binary). It runs on Debian-family Linux and ships with synthetic campus captures so you can try it without uploading files.

## What it reads

| Source | Extensions |
| --- | --- |
| Wireshark / tshark | `.pcap`, `.pcapng` |
| tcpdump | `.pcap` |
| Kismet | `.pcap`, `.pcapng`, `.netxml`, `.csv` |
| airodump-ng | `.csv`, `.cap` |

## What the map shows

When the frames or survey rows include them:

- MAC and IP addresses, vendor (short OUI table)
- VLANs, subnet membership, default gateway / DHCP options, OSPF
- Wireless SSIDs, BSSID, channel, frequency, encryption, signal, GPS
- **TCP/UDP ports and named services** on nodes and on client→server edges (HTTP, HTTPS/TLS, SSH, DNS, DHCP, NTP, SNMP, OSPF, and other well-known ports). Names also come from protocol metadata in the frames (DNS queries, HTTP `Host`, SSH ident, TLS handshake).

Click a device to open a **detail window** with every extracted field, per-field copy, copy-all, and downloads (PDF, CSV, XML, plain text). **Report PDF** in the toolbar dumps the whole map.

Wired L2, L3, wireless, VLAN, and service edges can be toggled independently.

## Exports (same attributes as the preview)

- **draw.io** — `.drawio` mxfile XML
- **Visio** — `.vsdx` (Open XML) and `.vdx` (Visio 2003 XML)
- **Device details** — PDF, CSV, XML, and `.txt` from the device window
- **Map report** — PDF of every device and link

Node labels include identity plus listen ports/services. Edge labels include `service proto/port` (for example `http tcp/80`).

## Run on Debian / Ubuntu

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m surveymap.generate_samples   # recreates bundled survey files
python -m surveymap --host 0.0.0.0 --port 47331
```

With [uv](https://docs.astral.sh/uv/):

```bash
uv sync --group dev
uv run python -m surveymap.generate_samples
uv run surveymap --port 47331
```

Open [http://127.0.0.1:47331](http://127.0.0.1:47331). The campus combined sample loads automatically. Drop your own capture onto the left panel, inspect a node for ports/services, then export draw.io or Visio.

Bundled files live in `src/surveymap/data/`.

## Tests

```bash
uv run pytest
```
