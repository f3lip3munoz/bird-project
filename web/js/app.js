import { toCSV, parseCSV } from "./csv.js";
import { store, newId, idbGet, idbSet } from "./store.js";

// ---------- Constants ----------
const BEHAVIORS = ["Posado", "Alimentándose", "Volando", "Cantando", "Forrajeando", "Nidificando", "Nadando", "En bandada", "Cortejo", "Bañándose"];
const HABITATS = ["Bosque", "Matorral", "Pastizal", "Humedal", "Río / lago", "Costa", "Cordillera", "Desierto", "Campo", "Urbano", "Parque / jardín"];
const WEATHER = ["Despejado", "Parcial", "Nublado", "Lluvia", "Niebla", "Viento"];
const STATUS_LABEL = { confirmed: "Confirmada", tentative: "Tentativa", unidentified: "Sin identificar" };

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => (s == null ? "" : String(s)).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const norm = (s) => (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").trim();
const supportsFS = "showOpenFilePicker" in window;
const isStandalone = matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;

const fmtDay = new Intl.DateTimeFormat("es-CL", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
const fmtShort = new Intl.DateTimeFormat("es-CL", { day: "numeric", month: "short", year: "numeric" });
const fmtTime = (dt) => (dt || "").slice(11, 16);
const parseLocal = (s) => { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); };

function nowLocal() {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}
const todayKey = () => nowLocal().slice(0, 10);

function relTime(iso) {
  if (!iso) return "nunca";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "hace un momento";
  if (s < 3600) return `hace ${Math.round(s / 60)} min`;
  if (s < 86400) return `hace ${Math.round(s / 3600)} h`;
  const d = Math.round(s / 86400);
  return d === 1 ? "ayer" : `hace ${d} días`;
}

// ---------- Toast ----------
let toastTimer;
function toast(msg, action) {
  const t = $("#toast"), btn = $("#toastAction");
  $("#toastMsg").textContent = msg;
  btn.hidden = !action;
  if (action) { btn.textContent = action.label; btn.onclick = () => { t.classList.remove("show"); action.run(); }; }
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), action ? 6000 : 2600);
}

// ---------- Species list ----------
let SPECIES = [];
async function loadSpecies() {
  try {
    const res = await fetch("data/chile_birds.json");
    SPECIES = (await res.json()).map((x) => ({ ...x, nc: norm(x.c), ns: norm(x.s) }));
  } catch {
    toast("No se pudo cargar la lista de especies");
  }
}

function searchSpecies(q) {
  const nq = norm(q);
  if (!nq) return [];
  const starts = [], words = [], contains = [];
  for (const sp of SPECIES) {
    if (sp.nc.startsWith(nq) || sp.ns.startsWith(nq)) starts.push(sp);
    else if (sp.nc.includes(" " + nq) || sp.ns.includes(" " + nq)) words.push(sp);
    else if (sp.nc.includes(nq) || sp.ns.includes(nq)) contains.push(sp);
  }
  return [...starts, ...words, ...contains].slice(0, 60);
}

function highlight(text, q) {
  const nt = norm(text), nq = norm(q);
  const i = nq ? nt.indexOf(nq) : -1;
  if (i < 0) return esc(text);
  return esc(text.slice(0, i)) + "<mark>" + esc(text.slice(i, i + nq.length)) + "</mark>" + esc(text.slice(i + nq.length));
}

// ---------- Form state ----------
const form = {
  species: null, // {c, s}
  status: "confirmed",
  gps: null, // {lat, lon, acc}
  editingId: null,
};

const spInput = $("#f_species"), spList = $("#speciesList");
let spActive = -1, spItems = [];

function renderCombo() {
  const q = spInput.value;
  spItems = searchSpecies(q);
  const exact = SPECIES.some((s) => s.nc === norm(q));
  let html = spItems.map((sp, i) =>
    `<li role="option" id="sp-${i}" data-i="${i}"><span class="c"><span>${highlight(sp.c, q)}</span>${sp.t ? `<span class="note">${esc(sp.t)}</span>` : ""}</span><span class="s">${highlight(sp.s, q)}</span></li>`).join("");
  if (q.trim() && !exact) {
    html += `<li role="option" class="custom" data-custom="1"><span class="c">+ Usar «${esc(q.trim())}»</span><span class="s">Especie fuera de la lista</span></li>`;
  }
  if (q.trim() && !spItems.length && exact) html = "";
  spList.innerHTML = html;
  spActive = spItems.length ? 0 : -1;
  paintActive();
  spInput.setAttribute("aria-expanded", html ? "true" : "false");
}
function paintActive() {
  $$("li", spList).forEach((li, i) => li.classList.toggle("active", i === spActive));
  const el = spList.children[spActive];
  if (!el) return;
  // Scroll inside the list only (scrollIntoView would also scroll the page)
  if (el.offsetTop < spList.scrollTop) spList.scrollTop = el.offsetTop;
  else if (el.offsetTop + el.offsetHeight > spList.scrollTop + spList.clientHeight) spList.scrollTop = el.offsetTop + el.offsetHeight - spList.clientHeight;
  spInput.setAttribute("aria-activedescendant", el.id || "");
}
function closeCombo() { spList.innerHTML = ""; spInput.setAttribute("aria-expanded", "false"); }

