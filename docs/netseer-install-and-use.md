# NetSeer — install and use on Linux

**Turn traffic into terrain.**

Walkthrough for installing the NetSeer preview on Debian/Ubuntu and using the browser map. One local Python web app; not a compiled binary yet.

## What it is

NetSeer is a **local** survey-to-map tool:

- Python package (import path `surveymap`, public CLI `netseer`)
- FastAPI + uvicorn serves a small UI in your browser
- You drop Wireshark / tcpdump / Kismet / airodump-ng files; it draws L2/L3/RF as a map
- Export the same picture to draw.io, Visio, and PDF/CSV/XML/text

It is **not** an installer `.deb`, AppImage, or standalone binary. You run it from source on the machine that holds the captures (or copy captures in). The map UI loads Cytoscape from a CDN (`cdn.jsdelivr.net`), so the browser needs outbound HTTPS the first time you open the map.

Bundled campus samples ship in `src/surveymap/data/` so you can click around without uploading anything.

## Requirements

- **OS:** Debian-family Linux (Debian, Ubuntu, Mint, …). Other distros work if you have Python 3.12+.
- **Python:** **3.12 or newer** (`requires-python = ">=3.12"`). Ubuntu 24.04 is fine. Debian 12’s default `python3` is 3.11 — use 3.12 (or let `uv` fetch it).
- **Packages the README actually installs:**

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip
```

- **Optional but useful:** `curl` (uv installer, IEEE OUI refresh), `git` (if you clone).
- **No database, no login, no extra daemons.** Scapy reads pcap files from disk; this preview does not live-sniff.

Python deps (installed into the venv, not apt): FastAPI, uvicorn, python-multipart, scapy, reportlab.

## Install from source

Get the project tree onto the box first (see [[#Next steps on your own Linux computer]]). Then pick **uv** or **venv + pip**.

### Path A — uv (preferred)

[uv](https://docs.astral.sh/uv/) can install Python 3.12 for you.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# open a new shell, or: source $HOME/.local/bin/env

cd /path/to/netseer
uv python install 3.12
uv sync --group dev
uv run python -m surveymap.generate_samples
```

`uv sync` creates `.venv` and installs the package (CLI `netseer`) plus pytest.

### Path B — python3 venv and pip

```bash
cd /path/to/netseer
python3 -m venv .venv
source .venv/bin/activate
python -c "import sys; assert sys.version_info >= (3, 12), sys.version"
pip install -U pip
pip install -e ".[dev]"
python -m surveymap.generate_samples
```

If `python3` is 3.11, install 3.12 and call it explicitly (`python3.12 -m venv .venv`). Pip needs to fetch the `uv_build` build backend from PyPI (declared in `pyproject.toml`).

`generate_samples` rewrites the bundled `.pcap` / `.pcapng` / Kismet / airodump files under `src/surveymap/data/`. Skip it if those files are already there.

## Start the preview

Default bind is **all interfaces**, port **47331**.

```bash
# uv
uv run netseer --host 0.0.0.0 --port 47331

# venv
source .venv/bin/activate
netseer --host 0.0.0.0 --port 47331
```

