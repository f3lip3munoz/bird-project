"""Conexión, creación del esquema y respaldos de la base SQLite."""
import shutil
import sqlite3
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path

SCHEMA_VERSION = 1


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    # Rollback journal (not WAL): a single file is safer inside a OneDrive folder
    con.execute("PRAGMA journal_mode = DELETE")
    ensure_schema(con)
    return con


def ensure_schema(con: sqlite3.Connection) -> None:
    version = con.execute("PRAGMA user_version").fetchone()[0]
    if version == SCHEMA_VERSION:
        return
    if version != 0:
        raise RuntimeError(f"Versión de esquema {version} no soportada (se esperaba {SCHEMA_VERSION})")
    con.executescript(resources.files("aves").joinpath("schema.sql").read_text(encoding="utf-8"))
    con.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    con.commit()


def backup(db_path: Path, keep: int = 10) -> Path | None:
    """Copy the database to db/respaldos/ before an import; keep the newest `keep` copies."""
    if not db_path.exists():
        return None
    folder = db_path.parent / "respaldos"
    folder.mkdir(exist_ok=True)
    dest = folder / f"{db_path.stem}_{datetime.now():%Y%m%d_%H%M%S}{db_path.suffix}"
    shutil.copy2(db_path, dest)
    for old in sorted(folder.glob(f"{db_path.stem}_*{db_path.suffix}"))[:-keep]:
        old.unlink()
    return dest