function setSpecies(sp) {
  form.species = sp;
  spInput.value = sp ? sp.c : "";
  $("#speciesClear").hidden = !sp;
  spInput.title = sp?.s || "";
  if (sp && form.status === "unidentified") setStatus("confirmed");
  closeCombo();
}
function pickFromList(li) {
  if (!li) return;
  if (li.dataset.custom) setSpecies({ c: spInput.value.trim(), s: "" });
  else if (li.dataset.i != null) { const sp = spItems[+li.dataset.i]; setSpecies({ c: sp.c, s: sp.s }); }
}

spInput.addEventListener("input", () => { form.species = null; $("#speciesClear").hidden = !spInput.value; renderCombo(); });
spInput.addEventListener("focus", () => { if (spInput.value && !form.species) renderCombo(); });
spInput.addEventListener("keydown", (e) => {
  const n = spList.children.length;
  if (e.key === "ArrowDown" && n) { e.preventDefault(); spActive = (spActive + 1) % n; paintActive(); }
  else if (e.key === "ArrowUp" && n) { e.preventDefault(); spActive = (spActive - 1 + n) % n; paintActive(); }
  else if (e.key === "Enter" && n) { e.preventDefault(); pickFromList(spList.children[Math.max(spActive, 0)]); }
  else if (e.key === "Escape") closeCombo();
});
spList.addEventListener("pointerdown", (e) => { e.preventDefault(); pickFromList(e.target.closest("li")); });
spInput.addEventListener("blur", () => setTimeout(() => {
  closeCombo();
  // Free text typed but not picked: keep it as a custom species (or match exactly)
  if (!form.species && spInput.value.trim()) {
    const m = SPECIES.find((s) => s.nc === norm(spInput.value));
    setSpecies(m ? { c: m.c, s: m.s } : { c: spInput.value.trim(), s: "" });
  }
}, 120));
$("#speciesClear").addEventListener("click", () => { setSpecies(null); spInput.focus(); });

function renderRecent() {
  $("#recentSpecies").innerHTML = store.meta.recent.slice(0, 6)
    .map((r, i) => `<button type="button" data-i="${i}" title="${esc(r.s)}">${esc(r.c)}</button>`).join("");
}
$("#recentSpecies").addEventListener("click", (e) => {
  const b = e.target.closest("button"); if (!b) return;
  setSpecies({ ...store.meta.recent[+b.dataset.i] });
});

// Status
function setStatus(s) {
  form.status = s;
  $$("#statusSeg button").forEach((b) => { const on = b.dataset.s === s; b.classList.toggle("on", on); b.setAttribute("aria-checked", on); });
}
$("#statusSeg").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) setStatus(b.dataset.s); });

// Count stepper
$(".stepper").addEventListener("click", (e) => {
  const b = e.target.closest("button"); if (!b) return;
  const inp = $("#f_count");
  inp.value = Math.max(0, (parseInt(inp.value, 10) || (b.dataset.step > 0 ? 0 : 1)) + +b.dataset.step) || "";
});

// Chips
function renderChips(el, items) { el.innerHTML = items.map((x) => `<button type="button" aria-pressed="false">${esc(x)}</button>`).join(""); }
renderChips($("#behaviorChips"), BEHAVIORS);
renderChips($("#habitatChips"), HABITATS);
renderChips($("#weatherChips"), WEATHER);
$("#behaviorChips").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) toggleChip(b); });
$("#habitatChips").addEventListener("click", (e) => {
  const b = e.target.closest("button"); if (!b) return;
  $$("#habitatChips button").forEach((x) => x !== b && setChip(x, false));
  toggleChip(b);
});
$("#weatherChips").addEventListener("click", (e) => {
  const b = e.target.closest("button"); if (!b) return;
  const inp = $("#f_weather");
  const parts = inp.value.split(",").map((s) => s.trim()).filter(Boolean);
  const w = b.textContent.toLowerCase();
  if (!parts.map((p) => p.toLowerCase()).includes(w)) parts.unshift(w);
  inp.value = parts.join(", ");
});
function setChip(b, on) { b.classList.toggle("on", on); b.setAttribute("aria-pressed", on); }
function toggleChip(b) { setChip(b, !b.classList.contains("on")); }
const chipValues = (el) => $$("button.on", el).map((b) => b.textContent);
const setChipValues = (el, values) => $$("button", el).forEach((b) => setChip(b, values.includes(b.textContent)));

