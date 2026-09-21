/* NetSeer preview — cytoscape map, samples, upload, export. */
const HIDDEN_SAMPLES_KEY = "netseer.hiddenSamples";
const ZOOM_MIN = 0.2;
const ZOOM_MAX = 4;

const state = {
  graph: null,
  title: "NetSeer map",
  cy: null,
  catalog: [],
  surveys: [],
  activeId: null,
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

const META_KEY = "netseer.deviceMeta.v1";

function allDeviceMeta() {
  try {
    const raw = JSON.parse(localStorage.getItem(META_KEY) || "{}");
    return raw && typeof raw === "object" ? raw : {};
  } catch {
    return {};
  }
}

function metaStorageKey(nodeId) {
  return `${state.activeId || "map"}::${nodeId}`;
}

function getDeviceMeta(nodeId) {
  return allDeviceMeta()[metaStorageKey(nodeId)] || {};
}

function setDeviceMeta(nodeId, patch) {
  const all = allDeviceMeta();
  const key = metaStorageKey(nodeId);
  all[key] = { ...all[key], ...patch };
  localStorage.setItem(META_KEY, JSON.stringify(all));
}

function inferredName(node) {
  return node.inferred_type || node.label || "Host";
}

function displayName(node) {
  const meta = getDeviceMeta(node.id);
  const name = (meta.name || "").trim();
  return name || inferredName(node);
}

function nodeLabel(node) {
  const meta = getDeviceMeta(node.id);
  const name = displayName(node);
  const extra = (meta.extra || "").trim();
  return extra ? `${name}\n${extra}` : name;
}

function macRoleValue(addrs) {
  if (addrs && addrs.length) return addrs.join(", ");
  return "not present";
}

function graphWithUserFields() {
  const nodes = (state.graph?.nodes || []).map((n) => {
    const meta = getDeviceMeta(n.id);
    return {
      ...n,
      label: displayName(n),
      inferred_type: inferredName(n),
      caption: (meta.extra || "").trim(),
      notes: (meta.notes || "").trim(),
    };
  });
  return { ...state.graph, title: state.title, nodes };
}

function refreshNodeLabel(node) {
  if (state.cy) {
    const cyNode = state.cy.getElementById(node.id);
    if (cyNode && cyNode.length) cyNode.data("label", nodeLabel(node));
  }
  if (activeDevice && activeDevice.id === node.id) {
    el("device-title").textContent = displayName(node);
  }
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
    minZoom: ZOOM_MIN,
    maxZoom: ZOOM_MAX,
    wheelSensitivity: 0.35,
    userZoomingEnabled: true,
    userPanningEnabled: true,
    style: [
      {
        selector: "node",
        style: {
          label: "data(label)",
          "text-wrap": "wrap",
          "text-max-width": 140,
          "font-size": 11,
          color: "#e8eef8",
          "text-valign": "center",
          "background-color": "#0f172a",
          "border-width": 2,
          "border-color": "data(color)",
          width: 92,
          height: 42,
          shape: "roundrectangle",
        },
      },
      {
        selector: 'node[kind = "ap"]',
        style: { shape: "hexagon", width: 88, height: 56 },
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
  state.cy.on("zoom", syncZoomUi);
  syncZoomUi();
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
      <h2>${escapeHtml(displayName(obj))}</h2>
      <dl class="kv">
        <dt>Type</dt><dd>${escapeHtml(inferredName(obj))}</dd>
        <dt>Kind</dt><dd>${escapeHtml(obj.kind)} · ${escapeHtml(obj.medium)}</dd>
        <dt>Roles</dt><dd>${escapeHtml((obj.roles || []).join(", ") || "—")}</dd>
        <dt>TX MAC</dt><dd>${escapeHtml(macRoleValue(obj.mac_tx))}</dd>
        <dt>RX MAC</dt><dd>${escapeHtml(macRoleValue(obj.mac_rx))}</dd>
        <dt>DA MAC</dt><dd>${escapeHtml(macRoleValue(obj.mac_da))}</dd>
        <dt>RA MAC</dt><dd>${escapeHtml(macRoleValue(obj.mac_ra))}</dd>
        ${!(obj.mac_tx || []).length && !(obj.mac_rx || []).length && !(obj.mac_da || []).length && !(obj.mac_ra || []).length && (obj.macs || []).length ? `<dt>MAC</dt><dd>${escapeHtml(obj.macs.join(", "))}</dd>` : ""}
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

function applyGraph(graph, title, surveyId) {
  state.graph = graph;
  state.title = title || "NetSeer map";
  if (surveyId) state.activeId = surveyId;
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
  renderSurveyList();
}

function clearMap() {
  if (state.cy) {
    state.cy.destroy();
    state.cy = null;
  }
  state.graph = null;
  state.title = "NetSeer map";
  state.activeId = null;
  ["btn-drawio", "btn-vsdx", "btn-vdx", "btn-report"].forEach((id) => {
    el(id).disabled = true;
  });
  inspect(null, null);
  closeDeviceDialog();
  show("empty", true);
  show("loading", false);
  show("error", false);
  setStatus("No survey loaded");
  syncZoomUi();
  renderSurveyList();
}

function fail(err) {
  show("loading", false);
  show("empty", !state.graph);
  show("error", true);
  el("error-msg").textContent = err.message || String(err);
  setStatus("Parse failed");
}

function hiddenSampleIds() {
  try {
    const raw = JSON.parse(localStorage.getItem(HIDDEN_SAMPLES_KEY) || "[]");
    return Array.isArray(raw) ? raw.filter((id) => typeof id === "string") : [];
  } catch {
    return [];
  }
}

function saveHiddenSampleIds(ids) {
  localStorage.setItem(HIDDEN_SAMPLES_KEY, JSON.stringify(ids));
}

function sampleToSurvey(sample) {
  return {
    id: sample.id,
    kind: "sample",
    name: sample.name,
    summary: sample.summary,
  };
}

function renderSurveyList() {
  const list = el("sample-list");
  list.innerHTML = "";
  const hidden = hiddenSampleIds();
  el("survey-empty").classList.toggle("hidden", state.surveys.length > 0);
  el("btn-restore-samples").classList.toggle("hidden", hidden.length === 0);
  for (const item of state.surveys) {
    const row = document.createElement("li");
    row.className = "survey-item";
    const load = document.createElement("button");
    load.type = "button";
    load.className = "survey-load";
    if (item.id === state.activeId) load.classList.add("active");
    load.dataset.id = item.id;
    const kicker = item.kind === "upload" ? "Uploaded capture" : item.summary;
    load.innerHTML = `${escapeHtml(item.name)}<small>${escapeHtml(kicker)}</small>`;
    load.addEventListener("click", () => selectSurvey(item.id));
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "btn survey-remove";
    remove.textContent = "Remove";
    remove.setAttribute("aria-label", `Remove ${item.name}`);
    remove.addEventListener("click", (evt) => {
      evt.stopPropagation();
      removeSurvey(item.id);
    });
    row.append(load, remove);
    list.appendChild(row);
  }
}

async function selectSurvey(id) {
  const item = state.surveys.find((s) => s.id === id);
  if (!item) return;
  if (item.kind === "upload") {
    applyGraph(item.graph, item.name, item.id);
    return;
  }
  setBusy(true);
  try {
    const graph = await parseResponse(await fetch(`/api/samples/${item.id}/graph`));
    applyGraph(graph, item.name, item.id);
  } catch (err) {
    fail(err);
  }
}

function removeSurvey(id) {
  const item = state.surveys.find((s) => s.id === id);
  if (!item) return;
  const idx = state.surveys.findIndex((s) => s.id === id);
  state.surveys = state.surveys.filter((s) => s.id !== id);
  if (item.kind === "sample") {
    const hidden = hiddenSampleIds();
    if (!hidden.includes(item.id)) {
      hidden.push(item.id);
      saveHiddenSampleIds(hidden);
    }
  }
  if (state.activeId !== id) {
    renderSurveyList();
    return;
  }
  closeDeviceDialog();
  const next = state.surveys[idx] || state.surveys[idx - 1] || state.surveys[0];
  if (next) selectSurvey(next.id);
  else clearMap();
}

function restoreBundledSamples() {
  saveHiddenSampleIds([]);
  const present = new Set(state.surveys.map((s) => s.id));
  for (const sample of state.catalog) {
    if (!present.has(sample.id)) state.surveys.push(sampleToSurvey(sample));
  }
  const uploads = state.surveys.filter((s) => s.kind === "upload");
  const samples = state.catalog
    .map((sample) => state.surveys.find((s) => s.id === sample.id))
    .filter(Boolean);
  state.surveys = [...uploads, ...samples];
  renderSurveyList();
  if (!state.activeId && state.surveys.length) {
    const campus = state.surveys.find((s) => s.id === "campus-all") || state.surveys[0];
    selectSurvey(campus.id);
  }
}

async function loadFile(file) {
  setBusy(true);
  const body = new FormData();
  body.append("file", file);
  try {
    const graph = await parseResponse(await fetch("/api/parse", { method: "POST", body }));
    const id = `upload:${file.name}`;
    const existing = state.surveys.findIndex((s) => s.id === id);
    const item = {
      id,
      kind: "upload",
      name: file.name,
      summary: "Uploaded capture",
      graph,
    };
    if (existing >= 0) state.surveys.splice(existing, 1, item);
    else state.surveys.unshift(item);
    applyGraph(graph, file.name, id);
  } catch (err) {
    fail(err);
  }
}

async function loadFiles(files) {
  for (const file of files) {
    if (file) await loadFile(file);
  }
}

function zoomPct() {
  if (!state.cy) return 100;
  return Math.round(state.cy.zoom() * 100);
}

function syncZoomUi() {
  const slider = el("zoom-slider");
  const label = el("zoom-pct");
  const fit = el("zoom-fit");
  if (!slider || !label) return;
  const on = Boolean(state.cy);
  slider.disabled = !on;
  if (fit) fit.disabled = !on;
  const pct = Math.min(400, Math.max(20, zoomPct()));
  if (document.activeElement !== slider) slider.value = String(pct);
  label.textContent = `${zoomPct()}%`;
}

function applyZoomPct(pct) {
  if (!state.cy) return;
  const level = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, Number(pct) / 100));
  const renderedPosition = { x: state.cy.width() / 2, y: state.cy.height() / 2 };
  state.cy.zoom({ level, renderedPosition });
  syncZoomUi();
}

async function exportKind(kind, filename) {
  if (!state.graph) return;
  const res = await fetch(`/api/export/${kind}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(graphWithUserFields()),
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
  fillLabelEditors(node);
  el("device-fields").innerHTML = "<p class='hint'>Loading extracted properties…</p>";
  el("device-modal").classList.remove("hidden");
  try {
    const payload = await parseResponse(
      await fetch("/api/device/properties", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...graphWithUserFields(), node_id: node.id }),
      })
    );
    activeDevice = { ...node, properties: payload.properties, text: payload.properties };
    const fields = el("device-fields");
    fields.innerHTML = "";
    const skip = new Set(["label", "caption", "notes", "inferred_type"]);
    for (const row of payload.properties) {
      if (skip.has(row.key)) continue;
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

function fillLabelEditors(node) {
  const meta = getDeviceMeta(node.id);
  el("device-title").textContent = displayName(node);
  el("device-name").value = displayName(node);
  el("device-extra").value = meta.extra || "";
  el("device-notes").value = meta.notes || "";
  el("device-inferred").textContent = inferredName(node);
}

function saveActiveMeta(patch) {
  if (!activeDevice) return;
  setDeviceMeta(activeDevice.id, patch);
  refreshNodeLabel(activeDevice);
}

function setAllLayers(on) {
  document.querySelectorAll("[data-filter]").forEach((box) => {
    box.checked = on;
    state.filters[box.dataset.filter] = on;
  });
  if (state.graph) renderMap();
}

async function exportDevice(fmt) {
  if (!state.graph || !activeDevice) return;
  const res = await fetch(`/api/export/device/${fmt}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...graphWithUserFields(), node_id: activeDevice.id }),
  });
  if (!res.ok) {
    fail(new Error("Device export failed"));
    return;
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  const stem = (displayName(activeDevice) || "device").replace(/[^A-Za-z0-9._-]+/g, "-");
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
    body: JSON.stringify({ ...graphWithUserFields(), node_id: activeDevice.id }),
  });
  if (!res.ok) {
    fail(new Error("Could not copy device details"));
    return;
  }
  await copyText(await res.text());
}

