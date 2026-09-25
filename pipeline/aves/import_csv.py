"""Importa el CSV exportado por la web (formato en docs/data-format.md)."""
import csv
import sqlite3
from collections import Counter
from pathlib import Path

from .db import utcnow
from .species import SpeciesIndex

LEGACY_BEHAVIOR = {
    "Perched": "Posado", "Feeding": "Alimentándose", "Flying": "Volando", "Calling / singing": "Cantando",
    "Nesting": "Nidificando", "Foraging": "Forrajeando", "Swimming": "Nadando", "In flock": "En bandada",
}
LEGACY_HABITAT = {
    "Forest / bosque": "Bosque", "Coast / costa": "Costa", "Wetland / humedal": "Humedal",
    "Grassland / pastizal": "Pastizal", "Shrubland / matorral": "Matorral", "Desert / desierto": "Desierto",
    "Mountain / cordillera": "Cordillera", "Urban / urbano": "Urbano", "Farmland / campo": "Campo",
    "River-lake / río-lago": "Río / lago",
}
STATUSES = {"confirmed", "tentative", "unidentified"}


def _num(v, cast):
    try:
        return cast(v) if v is not None and str(v).strip() != "" else None
    except ValueError:
        return None


def import_csv(con: sqlite3.Connection, path: Path) -> dict:
    index = SpeciesIndex(con)
    stats, unknown = Counter(), Counter()
    now = utcnow()
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "observation_id" not in reader.fieldnames:
            raise SystemExit(f"{path.name} no parece un CSV de observaciones (falta la columna observation_id)")
        for r in reader:
            r = {k: (v or "").strip() for k, v in r.items() if k}
            oid = r.get("observation_id")
            if not oid:
                stats["skipped_no_id"] += 1
                continue
            updated = r.get("updated_at") or r.get("created_at") or now
            prev = con.execute("SELECT updated_at, species_id FROM observations WHERE observation_id = ?", (oid,)).fetchone()
            if prev and prev["updated_at"] >= updated:
                stats["unchanged"] += 1
                continue

            sp = index.resolve(r.get("species"), r.get("scientific_name"))
            if r.get("species") and not sp:
                unknown[r["species"]] += 1
            status = r.get("status", "").lower()
            if status not in STATUSES:
                status = "tentative" if r.get("species") else "unidentified"
            behavior = "; ".join(LEGACY_BEHAVIOR.get(b.strip(), b.strip()) for b in r.get("behavior", "").split(";") if b.strip())
            rec = dict(
                observation_id=oid, origin="web", observer=r.get("observer") or None, datetime=r.get("datetime") or None,
                place=r.get("place") or None, latitude=_num(r.get("latitude"), float), longitude=_num(r.get("longitude"), float),
                gps_accuracy_m=_num(r.get("gps_accuracy_m"), float),
                species_id=sp["species_id"] if sp else None, species_text=r.get("species") or None,
                status=status, count=_num(r.get("count"), int), behavior=behavior or None,
                habitat=LEGACY_HABITAT.get(r.get("habitat", ""), r.get("habitat")) or None,
                weather=r.get("weather") or None, notes=r.get("notes") or None,
                photo_files=r.get("photo_files") or None, audio_files=r.get("audio_files") or None,
                id_source=r.get("id_source") or "manual", id_confidence=_num(r.get("id_confidence"), float),
                review_flag=1 if r.get("review_flag", "0") == "1" or status != "confirmed" else 0,
                created_at=r.get("created_at") or now, updated_at=updated,
            )
            cols = ", ".join(rec)
            con.execute(
                f"INSERT INTO observations ({cols}) VALUES ({', '.join(':' + k for k in rec)}) "
                f"ON CONFLICT (observation_id) DO UPDATE SET {', '.join(f'{k} = excluded.{k}' for k in rec if k != 'observation_id')}",
                rec)
            # Identification history: log when the species is new or changed
            if rec["species_text"] and (not prev or prev["species_id"] != rec["species_id"]):
                con.execute(
                    """INSERT INTO identifications (observation_id, species_id, species_text, source, confidence, status, note, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, 'Libreta web', ?)""",
                    (oid, rec["species_id"], rec["species_text"], rec["id_source"], rec["id_confidence"],
                     "accepted" if status == "confirmed" else "suggested", now))
            stats["updated" if prev else "new"] += 1

    con.execute("INSERT INTO imports (kind, source, started_at, stats) VALUES ('csv', ?, ?, ?)", (str(path), now, repr(dict(stats))))
    con.commit()
    return {**stats, "unknown_species": dict(unknown)}
