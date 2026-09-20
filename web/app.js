/* SurveyMap preview — cytoscape map, samples, upload, export. */
const state = {
  graph: null,
  title: "Survey map",
  cy: null,
  filters: {
    l2: true,
    l3: true,
    "client-server": true,
    wireless: true,
    vlan: true,
    subnet: true,
  },
};

const el = (id) => document.getElementById(id);

function show(id, on) {
  el(id).classList.toggle("hidden", !on);
}

function setStatus(text) {
  el("status").textContent = text;
}

function nodeCaption(node) {
  const listens = (node.ports || []).filter((p) => p.role === "listen" || p.role === "dest");
  const displays = [];
  for (const p of listens) {
    if (p.display && !displays.includes(p.display)) displays.push(p.display);
  }
  if (displays.length) return displays.slice(0, 3).join(" · ");
  return (node.services || []).slice(0, 3).join(" · ");
}

function nodeLabel(node) {
  const lines = [node.label];
  if (node.ips && node.ips[0] && node.ips[0] !== node.label) lines.push(node.ips[0]);
  if (node.vendor) lines.push(node.vendor);
  const cap = nodeCaption(node);
  if (cap) lines.push(cap);
  return lines.join("\n");
}

function edgeLabel(link) {
  const displays = [];
  for (const p of link.ports || []) {
    if (p.display && !displays.includes(p.display)) displays.push(p.display);
  }
  if (displays.length) return displays.slice(0, 2).join(", ");
  if (link.services && link.services.length) return link.services.slice(0, 2).join(", ");
  return link.label || link.kind;
}

function colorFor(node) {
  if (node.kind === "ap" || node.medium === "wireless") return "#fbbf24";
  if (node.kind === "gateway") return "#c4b5fd";
  if (node.kind === "server") return "#38bdf8";
  if (node.kind === "vlan") return "#a78bfa";
  if (node.kind === "subnet") return "#94a3b8";
  return "#5eead4";
}

function edgeColor(link) {
  if (link.kind === "wireless") return "#fbbf24";
  if (link.kind === "client-server") return "#38bdf8";
  if (link.kind === "l3") return "#86efac";
  if (link.kind === "vlan") return "#c4b5fd";
  if (link.kind === "subnet") return "#64748b";
  return "#5eead4";
}

function toElements(graph) {
  const nodes = graph.nodes.map((n) => ({
    data: {
      id: n.id,
      label: nodeLabel(n),
      kind: n.kind,
      medium: n.medium,
      color: colorFor(n),
      raw: n,
    },
  }));
  const edges = graph.links
    .filter((l) => state.filters[l.kind] !== false)
    .map((l) => ({
      data: {
        id: l.id,
        source: l.source,
        target: l.target,
        label: edgeLabel(l),
        kind: l.kind,
        color: edgeColor(l),
        dashed: l.kind === "wireless" || l.kind === "l3" || l.kind === "vlan" || l.kind === "subnet",
        raw: l,
      },
    }));
  return nodes.concat(edges);
}