// GPS
function renderGps() {
  const btn = $("#gpsBtn");
  btn.classList.toggle("has", !!form.gps);
  $("#gpsClear").hidden = !form.gps;
  if (form.gps) {
    $("#gpsTitle").textContent = `${form.gps.lat}, ${form.gps.lon}`;
    $("#gpsSub").textContent = form.gps.acc ? `Precisión ±${form.gps.acc} m · toca para actualizar` : "Toca para actualizar";
  } else {
    $("#gpsTitle").textContent = "Capturar ubicación GPS";
    $("#gpsSub").textContent = "Opcional · funciona sin señal de datos";
  }
}
$("#gpsBtn").addEventListener("click", (e) => {
  if (e.target.closest("#gpsClear")) { form.gps = null; renderGps(); return; }
  if (!navigator.geolocation) return toast("Este dispositivo no tiene GPS");
  const btn = $("#gpsBtn");
  btn.classList.add("busy"); $("#gpsTitle").textContent = "Buscando ubicación…";
  navigator.geolocation.getCurrentPosition(
    (p) => {
      btn.classList.remove("busy");
      form.gps = { lat: p.coords.latitude.toFixed(6), lon: p.coords.longitude.toFixed(6), acc: Math.round(p.coords.accuracy) };
      renderGps(); toast("Ubicación capturada");
    },
    (err) => {
      btn.classList.remove("busy"); renderGps();
      toast(err.code === 1 ? "Permiso de ubicación denegado" : "No se pudo obtener la ubicación");
    },
    { enableHighAccuracy: true, timeout: 20000, maximumAge: 30000 },
  );
});

function renderPlaces() {
  $("#placesList").innerHTML = store.meta.places.map((p) => `<option value="${esc(p)}">`).join("");
}

// ---------- Save / edit ----------
function resetForm({ keepContext = false } = {}) {
  setSpecies(null);
  setStatus("confirmed");
  $("#f_count").value = "";
  setChipValues($("#behaviorChips"), []);
  $("#f_notes").value = ""; $("#f_photos").value = ""; $("#f_audio").value = "";
  $("#f_date").value = nowLocal();
  if (!keepContext) {
    $("#f_place").value = ""; $("#f_weather").value = "";
    setChipValues($("#habitatChips"), []);
    form.gps = null;
  }
  renderGps();
  form.editingId = null;
  $("#editingBar").hidden = true;
  $("#saveBtn span").textContent = "Guardar observación";
  $("#h-anotar").textContent = "Nueva observación";
}

function startEdit(id) {
  const o = store.observations.find((x) => x.observation_id === id);
  if (!o) return;
  location.hash = "#/anotar";
  form.editingId = id;
  setSpecies(o.species ? { c: o.species, s: o.scientific_name } : null);
  setStatus(o.status || "confirmed");
  $("#f_count").value = o.count || "";
  $("#f_date").value = o.datetime || nowLocal();
  $("#f_place").value = o.place || "";
  form.gps = o.latitude && o.longitude ? { lat: o.latitude, lon: o.longitude, acc: o.gps_accuracy_m } : null;
  renderGps();
  setChipValues($("#behaviorChips"), o.behavior.split(";").map((s) => s.trim()));
  setChipValues($("#habitatChips"), [o.habitat]);
  $("#f_weather").value = o.weather || "";
  $("#f_notes").value = o.notes || "";
  $("#f_photos").value = o.photo_files || "";
  $("#f_audio").value = o.audio_files || "";
  $("#editingBar").hidden = false;
  $("#saveBtn span").textContent = "Guardar cambios";
  $("#h-anotar").textContent = "Editar observación";
  scrollTo({ top: 0, behavior: "smooth" });
}
$("#cancelEdit").addEventListener("click", () => { resetForm(); location.hash = "#/registro"; });
$("#resetBtn").addEventListener("click", () => resetForm());

const cleanList = (s) => s.split(/[,;]+/).map((x) => x.trim()).filter(Boolean).join("; ");

