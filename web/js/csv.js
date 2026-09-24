// CSV format shared by the web app and the future Python pipeline.
// See docs/data-format.md. Column order is stable; new columns go at the end.

export const COLUMNS = [
  "observation_id", "observer", "datetime", "place", "latitude", "longitude", "gps_accuracy_m",
  "species", "scientific_name", "status", "count", "behavior", "habitat", "weather", "notes",
  "photo_files", "audio_files", "id_source", "id_confidence", "review_flag", "created_at", "updated_at",
];

export const STATUSES = ["confirmed", "tentative", "unidentified"];

// Values written by the first (English) version of field-note.html
const LEGACY_BEHAVIOR = {
  "Perched": "Posado", "Feeding": "Alimentándose", "Flying": "Volando", "Calling / singing": "Cantando",
  "Nesting": "Nidificando", "Foraging": "Forrajeando", "Swimming": "Nadando", "In flock": "En bandada",
};
const LEGACY_HABITAT = {
  "Forest / bosque": "Bosque", "Coast / costa": "Costa", "Wetland / humedal": "Humedal",
  "Grassland / pastizal": "Pastizal", "Shrubland / matorral": "Matorral", "Desert / desierto": "Desierto",
  "Mountain / cordillera": "Cordillera", "Urban / urbano": "Urbano", "Farmland / campo": "Campo",
  "River-lake / río-lago": "Río / lago",
};

const escape = (v) => {
  v = v == null ? "" : String(v);
  return /[",\n\r]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
};

/** Serialise rows to CSV. Includes a UTF-8 BOM so Excel shows accents correctly. */
export function toCSV(rows) {
  const lines = [COLUMNS.join(",")];
  for (const r of rows) lines.push(COLUMNS.map((c) => escape(r[c])).join(","));
  return "﻿" + lines.join("\r\n") + "\r\n";
}

/** Parse CSV text (RFC 4180, quoted fields may contain commas/newlines) into row objects. */
export function parseCSV(text) {
  text = text.replace(/^﻿/, "");
  const rows = [];
  let row = [], field = "", inQ = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (inQ) {
      if (ch === '"') { if (text[i + 1] === '"') { field += '"'; i++; } else inQ = false; }
      else field += ch;
    } else if (ch === '"') inQ = true;
    else if (ch === ",") { row.push(field); field = ""; }
    else if (ch === "\n") { row.push(field); rows.push(row); row = []; field = ""; }
    else if (ch !== "\r") field += ch;
  }
  if (field.length || row.length) { row.push(field); rows.push(row); }
  if (!rows.length) return [];
  const header = rows.shift().map((h) => h.trim());
  if (!header.includes("observation_id") && !header.includes("species")) {
    throw new Error("El archivo no parece ser un CSV de observaciones");
  }
  return rows
    .filter((r) => r.some((v) => v.trim() !== ""))
    .map((r) => {
      const o = {};
      header.forEach((h, i) => (o[h] = r[i] ?? ""));
      return normalizeRow(o);
    });
}

/** Fill missing columns and translate values from the legacy English version. */
export function normalizeRow(o) {
  const out = {};
  for (const c of COLUMNS) out[c] = o[c] == null ? "" : String(o[c]);
  out.behavior = out.behavior.split(";").map((s) => s.trim()).filter(Boolean)
    .map((b) => LEGACY_BEHAVIOR[b] || b).join("; ");
  out.habitat = LEGACY_HABITAT[out.habitat] || out.habitat;
  out.status = STATUSES.includes(out.status.toLowerCase()) ? out.status.toLowerCase() : (out.species ? "tentative" : "unidentified");
  if (!out.updated_at) out.updated_at = out.created_at;
  return out;
}
