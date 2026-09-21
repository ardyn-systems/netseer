# Unwanted dumps

Emptying the **Unwanted** holding map writes one NetSeer JSON dump per original capture into this folder.

Names look like `Unwanted-office-lan.json` (from `office-lan.pcap`). Devices with no capture name go to `Unwanted-unknown.json`.

Drop a dump onto **Load a survey** to reload it as a map. These files are a readable graph sidecar (nodes, links, notes), not a reconstructed pcap.