Open [http://127.0.0.1:47331](http://127.0.0.1:47331).

- `--host 127.0.0.1` if you only want local loopback
- `--host 0.0.0.0` if other machines on the LAN should hit it
- Change `--port` if 47331 is taken

The CLI name is `netseer`. `surveymap` is also registered as an alias. Leave the process running while you use the UI.

## How to use

Campus survey (combined) loads on first visit. Empty, loading, and parse-error overlays cover the other states.

### Load and remove surveys

Left panel, **Load a survey**:

1. Click a bundled sample, **or** drop / pick `.pcap`, `.pcapng`, `.cap`, `.netxml`, `.csv`.
2. Uploads join the same list (tagged as uploaded captures).
3. **Remove** hides a bundled sample or drops an upload from the list. It does not delete files on disk.
4. **Restore bundled samples** comes back if you hid them all.

On a narrow screen, **Samples** in the header opens the left panel.

### Map labels

Nodes show a **short type**, not a dump of MAC/IP/OUI:

Access point, Wireless client, Router, Switch, Server, Gateway, Host. VLAN and subnet objects keep their network names (`VLAN 10`, `10.10.10.0/24`, …).

Click a device → **Map name** and **On-map extra** (second line). **Use auto name** restores the inferred type. Edits stick in the browser (`localStorage`) for this origin.

### Zoom

Bottom-right **Zoom** slider (20–400%) stays in sync with wheel zoom. **Fit** frames the graph.

### Show layers

Left **Show** checkboxes:

| Layer | What it toggles |
| --- | --- |
| Wired L2 | Ethernet adjacency |
| L3 / IP | IP conversations |
| Ports & services | Client → server edges (http, dns, ssh, …) |
| Wireless | STA ↔ AP |
| VLANs | VLAN membership |
| Subnets | Subnet membership |
| Bridge / attachment | STP / WDS / spanning-host links between **distinct** networks |

**Show all** checks every box. **Show none** clears every box (nodes stay; those edges hide).

Pink diamond-dashed **bridge / attachment** lines appear only when the capture has evidence: a device MAC on more than one VLAN (or two same-version subnets), an 802.1D STP BPDU, or 802.11 four-address WDS. NetSeer does not invent bridges.

### Device window

Click a node. The dialog lists extracted fields.

- **Capture** vs **Edited** on each row. Type to override; **Reset** goes back to what the parser found.
- Editable: type/kind/medium, TX / RX / DA / RA MACs, other MACs, IPs, VLANs, SSIDs, channel, frequency, encryption, OUI manufacturer, ports/services, GPS, routing, extra JSON, and the rest of the property list. `id` stays read-only.
- **Your notes** at the bottom.
- Copy one field, **Copy all**, or download **PDF / CSV / XML / Plain text**. Notes and edits go with those exports when present.

The right **Details** inspector shows the live overlay (including `User-edited: …`). Click a **bridge** edge to see kind `bridge`, mechanism (STP / WDS / attachment), and via device.

**TX / RX / DA / RA** are only filled from frames. Wired: TX = Ethernet src, DA and RX = dst, RA omitted. 802.11 follows ToDS/FromDS. Missing roles say `not present` — they are not guessed.

**OUI manufacturer** comes from the bundled IEEE MA-L / MA-M / MA-S / CID table.

### Exports (toolbar)

Need a map loaded (buttons disable on empty).

| Button | File |
| --- | --- |
| Export draw.io | `netseer-map.drawio` |
| Export Visio .vsdx | `netseer-map.vsdx` |
| Export Visio XML | `netseer-map.vdx` |
| Report PDF | whole-map PDF (devices + links) |

Device-window downloads are per node. Map-name, extra, notes, and field edits are included in the graph posted to the server.

## Optional: tests and OUI table

```bash
uv run pytest
# or: pytest   (inside the venv)
```

Rebuild manufacturers from IEEE CSVs:

```bash
curl -L -o /tmp/oui.csv https://standards-oui.ieee.org/oui/oui.csv
curl -L -o /tmp/mam.csv https://standards-oui.ieee.org/oui28/mam.csv
curl -L -o /tmp/oui36.csv https://standards-oui.ieee.org/oui36/oui36.csv
curl -L -o /tmp/cid.csv https://standards-oui.ieee.org/cid/cid.csv
uv run python -m surveymap.compile_oui /tmp/oui.csv /tmp/mam.csv /tmp/oui36.csv /tmp/cid.csv
```

## Next steps on your own Linux computer

This session could **not** create a public GitHub repo named `netseer`: `gh` is not logged in (`gh auth status` → not logged into any GitHub hosts). There is no clone URL to hand you from here.

Do one of:

1. **Copy the tree** — zip or `rsync` the project directory (including `src/`, `web/`, `tests/`, `pyproject.toml`, `README.md`). On the target box, follow [[#Install from source]] and [[#Start the preview]].
2. **Make your own GitHub repo** — on a machine where you `gh auth login` (or use the GitHub UI), create `netseer`, add the remote, push this source, then `git clone` on Debian/Ubuntu.
3. **After a clone URL exists** — `git clone <url> && cd netseer` and use Path A or B above.

Stay on a branch that has the current UI (bridge attachments, editable fields, Show all/none, type labels). Then:

```bash
uv sync --group dev
uv run netseer --host 127.0.0.1 --port 47331
```

Open http://127.0.0.1:47331, click **Campus survey (combined)**, try **Show none** / **Show all**, open a Router, edit a field, export draw.io.

Edits live in **this browser’s** `localStorage` (`netseer.deviceMeta.v1`, `netseer.hiddenSamples`). They are not written back into the pcap.

## Quick reference

| Item | Value |
| --- | --- |
| Product | NetSeer |
| Motto | Turn traffic into terrain. |
| CLI | `netseer` |
| Python import | `surveymap` |
| Default URL | http://127.0.0.1:47331 |
| Default bind | `0.0.0.0:47331` |
| Samples | `src/surveymap/data/` |
| UI | `web/` |