function renderMap() {
  const container = el("map");
  if (state.cy) {
    state.cy.destroy();
    state.cy = null;
  }
  if (!state.graph) return;
  state.cy = cytoscape({
    container,
    elements: toElements(state.graph),
    style: [
      {
        selector: "node",
        style: {
          label: "data(label)",
          "text-wrap": "wrap",
          "text-max-width": 140,
          "font-size": 9,
          color: "#e8eef8",
          "text-valign": "center",
          "background-color": "#0f172a",
          "border-width": 2,
          "border-color": "data(color)",
          width: 78,
          height: 48,
          shape: "roundrectangle",
        },
      },
      {
        selector: 'node[kind = "ap"]',
        style: { shape: "hexagon", width: 72, height: 64 },
      },
      {
        selector: 'node[kind = "subnet"], node[kind = "vlan"]',
        style: { "border-style": "dashed", opacity: 0.9 },
      },
      {
        selector: "edge",
        style: {
          label: "data(label)",
          "font-size": 8,
          color: "#cbd5e1",
          "text-rotation": "autorotate",
          "curve-style": "bezier",
          width: 2,
          "line-color": "data(color)",
          "target-arrow-color": "data(color)",
          "target-arrow-shape": "none",
          "line-style": "solid",
        },
      },
      {
        selector: "edge[dashed]",
        style: { "line-style": "dashed" },
      },
      {
        selector: 'edge[kind = "client-server"]',
        style: { "target-arrow-shape": "triangle", width: 2.5 },
      },
    ],
    layout: { name: "cose", animate: false, padding: 24, nodeOverlap: 16, gravity: 0.4 },
  });
  state.cy.on("tap", "node", (evt) => {
    const node = evt.target.data("raw");
    inspect("node", node);
    openDeviceDialog(node);
  });
  state.cy.on("tap", "edge", (evt) => inspect("link", evt.target.data("raw")));
  state.cy.on("tap", (evt) => {
    if (evt.target === state.cy) inspect(null, null);
  });
}