$("#obsForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!store.current) {
    const ok = await askObserver();
    if (!ok) return;
  }
  if (!form.species && spInput.value.trim()) setSpecies({ c: spInput.value.trim(), s: "" });
  const status = form.species ? form.status : "unidentified";
  if (!form.species && !$("#f_notes").value.trim()) {
    toast("Elige una especie o describe el ave en Comentarios");
    spInput.focus();
    return;
  }
  const prev = form.editingId ? store.observations.find((o) => o.observation_id === form.editingId) : null;
  const now = new Date().toISOString();
  const rec = {
    observation_id: form.editingId || newId(),
    observer: prev?.observer || store.current,
    datetime: $("#f_date").value || nowLocal(),
    place: $("#f_place").value.trim(),
    latitude: form.gps?.lat || "", longitude: form.gps?.lon || "", gps_accuracy_m: form.gps?.acc ?? "",
    species: form.species?.c || "", scientific_name: form.species?.s || "",
    status,
    count: $("#f_count").value.trim(),
    behavior: chipValues($("#behaviorChips")).join("; "),
    habitat: chipValues($("#habitatChips"))[0] || "",
    weather: $("#f_weather").value.trim(),
    notes: $("#f_notes").value.trim(),
    photo_files: cleanList($("#f_photos").value),
    audio_files: cleanList($("#f_audio").value),
    id_source: prev?.id_source || "manual",
    id_confidence: prev?.id_confidence || "",
    review_flag: status === "confirmed" ? "0" : "1",
    created_at: prev?.created_at || now,
    updated_at: now,
  };
  if (!store.upsert(rec)) { toast("⚠ No se pudo guardar: el almacenamiento está lleno"); return; }
  requestPersistence();
  await writeLinked();
  const wasEditing = !!form.editingId;
  resetForm({ keepContext: !wasEditing });
  renderAll();
  if (wasEditing) { toast("Cambios guardados"); location.hash = "#/registro"; }
  else {
    toast(`Guardado · ${rec.species || "Sin identificar"}`, { label: "Deshacer", run: () => removeObs(rec.observation_id, false) });
    scrollTo({ top: 0, behavior: "smooth" });
  }
});

async function removeObs(id, withUndo = true) {
  const gone = store.remove(id);
  if (!gone) return;
  await writeLinked();
  renderAll();
  if (withUndo) toast(`Eliminada · ${gone.species || "Sin identificar"}`, { label: "Deshacer", run: async () => { store.upsert(gone); await writeLinked(); renderAll(); } });
}

// ---------- Observers ----------
function renderObserver() {
  const chip = $("#observerChip");
  $("#observerName").textContent = store.current || "¿Quién observa?";
  chip.classList.toggle("empty", !store.current);
  $("#observerList").innerHTML = store.observers.length
    ? store.observers.map((o) => `<div class="row ${o === store.current ? "cur" : ""}"><span>${esc(o)}</span>
        ${o !== store.current ? `<button type="button" class="link" data-use="${esc(o)}">Usar</button>` : ""}
        <button type="button" class="icon-btn danger" data-rm="${esc(o)}" aria-label="Quitar ${esc(o)}"><svg><use href="#i-trash"/></svg></button></div>`).join("")
    : `<p class="muted">Aún no hay observadores registrados.</p>`;
}
function setObserver(name) {
  name = name.trim(); if (!name) return;
  if (!store.observers.includes(name)) store.observers.push(name);
  store.current = name; store.saveObservers(); renderObserver();
}
$("#observerList").addEventListener("click", (e) => {
  const u = e.target.closest("[data-use]"), r = e.target.closest("[data-rm]");
  if (u) setObserver(u.dataset.use);
  if (r) {
    store.observers = store.observers.filter((o) => o !== r.dataset.rm);
    if (store.current === r.dataset.rm) store.current = store.observers[0] || "";
    store.saveObservers(); renderObserver();
  }
});
$("#observerForm").addEventListener("submit", (e) => { e.preventDefault(); setObserver($("#newObserver").value); $("#newObserver").value = ""; });

// Resolves true when an observer is set. Driven by submit/click handlers rather than
// the dialog "close" event, which is not reliably dispatched in every browser.
let observerAsk = null, finishObserver = null;
function askObserver() {
  if (observerAsk) return observerAsk;
  const dlg = $("#observerDialog");
  $("#observerPick").innerHTML = store.observers.map((o) => `<button type="button" data-o="${esc(o)}">${esc(o)}</button>`).join("");
  $("#dlgObserver").value = "";
  dlg.showModal();
  if (!store.observers.length) $("#dlgObserver").focus();
  observerAsk = new Promise((resolve) => {
    finishObserver = (ok) => {
      finishObserver = null; observerAsk = null;
      if (dlg.open) dlg.close();
      resolve(ok && !!store.current);
    };
  });
  return observerAsk;
}
$("#observerPick").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-o]"); if (!b) return;
  setObserver(b.dataset.o); finishObserver?.(true);
});
$("#observerDialogForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const name = $("#dlgObserver").value.trim();
  if (!name && !store.current) { $("#dlgObserver").focus(); return; }
  if (name) setObserver(name);
  finishObserver?.(true);
});
$("#dlgCancel").addEventListener("click", () => finishObserver?.(false));
$("#observerDialog").addEventListener("cancel", () => finishObserver?.(false));
$("#observerDialog").addEventListener("close", () => finishObserver?.(false));
$("#observerChip").addEventListener("click", () => askObserver());