async function init() {
  const samples = await parseResponse(await fetch("/api/samples"));
  state.catalog = samples;
  const hidden = new Set(hiddenSampleIds());
  state.surveys = samples.filter((s) => !hidden.has(s.id)).map(sampleToSurvey);
  renderSurveyList();
  syncZoomUi();

  el("file").addEventListener("change", (e) => {
    const files = [...(e.target.files || [])];
    e.target.value = "";
    if (files.length) loadFiles(files);
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
    const files = [...(e.dataTransfer.files || [])];
    if (files.length) loadFiles(files);
  });
  el("btn-restore-samples").addEventListener("click", restoreBundledSamples);
  el("btn-show-all").addEventListener("click", () => setAllLayers(true));
  el("btn-show-none").addEventListener("click", () => setAllLayers(false));
  el("device-name").addEventListener("input", (e) => saveActiveMeta({ name: e.target.value }));
  el("device-extra").addEventListener("input", (e) => saveActiveMeta({ extra: e.target.value }));
  el("device-notes").addEventListener("input", (e) => saveActiveMeta({ notes: e.target.value }));
  el("device-reset-name").addEventListener("click", () => {
    if (!activeDevice) return;
    saveActiveMeta({ name: "" });
    el("device-name").value = inferredName(activeDevice);
    refreshNodeLabel(activeDevice);
  });
  el("zoom-slider").addEventListener("input", (e) => applyZoomPct(e.target.value));
  el("zoom-fit").addEventListener("click", () => {
    if (!state.cy) return;
    state.cy.fit(undefined, 24);
    syncZoomUi();
  });

  document.querySelectorAll("[data-filter]").forEach((box) => {
    box.addEventListener("change", () => {
      state.filters[box.dataset.filter] = box.checked;
      if (state.graph) renderMap();
    });
  });
  el("btn-drawio").addEventListener("click", () => exportKind("drawio", "netseer-map.drawio"));
  el("btn-vsdx").addEventListener("click", () => exportKind("vsdx", "netseer-map.vsdx"));
  el("btn-vdx").addEventListener("click", () => exportKind("vdx", "netseer-map.vdx"));
  el("btn-report").addEventListener("click", () => exportKind("report.pdf", "netseer-map-report.pdf"));
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

  const first =
    state.surveys.find((s) => s.id === "campus-all") || state.surveys[0];
  if (first) await selectSurvey(first.id);
  else clearMap();
}

init().catch((err) => fail(err));
