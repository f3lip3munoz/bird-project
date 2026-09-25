"""Importa las fotos de Bird-Project/Aves/ y las agrupa en observaciones.

Reglas:
- La primera carpeta bajo Aves/ define la especie (ver carpetas.csv; si no está, se busca
  una especie con el mismo nombre). Las fotos de carpetas de especie quedan confirmadas.
- Fotos de la misma carpeta separadas por <= GAP minutos forman una sola observación.
- Es repetible: los archivos sin cambios se saltan; un archivo movido de carpeta se reconoce
  por su hash SHA-256 y se reasigna (útil al ordenar Revisión/).
"""
import hashlib
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .config import MULTIPLE, ROOT_FOLDER, UNIDENTIFIED
from .db import utcnow
from .exif import read_photo_info
from .species import SpeciesIndex, norm

PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}
DEFAULT_GAP_MIN = 30


@dataclass
class FolderTarget:
    folder: str
    species: sqlite3.Row | None
    kind: str  # species | unidentified | multiple

    @property
    def label(self) -> str:
        return self.folder or "(sueltas en Aves/)"


def resolve_folder(folder: str, folder_map: dict[str, str], index: SpeciesIndex) -> FolderTarget | None:
    key = ROOT_FOLDER if folder == "" else folder
    mapped = {norm(k): v for k, v in folder_map.items()}.get(norm(key))
    if mapped == UNIDENTIFIED:
        return FolderTarget(folder, None, "unidentified")
    if mapped == MULTIPLE:
        return FolderTarget(folder, None, "multiple")
    sp = index.resolve(common=mapped or folder)
    return FolderTarget(folder, sp, "species") if sp else None