// ---------- Registro ----------
let regFilter = "all";
$("#regFilter").addEventListener("click", (e) => {
  const b = e.target.closest("button"); if (!b) return;
  regFilter = b.dataset.f;
  $$("#regFilter button").forEach((x) => x.classList.toggle("on", x === b));
  renderRegistro();
});
$("#regSearch").addEventListener("input", () => renderRegistro());

function obsCard(o, pendingIds) {
  const st = o.status || "unidentified";
  const meta = [];
  meta.push(`<span><svg><use href="#i-clock"/></svg>${esc(fmtTime(o.datetime))}</span>`);
  if (o.place) meta.push(`<span><svg><use href="#i-pin"/></svg>${esc(o.place)}</span>`);
  if (o.latitude && o.longitude) meta.push(`<span><a href="https://www.google.com/maps?q=${encodeURIComponent(o.latitude + "," + o.longitude)}" target="_blank" rel="noopener">mapa</a></span>`);
  if (o.observer) meta.push(`<span><svg><use href="#i-user"/></svg>${esc(o.observer)}</span>`);
  const pills = [];
  if (st !== "confirmed") pills.push(`<span class="pill status-${st}">${STATUS_LABEL[st]}</span>`);
  if (pendingIds.has(o.observation_id)) pills.push(`<span class="pill new">Sin exportar</span>`);
  if (o.habitat) pills.push(`<span class="pill">${esc(o.habitat)}</span>`);
  o.behavior.split(";").map((s) => s.trim()).filter(Boolean).forEach((b) => pills.push(`<span class="pill">${esc(b)}</span>`));
  if (o.weather) pills.push(`<span class="pill">${esc(o.weather)}</span>`);
  if (o.photo_files) pills.push(`<span class="pill">📷 ${o.photo_files.split(";").length}</span>`);
  if (o.audio_files) pills.push(`<span class="pill">🎙 ${o.audio_files.split(";").length}</span>`);
  return `<article class="obs ${st}">
    <div class="obs-top">
      <div class="obs-name"><strong>${esc(o.species || "Ave sin identificar")}</strong>${o.scientific_name ? `<em>${esc(o.scientific_name)}</em>` : ""}</div>
      ${o.count ? `<span class="obs-count">×${esc(o.count)}</span>` : ""}
      <div class="obs-acts">
        <button type="button" class="icon-btn" data-edit="${o.observation_id}" aria-label="Editar"><svg><use href="#i-edit"/></svg></button>
        <button type="button" class="icon-btn danger" data-del="${o.observation_id}" aria-label="Eliminar"><svg><use href="#i-trash"/></svg></button>
      </div>
    </div>
    <div class="obs-meta">${meta.join("")}</div>
    ${pills.length ? `<div class="pills">${pills.join("")}</div>` : ""}
    ${o.notes ? `<p class="obs-notes">${esc(o.notes)}</p>` : ""}
  </article>`;
}

function renderRegistro() {
  const all = store.observations;
  $("#regCount").textContent = `${all.length} ${all.length === 1 ? "observación" : "observaciones"}`;
  const q = norm($("#regSearch").value);
  const rows = all.filter((o) => (regFilter === "all" || o.status === regFilter) &&
    (!q || norm([o.species, o.scientific_name, o.place, o.notes, o.observer, o.behavior, o.habitat].join(" ")).includes(q)));
  const el = $("#regList");
  if (!all.length) {
    el.innerHTML = `<div class="empty-state"><img src="icons/icon.svg" alt=""><h3>Tu libreta está vacía</h3><p>Anota tu primera observación o importa un CSV.</p><a class="btn btn-primary" href="#/anotar">Anotar observación</a></div>`;
    return;
  }
  if (!rows.length) { el.innerHTML = `<div class="empty-state"><h3>Sin resultados</h3><p>Prueba con otra búsqueda o filtro.</p></div>`; return; }
  const pendingIds = new Set(store.pending().map((o) => o.observation_id));
  const groups = new Map();
  for (const o of rows) { const k = (o.datetime || "").slice(0, 10) || "sin fecha"; if (!groups.has(k)) groups.set(k, []); groups.get(k).push(o); }
  el.innerHTML = [...groups].map(([day, list]) => {
    const label = day === "sin fecha" ? "Sin fecha" : day === todayKey() ? "Hoy" : fmtDay.format(parseLocal(day));
    return `<h3 class="day"><span>${esc(label)}</span><span>${list.length}</span></h3><div class="obs-grid">${list.map((o) => obsCard(o, pendingIds)).join("")}</div>`;
  }).join("");
}
$("#regList").addEventListener("click", (e) => {
  const ed = e.target.closest("[data-edit]"), del = e.target.closest("[data-del]");
  if (ed) startEdit(ed.dataset.edit);
  if (del) removeObs(del.dataset.del);
});

