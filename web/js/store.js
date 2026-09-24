// Local persistence. Observations live in localStorage (per device, per browser);
// the linked CSV file handle lives in IndexedDB because it cannot be serialised to JSON.

import { normalizeRow } from "./csv.js";

const KEY = {
  obs: "libreta_observations_v2",
  observers: "libreta_observers_v1",
  current: "libreta_current_observer_v1",
  meta: "libreta_meta_v1",
  theme: "libreta_theme",
};

const read = (k, fallback) => {
  try { const v = localStorage.getItem(k); return v == null ? fallback : JSON.parse(v); } catch { return fallback; }
};
const write = (k, v) => {
  try { localStorage.setItem(k, JSON.stringify(v)); return true; } catch { return false; }
};

export const byDateDesc = (a, b) => (b.datetime || "").localeCompare(a.datetime || "");

export const store = {
  observations: [],
  observers: [],
  current: "",
  // lastExportAt: ISO string, recent: [{c, s}], places: [string]
  meta: { lastExportAt: "", recent: [], places: [] },

  load() {
    this.observations = read(KEY.obs, []).map(normalizeRow).sort(byDateDesc);
    this.observers = read(KEY.observers, []);
    this.current = read(KEY.current, "");
    this.meta = { lastExportAt: "", recent: [], places: [], ...read(KEY.meta, {}) };
  },
  saveObservations() { return write(KEY.obs, this.observations); },
  saveObservers() { write(KEY.observers, this.observers); write(KEY.current, this.current); },
  saveMeta() { write(KEY.meta, this.meta); },

  upsert(rec) {
    const i = this.observations.findIndex((o) => o.observation_id === rec.observation_id);
    if (i >= 0) this.observations[i] = rec; else this.observations.push(rec);
    this.observations.sort(byDateDesc);
    this.rememberUse(rec);
    return this.saveObservations();
  },
  remove(id) {
    const i = this.observations.findIndex((o) => o.observation_id === id);
    if (i < 0) return null;
    const [gone] = this.observations.splice(i, 1);
    this.saveObservations();
    return gone;
  },

  /** Merge incoming rows by id; the most recently updated version wins. */
  merge(rows) {
    const byId = new Map(this.observations.map((o) => [o.observation_id, o]));
    let added = 0, updated = 0;
    for (const r of rows) {
      if (!r.observation_id) r.observation_id = newId();
      const cur = byId.get(r.observation_id);
      if (!cur) { byId.set(r.observation_id, r); added++; }
      else if ((r.updated_at || "") > (cur.updated_at || "")) { byId.set(r.observation_id, r); updated++; }
    }
    this.observations = [...byId.values()].sort(byDateDesc);
    this.saveObservations();
    return { added, updated };
  },

  rememberUse(rec) {
    if (rec.species) {
      this.meta.recent = [{ c: rec.species, s: rec.scientific_name }, ...this.meta.recent.filter((x) => x.c !== rec.species)].slice(0, 8);
    }
    if (rec.place) {
      this.meta.places = [rec.place, ...this.meta.places.filter((p) => p !== rec.place)].slice(0, 30);
    }
    this.saveMeta();
  },

  /** Observations created or edited since the last export. */
  pending() {
    const t = this.meta.lastExportAt || "";
    return this.observations.filter((o) => (o.updated_at || o.created_at || "") > t);
  },
  markExported() { this.meta.lastExportAt = new Date().toISOString(); this.saveMeta(); },

  getTheme() { try { return localStorage.getItem(KEY.theme) || "auto"; } catch { return "auto"; } },
  setTheme(t) { try { t === "auto" ? localStorage.removeItem(KEY.theme) : localStorage.setItem(KEY.theme, t); } catch {} },
};

export function newId() {
  return "obs_" + Date.now().toString(36) + "_" + Math.random().toString(36).slice(2, 7);
}

// ---------- IndexedDB (linked file handle) ----------
function idb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open("libreta-aves", 1);
    req.onupgradeneeded = () => req.result.createObjectStore("kv");
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}
export async function idbGet(key) {
  try {
    const db = await idb();
    return await new Promise((res, rej) => {
      const r = db.transaction("kv").objectStore("kv").get(key);
      r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error);
    });
  } catch { return undefined; }
}
export async function idbSet(key, value) {
  try {
    const db = await idb();
    await new Promise((res, rej) => {
      const tx = db.transaction("kv", "readwrite");
      value === undefined ? tx.objectStore("kv").delete(key) : tx.objectStore("kv").put(value, key);
      tx.oncomplete = res; tx.onerror = () => rej(tx.error);
    });
  } catch {}
}