function chips(values) {
  if (!values || !values.length) return "";
  return `<div class="chips">${values.map((v) => `<span class="chip">${escapeHtml(String(v))}</span>`).join("")}</div>`;
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function inspect(kind, obj) {
  const empty = el("inspector-empty");
  const body = el("inspector-body");
  if (!obj) {
    empty.classList.remove("hidden");
    body.classList.add("hidden");
    return;
  }
  empty.classList.add("hidden");
  body.classList.remove("hidden");
  if (kind === "node") {
    const portList = (obj.ports || []).map((p) => p.display || `${p.proto}/${p.port}`).filter(Boolean);
    const gps = obj.gps ? `${obj.gps.lat.toFixed(5)}, ${obj.gps.lon.toFixed(5)}` : "—";
    body.innerHTML = `
      <h2>${escapeHtml(obj.label)}</h2>
      <dl class="kv">
        <dt>Kind</dt><dd>${escapeHtml(obj.kind)} · ${escapeHtml(obj.medium)}</dd>
        <dt>Roles</dt><dd>${escapeHtml((obj.roles || []).join(", ") || "—")}</dd>
        <dt>MACs</dt><dd>${escapeHtml((obj.macs || []).join(", ") || "—")}</dd>
        <dt>IPs</dt><dd>${escapeHtml((obj.ips || []).join(", ") || "—")}</dd>
        <dt>OUI manufacturer</dt><dd>${escapeHtml(obj.vendor || "—")}</dd>
        <dt>SSID</dt><dd>${escapeHtml((obj.ssids || []).join(", ") || "—")}</dd>
        <dt>Channel</dt><dd>${escapeHtml((obj.channels || []).join(", ") || "—")}</dd>
        <dt>Freq</dt><dd>${escapeHtml((obj.frequencies_mhz || []).map((f) => f + " MHz").join(", ") || "—")}</dd>
        <dt>Signal</dt><dd>${obj.signal_dbm == null ? "—" : obj.signal_dbm + " dBm"}</dd>
        <dt>Encrypt</dt><dd>${escapeHtml((obj.encryption || []).join(", ") || "—")}</dd>
        <dt>VLANs</dt><dd>${escapeHtml((obj.vlans || []).join(", ") || "—")}</dd>
        <dt>GPS</dt><dd>${escapeHtml(gps)}</dd>
      </dl>
      <h2>Ports &amp; services</h2>
      ${chips(obj.services)}
      ${chips(portList)}
      ${obj.routing && Object.keys(obj.routing).length ? `<pre>${escapeHtml(JSON.stringify(obj.routing, null, 2))}</pre>` : ""}
    `;
  } else {
    const portList = (obj.ports || []).map((p) => {
      const bits = [p.display || ""];
      if (p.sport != null && p.dport != null) bits.push(`src ${p.sport} → dst ${p.dport}`);
      return bits.filter(Boolean).join(" · ");
    });
    body.innerHTML = `
      <h2>${escapeHtml(obj.label || obj.kind)}</h2>
      <dl class="kv">
        <dt>Kind</dt><dd>${escapeHtml(obj.kind)} · ${escapeHtml(obj.medium)}</dd>
        <dt>From</dt><dd>${escapeHtml(obj.source)}</dd>
        <dt>To</dt><dd>${escapeHtml(obj.target)}</dd>
        <dt>VLANs</dt><dd>${escapeHtml((obj.vlans || []).join(", ") || "—")}</dd>
      </dl>
      <h2>Ports &amp; services</h2>
      ${chips(obj.services)}
      ${chips(portList)}
    `;
  }
}

function setBusy(on) {
  show("loading", on);
  show("empty", !on && !state.graph);
  show("error", false);
}

async function parseResponse(res) {
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = payload.detail || payload.error || res.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return payload;
}

function applyGraph(graph, title) {
  state.graph = graph;
  state.title = title || "Survey map";
  const n = graph.nodes?.length || 0;
  const e = graph.links?.length || 0;
  const services = new Set();
  for (const node of graph.nodes || []) (node.services || []).forEach((s) => services.add(s));
  setStatus(`${n} nodes · ${e} links · ${services.size} services`);
  ["btn-drawio", "btn-vsdx", "btn-vdx", "btn-report"].forEach((id) => {
    el(id).disabled = n === 0;
  });
  show("empty", n === 0);
  show("loading", false);
  show("error", false);
  renderMap();
}

function fail(err) {
  show("loading", false);
  show("empty", !state.graph);
  show("error", true);
  el("error-msg").textContent = err.message || String(err);
  setStatus("Parse failed");
}

async function loadSample(id, name) {
  setBusy(true);
  try {
    const graph = await parseResponse(await fetch(`/api/samples/${id}/graph`));
    applyGraph(graph, name);
    document.querySelectorAll("#sample-list button").forEach((b) => {
      b.classList.toggle("active", b.dataset.id === id);
    });
  } catch (err) {
    fail(err);
  }
}

async function loadFile(file) {
  setBusy(true);
  const body = new FormData();
  body.append("file", file);
  try {
    const graph = await parseResponse(
      await fetch("/api/parse", { method: "POST", body })
    );
    applyGraph(graph, file.name);
  } catch (err) {
    fail(err);
  }
}

async function exportKind(kind, filename) {
  if (!state.graph) return;
  const res = await fetch(`/api/export/${kind}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...state.graph, title: state.title }),
  });
  if (!res.ok) {
    fail(new Error("Export failed"));
    return;
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

let activeDevice = null;

function showToast() {
  const toast = el("copy-toast");
  toast.classList.remove("hidden");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.add("hidden"), 1400);
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const area = document.createElement("textarea");
    area.value = text;
    document.body.appendChild(area);
    area.select();
    document.execCommand("copy");
    area.remove();
  }
  showToast();
}

function closeDeviceDialog() {
  el("device-modal").classList.add("hidden");
  activeDevice = null;
}

async function openDeviceDialog(node) {
  if (!state.graph || !node) return;
  activeDevice = node;
  el("device-title").textContent = node.label || node.id;
  el("device-fields").innerHTML = "<p class='hint'>Loading extracted properties…</p>";
  el("device-modal").classList.remove("hidden");
  try {
    const payload = await parseResponse(
      await fetch("/api/device/properties", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...state.graph, title: state.title, node_id: node.id }),
      })
    );
    activeDevice = { ...node, properties: payload.properties, text: payload.properties };
    const fields = el("device-fields");
    fields.innerHTML = "";
    for (const row of payload.properties) {
      const wrap = document.createElement("div");
      wrap.className = "field-row";
      const value = row.value || "—";
      wrap.innerHTML = `<dt>${escapeHtml(row.name)}</dt><dd></dd>`;
      wrap.querySelector("dd").textContent = value;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn ghost copy-one";
      btn.textContent = "Copy";
      btn.addEventListener("click", () => copyText(`${row.name}: ${value}`));
      wrap.appendChild(btn);
      fields.appendChild(wrap);
    }
  } catch (err) {
    el("device-fields").innerHTML = `<p class="hint">${escapeHtml(err.message || String(err))}</p>`;
  }
}

async function exportDevice(fmt) {
  if (!state.graph || !activeDevice) return;
  const res = await fetch(`/api/export/device/${fmt}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...state.graph, title: state.title, node_id: activeDevice.id }),
  });
  if (!res.ok) {
    fail(new Error("Device export failed"));
    return;
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  const stem = (activeDevice.label || "device").replace(/[^A-Za-z0-9._-]+/g, "-");
  a.href = url;
  a.download = `${stem}-device.${fmt}`;
  a.click();
  URL.revokeObjectURL(url);
}