// ---------- Today (side panel) ----------
function renderToday() {
  const t = todayKey();
  const list = store.observations.filter((o) => (o.datetime || "").startsWith(t));
  $("#todayList").innerHTML = list.length
    ? list.slice(0, 12).map((o) => `<div class="mini-item"><span class="t">${esc(fmtTime(o.datetime))}</span><span class="n">${esc(o.species || "Sin identificar")}</span>${o.count ? `<span class="obs-count">×${esc(o.count)}</span>` : ""}</div>`).join("")
    : `<p class="mini-empty">Aún no hay observaciones hoy.</p>`;
}

// ---------- Especies ----------
$("#spSearch").addEventListener("input", () => renderEspecies());
function renderEspecies() {
  const obs = store.observations;
  const agg = new Map();
  for (const o of obs) {
    if (!o.species) continue;
    const k = o.species;
    const a = agg.get(k) || { c: o.species, s: o.scientific_name, n: 0, ind: 0, confirmed: 0, last: "", first: "9999" };
    a.n++; a.ind += parseInt(o.count, 10) || 1;
    if (o.status === "confirmed") a.confirmed++;
    if (o.datetime > a.last) a.last = o.datetime;
    if (o.datetime < a.first) a.first = o.datetime;
    if (!a.s && o.scientific_name) a.s = o.scientific_name;
    agg.set(k, a);
  }
  const days = new Set(obs.map((o) => (o.datetime || "").slice(0, 10)).filter(Boolean));
  const places = new Set(obs.map((o) => norm(o.place)).filter(Boolean));
  const confirmedSpecies = [...agg.values()].filter((a) => a.confirmed).length;
  $("#stats").innerHTML = `
    <div class="stat hero"><b>${confirmedSpecies}</b><span>especies confirmadas</span></div>
    <div class="stat"><b>${obs.length}</b><span>observaciones</span></div>
    <div class="stat"><b>${days.size}</b><span>días en terreno</span></div>
    <div class="stat"><b>${places.size}</b><span>lugares</span></div>`;
  const q = norm($("#spSearch").value);
  const list = [...agg.values()].sort((a, b) => b.n - a.n || a.c.localeCompare(b.c, "es"));
  const max = list[0]?.n || 1;
  const shown = list.map((a, i) => ({ a, rank: i + 1 })).filter(({ a }) => !q || norm(a.c + " " + a.s).includes(q));
  $("#speciesTable").innerHTML = !list.length
    ? `<div class="empty-state"><h3>Aún no hay especies</h3><p>Cuando anotes observaciones con especie aparecerán aquí.</p></div>`
    : !shown.length ? `<div class="empty-state"><p>Sin resultados.</p></div>`
    : shown.map(({ a, rank }) => `<div class="sp-row">
        <div class="nm"><strong><i class="sp-rank">${rank}</i>${esc(a.c)}${a.confirmed ? "" : ` <span class="pill status-tentative">Tentativa</span>`}</strong><em>${esc(a.s)}</em></div>
        <div class="num"><b>${a.n} obs.</b>${a.ind} ind. · ${a.last ? esc(fmtShort.format(parseLocal(a.last.slice(0, 10)))) : "—"}</div>
        <div class="bar"><i style="width:${Math.max(4, (a.n / max) * 100)}%"></i></div>
      </div>`).join("");
}

// ---------- Datos: export / import / linked file ----------
let fileHandle = null, linkGranted = false;

function renderSync() {
  const pend = store.pending().length, total = store.observations.length;
  const warn = pend > 0;
  $("#navDot").hidden = $("#tabDot").hidden = !warn;
  const card = $("#syncCard");
  card.classList.toggle("warn", warn);
  const linked = fileHandle && linkGranted;
  card.innerHTML = `
    <div class="ic"><svg><use href="#${warn ? "i-alert" : "i-ok"}"/></svg></div>
    <div class="grow">
      <h2>${warn ? `${pend} ${pend === 1 ? "cambio" : "cambios"} sin exportar` : total ? "Todo respaldado" : "Sin observaciones aún"}</h2>
      <p>${total} ${total === 1 ? "observación" : "observaciones"} en este dispositivo · último respaldo: ${relTime(store.meta.lastExportAt)}${linked ? " · archivo enlazado activo" : ""}</p>
      <p id="persistInfo"></p>
      ${warn ? `<button type="button" class="btn btn-primary" data-export><svg><use href="#i-download"/></svg><span>Exportar ahora</span></button>` : ""}
    </div>`;
  navigator.storage?.persisted?.().then((p) => {
    const el = $("#persistInfo");
    if (el) el.textContent = p ? "Almacenamiento protegido: el navegador no borrará estos datos automáticamente." : "";
  });
}
$("#syncCard").addEventListener("click", (e) => { if (e.target.closest("[data-export]")) exportCSV(); });

