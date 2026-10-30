const state = {
  config: null,
  defaults: null,
  selection: null, // {category, name} or {file}
  viewer: null,
  result: null,
  annotationIds: [],
};
const el = (id) => document.getElementById(id);
const api = (path) => `/api${path}`;
const CDN = "https://cdn.cloud.pspdfkit.com/pspdfkit-web@1.22.0/";

async function boot() {
  bindUi();
  try {
    const [config, templates] = await Promise.all([
      fetch(api("/config")).then((r) => r.json()),
      fetch(api("/templates")).then((r) => r.json()),
    ]);
    state.config = config;
    state.defaults = templates;
    renderSamples();
    renderTemplateOptions(templates.templates);
    renderModels(config);
    el("templates-json").value = JSON.stringify(templates.templates, null, 2);
    if (!config.openai_configured) setBanner("OPENAI_API_KEY is not set: classification works, attribute extraction will fail.");
  } catch (error) {
    setBanner(`Backend not reachable: ${error.message}`);
  }
}

function bindUi() {
  el("theme-toggle").addEventListener("click", () => {
    const dark = document.documentElement.dataset.theme !== "dark";
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    el("theme-toggle").textContent = dark ? "Light" : "Dark";
    if (state.viewer) state.viewer.setViewState((v) => v.set("theme", dark ? NutrientViewer.Theme.DARK : NutrientViewer.Theme.LIGHT));
  });
  el("upload").addEventListener("change", (event) => {
    const file = event.target.files[0];
    if (!file) return;
    select({ file });
    showDocument(URL.createObjectURL(file), file.name, file.name);
  });
  el("edit-templates").addEventListener("click", () => {
    const editor = el("template-editor");
    editor.hidden = !editor.hidden;
  });
  el("reset-templates").addEventListener("click", () => {
    el("templates-json").value = JSON.stringify(state.defaults.templates, null, 2);
    renderTemplateOptions(state.defaults.templates);
  });
  el("templates-json").addEventListener("change", () => {
    try { renderTemplateOptions(JSON.parse(el("templates-json").value)); setBanner(""); }
    catch (error) { setBanner(`Template JSON is invalid: ${error.message}`); }
  });
  el("process").addEventListener("click", process);
  el("download").addEventListener("click", downloadAnnotated);
  el("copy-json").addEventListener("click", () => navigator.clipboard.writeText(el("json").textContent));
  document.querySelectorAll(".tabs button").forEach((button) =>
    button.addEventListener("click", () => {
      document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("active", b === button));
      el("view-attributes").hidden = button.dataset.view !== "attributes";
      el("view-json").hidden = button.dataset.view !== "json";
    })
  );
}

function setBanner(message) {
  el("banner").textContent = message;
  el("banner").hidden = !message;
}

function renderSamples() {
  for (const [category, names] of Object.entries(state.config.samples)) {
    const list = el(`samples-${category}`);
    list.innerHTML = "";
    for (const name of names) {
      const item = document.createElement("li");
      item.innerHTML = `<span>${name.replace(/\.[^.]+$/, "")}</span><span class="ext">${name.split(".").pop()}</span>`;
      item.addEventListener("click", () => {
        select({ category, name });
        list.parentElement.parentElement.querySelectorAll("li").forEach((li) => li.classList.toggle("active", li === item));
        const url = api(`/sample/${category}/${encodeURIComponent(name)}`);
        showDocument(url, name, name);
      });
      list.appendChild(item);
    }
  }
}

function renderTemplateOptions(templates) {
  const select = el("template");
  const current = select.value;
  select.innerHTML = `<option value="auto">Auto-detect (classification)</option>`;
  for (const [id, template] of Object.entries(templates)) {
    const option = document.createElement("option");
    option.value = id;
    option.textContent = `${template.label || id} (${(template.attributes || []).length} attributes)`;
    select.appendChild(option);
  }
  select.value = [...select.options].some((o) => o.value === current) ? current : "auto";
}

function renderModels(config) {
  const select = el("model");
  select.innerHTML = "";
  for (const model of config.models) {
    const option = document.createElement("option");
    const price = config.pricing[model];
    option.value = model;
    option.textContent = model.startsWith("ollama:")
      ? `${model.slice(7)} via Ollama, local (no data leaves the machine)`
      : `${model} ($${price.input}/M in, $${price.output}/M out)`;
    select.appendChild(option);
  }
  select.value = config.model;
}

function select(selection) {
  state.selection = selection;
  state.result = null;
  el("selected").textContent = selection.file ? `Upload: ${selection.file.name}` : `${selection.category}/${selection.name}`;
  el("process").disabled = false;
  el("classification").hidden = true;
  el("usage").hidden = true;
  el("download").hidden = true;
  el("attributes").innerHTML = `<p class="hint">Ready. Click "Process document".</p>`;
  el("json").textContent = "";
}