async function copyAllDevice() {
  if (!state.graph || !activeDevice) return;
  const res = await fetch("/api/export/device/txt", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...state.graph, title: state.title, node_id: activeDevice.id }),
  });
  if (!res.ok) {
    fail(new Error("Could not copy device details"));
    return;
  }
  await copyText(await res.text());
}

async function init() {
  const samples = await parseResponse(await fetch("/api/samples"));
  const list = el("sample-list");
  list.innerHTML = "";
  for (const s of samples) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.dataset.id = s.id;
    btn.innerHTML = `${escapeHtml(s.name)}<small>${escapeHtml(s.summary)}</small>`;
    btn.addEventListener("click", () => loadSample(s.id, s.name));
    list.appendChild(btn);
  }

  el("file").addEventListener("change", (e) => {
    const file = e.target.files?.[0];
    if (file) loadFile(file);
  });
  const drop = el("dropzone");
  ["dragenter", "dragover"].forEach((ev) =>
    drop.addEventListener(ev, (e) => {
      e.preventDefault();
      drop.classList.add("drag");
    })
  );
  ["dragleave", "drop"].forEach((ev) =>
    drop.addEventListener(ev, (e) => {
      e.preventDefault();
      drop.classList.remove("drag");
    })
  );
  drop.addEventListener("drop", (e) => {
    const file = e.dataTransfer.files?.[0];
    if (file) loadFile(file);
  });

  document.querySelectorAll("[data-filter]").forEach((box) => {
    box.addEventListener("change", () => {
      state.filters[box.dataset.filter] = box.checked;
      if (state.graph) renderMap();
    });
  });
  el("btn-drawio").addEventListener("click", () => exportKind("drawio", "survey-map.drawio"));
  el("btn-vsdx").addEventListener("click", () => exportKind("vsdx", "survey-map.vsdx"));
  el("btn-vdx").addEventListener("click", () => exportKind("vdx", "survey-map.vdx"));
  el("btn-report").addEventListener("click", () => exportKind("report.pdf", "survey-map-report.pdf"));
  el("btn-dismiss").addEventListener("click", () => show("error", false));
  el("btn-menu").addEventListener("click", () => el("sidebar").classList.toggle("open"));
  el("device-close").addEventListener("click", closeDeviceDialog);
  el("device-modal").addEventListener("click", (e) => {
    if (e.target === el("device-modal")) closeDeviceDialog();
  });
  el("copy-all").addEventListener("click", copyAllDevice);
  document.querySelectorAll("[data-device-export]").forEach((btn) => {
    btn.addEventListener("click", () => exportDevice(btn.dataset.deviceExport));
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeDeviceDialog();
  });

  await loadSample("campus-all", "Campus survey (combined)");
}

init().catch((err) => fail(err));