function stamp() { return nowLocal().replace("T", "_").replace(":", ""); }

async function exportCSV() {
  if (!store.observations.length) return toast("No hay observaciones para exportar");
  const name = `observaciones_${stamp()}.csv`;
  const blob = new Blob([toCSV(store.observations)], { type: "text/csv;charset=utf-8" });
  const file = new File([blob], name, { type: "text/csv" });
  const mobile = matchMedia("(pointer: coarse)").matches;
  if (mobile && navigator.canShare?.({ files: [file] })) {
    try {
      await navigator.share({ files: [file], title: "Observaciones de aves" });
      store.markExported(); renderAll(); toast("CSV compartido");
    } catch (err) { if (err.name !== "AbortError") download(blob, name); }
    return;
  }
  download(blob, name);
}
function download(blob, name) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = name;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  store.markExported(); renderAll(); toast(`Descargado ${name}`);
}
$("#exportBtn").addEventListener("click", exportCSV);

$("#importBtn").addEventListener("click", () => $("#fileInput").click());
$("#fileInput").addEventListener("change", async (e) => {
  const f = e.target.files[0]; e.target.value = "";
  if (!f) return;
  try {
    const res = store.merge(parseCSV(await f.text()));
    await writeLinked(); renderAll();
    toast(`Importado: ${res.added} nuevas, ${res.updated} actualizadas`);
  } catch (err) { toast(err.message || "No se pudo leer el archivo"); }
});

async function writeLinked() {
  if (!fileHandle || !linkGranted) return false;
  try {
    const w = await fileHandle.createWritable();
    await w.write(toCSV(store.observations)); await w.close();
    store.markExported();
    return true;
  } catch {
    linkGranted = false; renderLink(); toast("No se pudo escribir el archivo enlazado");
    return false;
  }
}

function renderLink() {
  const st = $("#linkState"), btn = $("#linkBtn");
  if (!supportsFS) {
    st.textContent = ""; btn.hidden = true; $("#unlinkBtn").hidden = true;
    $("#linkCard .muted").innerHTML = "Disponible en Chrome o Edge de computador. En este dispositivo usa <b>Exportar</b> e <b>Importar</b>.";
    return;
  }
  $("#unlinkBtn").hidden = !fileHandle;
  if (fileHandle && linkGranted) { st.className = "link-state"; st.textContent = `Guardando automáticamente en ${fileHandle.name}`; btn.querySelector("span").textContent = "Cambiar archivo"; }
  else if (fileHandle) { st.className = "link-state pending"; st.textContent = `${fileHandle.name} necesita permiso de nuevo`; btn.querySelector("span").textContent = "Reconectar"; }
  else { st.textContent = ""; btn.querySelector("span").textContent = "Enlazar archivo"; }
}

async function syncWithLinked() {
  const txt = await (await fileHandle.getFile()).text();
  const res = txt.trim() ? store.merge(parseCSV(txt)) : { added: 0, updated: 0 };
  await writeLinked();
  renderAll();
  return res;
}

$("#linkBtn").addEventListener("click", async () => {
  try {
    if (fileHandle && !linkGranted) {
      linkGranted = (await fileHandle.requestPermission({ mode: "readwrite" })) === "granted";
    } else {
      [fileHandle] = await window.showOpenFilePicker({ types: [{ description: "CSV", accept: { "text/csv": [".csv"] } }] });
      linkGranted = (await fileHandle.requestPermission({ mode: "readwrite" })) === "granted";
      await idbSet("linkedFile", fileHandle);
    }
    if (linkGranted) {
      const res = await syncWithLinked();
      toast(`Enlazado · ${res.added} nuevas desde el archivo`);
    }
  } catch (err) {
    if (err.name !== "AbortError") toast(err.message || "No se pudo enlazar el archivo");
  }
  renderLink(); renderSync();
});
$("#unlinkBtn").addEventListener("click", async () => {
  fileHandle = null; linkGranted = false; await idbSet("linkedFile", undefined); renderLink(); renderSync();
});