async function showDocument(url, label, name) {
  // Unload whatever is mounted, including a viewer whose load failed.
  try { NutrientViewer.unload(el("viewer")); } catch (_) { /* nothing mounted */ }
  state.viewer = null;
  state.annotationIds = [];
  const dark = document.documentElement.dataset.theme === "dark";
  const isPdf = /\.pdf$/i.test(name);
  el("viewer-note").textContent = isPdf ? label : `${label} (Office preview; the processed PDF replaces it after conversion)`;
  try {
    state.viewer = await NutrientViewer.load({
      container: "#viewer",
      document: url,
      licenseKey: state.config?.web_sdk_license_key || undefined,
      baseUrl: CDN,
      theme: dark ? NutrientViewer.Theme.DARK : NutrientViewer.Theme.LIGHT,
      toolbarItems: [{ type: "sidebar-thumbnails" }, { type: "pager" }, { type: "zoom-out" }, { type: "zoom-in" }, { type: "zoom-mode" }, { type: "spacer" }, { type: "search" }],
    });
  } catch (error) {
    el("viewer-note").textContent = `Viewer could not open ${label}: ${error.message || error}`;
  }
}

function step(name, status) {
  const item = el("progress").querySelector(`[data-step="${name}"]`);
  item.className = status;
}

async function process() {
  if (!state.selection) return;
  const form = new FormData();
  form.append("template", el("template").value);
  form.append("model", el("model").value);
  form.append("engine", el("engine").value);
  const edited = el("templates-json").value;
  if (edited.trim() && edited !== JSON.stringify(state.defaults.templates, null, 2)) form.append("templates_json", edited);
  if (state.selection.file) form.append("file", state.selection.file);
  else { form.append("category", state.selection.category); form.append("sample", state.selection.name); }

  el("process").disabled = true;
  el("progress").hidden = false;
  const isPdf = state.selection.file ? /\.pdf$/i.test(state.selection.file.name) : /\.pdf$/i.test(state.selection.name);
  ["convert", "parse", "classify", "extract", "annotate"].forEach((s) => step(s, ""));
  step("convert", isPdf ? "skipped" : "active");
  if (el("template").value !== "auto") step("classify", "skipped");
  const timer = setTimeout(() => { if (!isPdf) step("convert", "done"); step("parse", "active"); }, 1200);
  const timer2 = setTimeout(() => { step("parse", "done"); step(el("template").value === "auto" ? "classify" : "extract", "active"); }, 9000);
  const timer3 = setTimeout(() => { if (el("template").value === "auto") { step("classify", "done"); step("extract", "active"); } }, 16000);
  const started = performance.now();
  try {
    const response = await fetch(api("/process"), { method: "POST", body: form });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
    [timer, timer2, timer3].forEach(clearTimeout);
    ["convert", "parse", "classify", "extract"].forEach((s) => { if (el("progress").querySelector(`[data-step="${s}"]`).className !== "skipped") step(s, "done"); });
    step("annotate", "active");
    payload.client_round_trip_ms = Math.round(performance.now() - started);
    state.result = payload;
    render(payload);
    await showDocument(payload.document.pdf_url, payload.document.name, "x.pdf");
    await drawAnnotations(payload);
    step("annotate", "done");
    el("download").hidden = false;
  } catch (error) {
    [timer, timer2, timer3].forEach(clearTimeout);
    setBanner(`Processing failed: ${error.message}`);
  } finally {
    el("process").disabled = false;
  }
}

function pct(value) {
  return value == null ? "" : `${Math.round(value * 100)}%`;
}

