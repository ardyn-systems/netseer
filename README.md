<p align="center">
  <img src="web/logo-192.png" alt="NetSeer logo" width="168" />
</p>

# NetSeer

**Turn traffic into terrain.**

NetSeer turns Layer 2 / Layer 3 network surveys into an interactive map, then export **draw.io** and **Visio**.

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

- MAC and IP addresses
- **OUI manufacturer** from the IEEE MA-L / MA-M / MA-S / CID registries (locally administered and unregistered prefixes are labeled as such)
- VLANs, subnet membership, default gateway / DHCP options, OSPF
- Wireless SSIDs, BSSID, channel, frequency, encryption, signal, GPS
- **TCP/UDP ports and named services** on nodes and on client→server edges (HTTP, HTTPS/TLS, SSH, DNS, DHCP, NTP, SNMP, OSPF, and other well-known ports). Names also come from protocol metadata in the frames (DNS queries, HTTP `Host`, SSH ident, TLS handshake).

Click a device to open a **detail window** with every extracted field, per-field copy, copy-all, and downloads (PDF, CSV, XML, plain text). **Report PDF** in the toolbar dumps the whole map, with NetSeer chrome on every page.

Wired L2, L3, wireless, VLAN, and service edges can be toggled independently.

## Exports (same attributes as the preview)

- **draw.io** — `.drawio` mxfile XML (`netseer-map.drawio`)
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
netseer --host 0.0.0.0 --port 47331
```

With [uv](https://docs.astral.sh/uv/):

```bash
uv sync --group dev
uv run python -m surveymap.generate_samples
uv run netseer --port 47331
```

Open [http://127.0.0.1:47331](http://127.0.0.1:47331). The campus combined sample loads automatically. Drop your own capture onto the left panel — it is added to **Load a survey** with a Remove control. Bundled samples can be hidden from the list (files stay on disk) and restored with **Restore bundled samples**. Use the map **Zoom** slider (kept in sync with scroll/pinch). Inspect a node for TX/RX/DA/RA MACs, ports, and services, then export draw.io or Visio.

The public CLI is `netseer`. The Python import path remains `surveymap`. Bundled files live in `src/surveymap/data/`. The OUI table is compiled from IEEE CSVs:

```bash
curl -L -o /tmp/oui.csv https://standards-oui.ieee.org/oui/oui.csv
curl -L -o /tmp/mam.csv https://standards-oui.ieee.org/oui28/mam.csv
curl -L -o /tmp/oui36.csv https://standards-oui.ieee.org/oui36/oui36.csv
curl -L -o /tmp/cid.csv https://standards-oui.ieee.org/cid/cid.csv
uv run python -m surveymap.compile_oui /tmp/oui.csv /tmp/mam.csv /tmp/oui36.csv /tmp/cid.csv
```

## Tests

```bash
uv run pytest
```