async function restoreLink() {
  if (!supportsFS) return renderLink();
  fileHandle = (await idbGet("linkedFile")) || null;
  if (fileHandle) {
    try { linkGranted = (await fileHandle.queryPermission({ mode: "readwrite" })) === "granted"; } catch { linkGranted = false; }
    if (linkGranted) { try { await syncWithLinked(); } catch {} }
  }
  renderLink(); renderSync();
}

let persistAsked = false;
function requestPersistence() {
  if (persistAsked || !navigator.storage?.persist) return;
  persistAsked = true;
  navigator.storage.persist().catch(() => {});
}

// ---------- Theme & install ----------
function applyTheme(t) {
  if (t === "auto") delete document.documentElement.dataset.theme; else document.documentElement.dataset.theme = t;
  $$("#themeSeg button").forEach((b) => b.classList.toggle("on", b.dataset.t === t));
}
$("#themeSeg").addEventListener("click", (e) => { const b = e.target.closest("button"); if (!b) return; store.setTheme(b.dataset.t); applyTheme(b.dataset.t); });

let installEvt = null;
addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); installEvt = e; renderInstall(); });
addEventListener("appinstalled", () => { installEvt = null; toast("App instalada"); renderInstall(); });
function renderInstall() {
  const box = $("#installBox");
  if (isStandalone) { box.innerHTML = "✓ Estás usando la app instalada."; return; }
  if (installEvt) {
    box.innerHTML = `<p style="margin:0 0 10px">Instala la libreta para abrirla como app y usarla sin conexión.</p><button type="button" class="btn btn-secondary" id="installBtn">Instalar app</button>`;
    $("#installBtn").onclick = async () => { installEvt.prompt(); await installEvt.userChoice; installEvt = null; renderInstall(); };
  } else if (/iphone|ipad|ipod/i.test(navigator.userAgent)) {
    box.innerHTML = "Para instalarla en iPhone: abre esta página en Safari, toca <b>Compartir</b> y luego <b>Agregar a pantalla de inicio</b>.";
  } else box.innerHTML = "";
}

// ---------- Network status ----------
function renderNet() {
  const p = $("#netPill");
  p.textContent = navigator.onLine ? "En línea" : "Sin conexión · se guarda en el equipo";
  p.classList.toggle("off", !navigator.onLine);
}
addEventListener("online", renderNet);
addEventListener("offline", renderNet);

// ---------- Router ----------
const VIEWS = ["anotar", "registro", "especies", "datos"];
function route() {
  const v = (location.hash.match(/^#\/(\w+)/) || [])[1];
  const view = VIEWS.includes(v) ? v : "anotar";
  VIEWS.forEach((x) => ($(`#view-${x}`).hidden = x !== view));
  $$("[data-view]").forEach((a) => { const on = a.dataset.view === view; a.classList.toggle("on", on); on ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current"); });
  if (view !== "anotar" && form.editingId) resetForm();
  if (view === "registro") renderRegistro();
  if (view === "especies") renderEspecies();
  if (view === "datos") renderSync();
  scrollTo({ top: 0 });
}
addEventListener("hashchange", route);

function renderAll() {
  renderRecent(); renderPlaces(); renderToday(); renderSync();
  if (!$("#view-registro").hidden) renderRegistro();
  if (!$("#view-especies").hidden) renderEspecies();
}

// ---------- Service worker ----------
function registerSW() {
  if (!("serviceWorker" in navigator) || location.protocol === "file:") return;
  // Skip on local dev so edits show up immediately; add ?sw to the URL to test offline mode
  if (["localhost", "127.0.0.1"].includes(location.hostname) && !location.search.includes("sw")) return;
  navigator.serviceWorker.register("sw.js").then((reg) => {
    const notify = (w) => toast("Hay una nueva versión disponible", { label: "Actualizar", run: () => w.postMessage("skipWaiting") });
    if (reg.waiting && navigator.serviceWorker.controller) notify(reg.waiting);
    reg.addEventListener("updatefound", () => {
      const w = reg.installing;
      w?.addEventListener("statechange", () => { if (w.state === "installed" && navigator.serviceWorker.controller) notify(w); });
    });
  }).catch(() => {});
  let reloaded = false;
  navigator.serviceWorker.addEventListener("controllerchange", () => { if (!reloaded) { reloaded = true; location.reload(); } });
}

// ---------- Init ----------
(async function init() {
  store.load();
  $("#todayLabel").textContent = fmtDay.format(new Date());
  applyTheme(store.getTheme());
  renderObserver(); renderNet(); renderInstall();
  resetForm();
  route();
  renderAll();
  await loadSpecies();
  restoreLink();
  registerSW();
})();