function render(payload) {
  setBanner(payload.note || "");
  const c = payload.classification;
  const box = el("classification");
  if (c) {
    const conf = c.confidence ?? 0;
    const klass = conf >= 0.8 ? "ok" : conf >= 0.5 ? "warn" : "bad";
    box.innerHTML = `<h2>Classification</h2>
      <div class="class-row"><span class="pill ${klass}">${c.predictedLabel}</span><span>${pct(conf)} confidence</span></div>
      <div class="scores">${(c.predictions || []).map((p) => `${p.label}: ${pct(p.probability)}`).join(" · ")}</div>
      <p class="hint">Template applied: <strong>${payload.template ? payload.template.label : "none"}</strong></p>`;
  } else {
    box.innerHTML = `<h2>Classification</h2><div class="class-row"><span class="pill neutral">skipped</span><span>Template forced: <strong>${payload.template ? payload.template.label : "none"}</strong></span></div>`;
  }
  box.hidden = false;

  const rows = payload.attributes.map((a, index) => {
    const g = a.confidence.grounding;
    const derived = g != null && g < 0.3 && a.citation;
    const value = a.value == null ? `<span class="null">not found</span>` : typeof a.value === "boolean" ? (a.value ? "true" : "false") : String(a.value);
    const score = g == null ? "" : pct(g);
    const scoreClass = derived ? "derived" : g != null && g < 0.7 ? "low" : "";
    return `<tr class="${a.citation ? "clickable" : ""}" data-index="${index}">
      <td class="name">${a.name}</td>
      <td class="value">${value}</td>
      <td class="score ${scoreClass}" title="Grounding: how literally the value is supported by the text at the cited location">${score}</td>
      <td class="score">${a.citation ? `p.${a.citation.page}` : ""}</td>
    </tr>`;
  });
  el("attributes").innerHTML = `<h2>Attributes (${payload.attributes.length})</h2>
    <table><thead><tr><th>Attribute</th><th>Value</th><th>Ground.</th><th>Page</th></tr></thead><tbody>${rows.join("")}</tbody></table>
    <p class="legend">Grounding is the Nutrient confidence that the value is literally present at the cited location. Normalised or inferred values (enums, booleans, numbers without currency) score low by design and still carry a citation.</p>`;
  el("attributes").querySelectorAll("tr.clickable").forEach((row) =>
    row.addEventListener("click", () => {
      el("attributes").querySelectorAll("tr").forEach((r) => r.classList.toggle("focused", r === row));
      jumpTo(payload.attributes[Number(row.dataset.index)]);
    })
  );

  const u = payload.usage || {};
  const t = payload.timings_ms || {};
  el("usage").innerHTML = `<h2>Cost and timing</h2>
    <dl class="metrics">
      <dt>LLM model</dt><dd>${u.model || ""}</dd>
      <dt>LLM calls</dt><dd>${u.calls ?? 0}</dd>
      <dt>Input tokens</dt><dd>${(u.input_tokens ?? 0).toLocaleString()}</dd>
      <dt>Output tokens</dt><dd>${(u.output_tokens ?? 0).toLocaleString()}</dd>
      <dt>LLM cost (list price)</dt><dd>$${(u.cost_usd ?? 0).toFixed(5)}</dd>
      <dt>Convert to PDF</dt><dd>${t.convert ?? 0} ms</dd>
      <dt>Parsing engine</dt><dd>${payload.engine || ""}</dd>
      <dt>Parse (local)</dt><dd>${t.parse ?? 0} ms</dd>
      <dt>Classify (local)</dt><dd>${t.classify ?? 0} ms</dd>
      <dt>Extract (LLM)</dt><dd>${t.extract ?? 0} ms</dd>
      <dt>Round trip</dt><dd>${payload.client_round_trip_ms} ms</dd>
    </dl>
    <p class="legend">Parsing and classification run locally in the Nutrient SDK. Only the extraction step sends text to the LLM, so tokens are measured per document.</p>`;
  el("usage").hidden = false;

  const { raw, client_round_trip_ms, highlights, ...ingest } = payload;
  el("json").textContent = JSON.stringify(ingest, null, 2);
}

function scaleFor(pageIndex) {
  const page = (state.result?.document.pages || []).find((p) => p.page === pageIndex + 1);
  const viewerPage = state.viewer.pageInfoForIndex(pageIndex);
  if (!page || !viewerPage || !page.width || !page.height) return { x: 1, y: 1 };
  return { x: viewerPage.width / page.width, y: viewerPage.height / page.height };
}

function rectFor(citation) {
  const pageIndex = (citation.page || 1) - 1;
  const s = scaleFor(pageIndex);
  const b = citation.bbox;
  return { pageIndex, rect: new NutrientViewer.Geometry.Rect({ left: b.x * s.x, top: b.y * s.y, width: b.width * s.x, height: b.height * s.y }) };
}

async function drawAnnotations(payload) {
  if (!state.viewer) return;
  const annotations = payload.attributes.filter((a) => a.citation).map((a) => {
    const { pageIndex, rect } = rectFor(a.citation);
    return new NutrientViewer.Annotations.RectangleAnnotation({
      pageIndex,
      boundingBox: rect,
      strokeColor: new NutrientViewer.Color({ r: 15, g: 106, b: 156 }),
      strokeWidth: 1.5,
      fillColor: null,
      customData: { attribute: a.name, value: a.value, grounding: a.confidence.grounding },
    });
  });
  if (!annotations.length) return;
  const created = await state.viewer.create(annotations);
  state.annotationIds = created.map((a) => a.id);
}

async function jumpTo(attribute) {
  if (!attribute?.citation || !state.viewer) return;
  const { pageIndex, rect } = rectFor(attribute.citation);
  await state.viewer.setViewState((v) => v.set("currentPageIndex", pageIndex));
  state.viewer.jumpToRect(pageIndex, rect);
}

async function downloadAnnotated() {
  if (!state.viewer) return;
  const buffer = await state.viewer.exportPDF();
  const blob = new Blob([buffer], { type: "application/pdf" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = (state.result?.document.name || "document").replace(/\.[^.]+$/, "") + "-annotated.pdf";
  link.click();
}

boot();