def sha256(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def top_folder(rel_to_aves: Path) -> str:
    return rel_to_aves.parts[0] if len(rel_to_aves.parts) > 1 else ""


def import_photos(con: sqlite3.Connection, bird_project: Path, folder_map: dict[str, str],
                  observer: str = "", gap_min: int = DEFAULT_GAP_MIN, log=print) -> dict:
    aves = bird_project / "Aves"
    if not aves.is_dir():
        raise SystemExit(f"No existe la carpeta {aves}")
    index = SpeciesIndex(con)
    stats = Counter()

    files = sorted(p for p in aves.rglob("*") if p.is_file() and p.suffix.lower() in PHOTO_EXTS)
    on_disk = {p.relative_to(bird_project).as_posix(): p for p in files}

    # Folder → species mapping; folders that cannot be mapped are skipped and reported
    targets: dict[str, FolderTarget] = {}
    unmapped: set[str] = set()
    for p in files:
        folder = top_folder(p.relative_to(aves))
        if folder not in targets and folder not in unmapped:
            t = resolve_folder(folder, folder_map, index)
            if t:
                targets[folder] = t
            else:
                unmapped.add(folder)

    known = {r["rel_path"]: r for r in con.execute("SELECT * FROM media WHERE kind = 'photo'")}
    gone_by_hash: dict[str, list[sqlite3.Row]] = {}
    for rel, r in known.items():
        if rel not in on_disk:
            gone_by_hash.setdefault(r["sha256"], []).append(r)
    moved_ids: set[int] = set()

    now = utcnow()
    total = len(files)
    for i, p in enumerate(files, start=1):
        if i % 25 == 0 or i == total:
            log(f"  fotos revisadas: {i}/{total}")
        rel = p.relative_to(bird_project).as_posix()
        folder = top_folder(p.relative_to(aves))
        if folder in unmapped:
            stats["skipped_unmapped"] += 1
            continue
        st = p.stat()
        row = known.get(rel)
        if row and row["size_bytes"] == st.st_size and row["mtime_ns"] == st.st_mtime_ns:
            if row["missing"]:
                con.execute("UPDATE media SET missing = 0 WHERE media_id = ?", (row["media_id"],))
            stats["unchanged"] += 1
            continue

        digest = sha256(p)
        info = read_photo_info(p)
        values = dict(folder=folder, file_name=p.name, size_bytes=st.st_size, mtime_ns=st.st_mtime_ns, sha256=digest,
                      taken_at=info.taken_at, taken_at_source=info.taken_at_source, latitude=info.latitude,
                      longitude=info.longitude, camera=info.camera, width=info.width, height=info.height)
        sets = ", ".join(f"{k} = :{k}" for k in values)

        if row:  # same path, file content changed: refresh metadata, keep its observation
            con.execute(f"UPDATE media SET {sets}, missing = 0 WHERE media_id = :id", {**values, "id": row["media_id"]})
            stats["updated"] += 1
        elif gone_by_hash.get(digest):
            moved = gone_by_hash[digest].pop()
            moved_ids.add(moved["media_id"])
            con.execute(f"UPDATE media SET {sets}, rel_path = :rel, missing = 0, observation_id = NULL WHERE media_id = :id",
                        {**values, "rel": rel, "id": moved["media_id"]})
            stats["moved"] += 1
        else:
            con.execute(
                f"INSERT INTO media (kind, rel_path, imported_at, {', '.join(values)}) "
                f"VALUES ('photo', :rel, :now, {', '.join(':' + k for k in values)})",
                {**values, "rel": rel, "now": now})
            stats["new"] += 1

    # Files that disappeared (not moved): keep the row, flag it
    for rel, r in known.items():
        if rel not in on_disk and r["media_id"] not in moved_ids and not r["missing"]:
            con.execute("UPDATE media SET missing = 1 WHERE media_id = ?", (r["media_id"],))
            stats["missing"] += 1

    stats["species_changed"] = _sync_folder_species(con, targets, now)
    stats["observations_created"] = _assign(con, targets, observer, gap_min, now)
    stats["observations_removed"] = con.execute(
        "DELETE FROM observations WHERE origin = 'photos' AND observation_id NOT IN "
        "(SELECT observation_id FROM media WHERE observation_id IS NOT NULL AND missing = 0)").rowcount
    _refresh_summaries(con, now)

    con.execute("INSERT INTO imports (kind, source, started_at, stats) VALUES ('photos', ?, ?, ?)",
                (str(aves), now, repr(dict(stats))))
    con.commit()
    return {**stats, "unmapped_folders": sorted(unmapped), "files": total}


def _new_observation(con, target: FolderTarget, media: sqlite3.Row, observer: str, now: str) -> str:
    obs_id = f"foto_{media['sha256'][:10]}_{media['media_id']}"
    sp = target.species
    notes = f"Importada desde Aves/{target.folder}" if target.folder else "Importada desde Aves/ (foto suelta)"
    if target.kind == "multiple":
        notes += " · varias aves en la foto"
    con.execute(
        """INSERT INTO observations (observation_id, origin, photo_folder, observer, datetime, species_id, species_text,
               status, id_source, review_flag, notes, created_at, updated_at)
           VALUES (?, 'photos', ?, ?, ?, ?, ?, ?, 'manual', ?, ?, ?, ?)""",
        (obs_id, target.folder, observer or None, media["taken_at"][:16], sp["species_id"] if sp else None,
         sp["common_name"] if sp else None, "confirmed" if sp else "unidentified", 0 if sp else 1, notes, now, now))
    if sp:
        con.execute(
            """INSERT INTO identifications (observation_id, species_id, species_text, source, status, note, created_at)
               VALUES (?, ?, ?, 'folder', 'accepted', ?, ?)""",
            (obs_id, sp["species_id"], sp["common_name"], f"Carpeta Aves/{target.folder}", now))
    return obs_id


def _assign(con, targets: dict[str, FolderTarget], observer: str, gap_min: int, now: str) -> int:
    """Attach unassigned photos to the nearest observation of the same folder within gap_min, or start a new one."""
    created = 0
    pending = con.execute(
        "SELECT * FROM media WHERE kind = 'photo' AND missing = 0 AND observation_id IS NULL ORDER BY folder, taken_at").fetchall()
    for m in pending:
        target = targets.get(m["folder"])
        if not target:
            continue
        near = con.execute(
            """SELECT md.observation_id, ABS(julianday(md.taken_at) - julianday(?)) * 1440 AS gap
               FROM media md JOIN observations o ON o.observation_id = md.observation_id
               WHERE o.origin = 'photos' AND o.photo_folder = ? AND md.missing = 0
               ORDER BY gap LIMIT 1""", (m["taken_at"], m["folder"])).fetchone()
        if near and near["gap"] <= gap_min:
            obs_id = near["observation_id"]
        else:
            obs_id = _new_observation(con, target, m, observer, now)
            created += 1
        con.execute("UPDATE media SET observation_id = ? WHERE media_id = ?", (obs_id, m["media_id"]))
    return created


def _sync_folder_species(con, targets: dict[str, FolderTarget], now: str) -> int:
    """If carpetas.csv now maps a folder to a different species, update its observations (and log it)."""
    changed = 0
    for t in targets.values():
        new_id = t.species["species_id"] if t.species else None
        rows = con.execute(
            "SELECT observation_id FROM observations WHERE origin = 'photos' AND photo_folder = ? AND species_id IS NOT ?",
            (t.folder, new_id)).fetchall()
        for r in rows:
            con.execute(
                """UPDATE observations SET species_id = ?, species_text = ?, status = ?, review_flag = ?, updated_at = ?
                   WHERE observation_id = ?""",
                (new_id, t.species["common_name"] if t.species else None, "confirmed" if t.species else "unidentified",
                 0 if t.species else 1, now, r["observation_id"]))
            if t.species:
                con.execute(
                    """INSERT INTO identifications (observation_id, species_id, species_text, source, status, note, created_at)
                       VALUES (?, ?, ?, 'folder', 'accepted', ?, ?)""",
                    (r["observation_id"], new_id, t.species["common_name"], f"Carpeta Aves/{t.folder} (reasignada)", now))
            changed += 1
    return changed


def _refresh_summaries(con, now: str) -> None:
    """Observation date = earliest photo; coordinates = first photo with GPS."""
    con.execute(
        """UPDATE observations SET
             datetime = (SELECT substr(MIN(taken_at), 1, 16) FROM media m
                         WHERE m.observation_id = observations.observation_id AND m.missing = 0),
             latitude = (SELECT latitude FROM media m WHERE m.observation_id = observations.observation_id
                         AND m.missing = 0 AND latitude IS NOT NULL ORDER BY taken_at LIMIT 1),
             longitude = (SELECT longitude FROM media m WHERE m.observation_id = observations.observation_id
                          AND m.missing = 0 AND longitude IS NOT NULL ORDER BY taken_at LIMIT 1),
             photo_files = (SELECT group_concat(file_name, '; ') FROM
                            (SELECT file_name FROM media m WHERE m.observation_id = observations.observation_id
                             AND m.missing = 0 ORDER BY taken_at))
           WHERE origin = 'photos'""")
