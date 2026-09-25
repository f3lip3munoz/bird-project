"""Configuración local (no se versiona): dónde está la carpeta Bird-Project de OneDrive."""
import csv
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = Path(os.environ.get("AVES_CONFIG", REPO_ROOT / "aves.toml"))
FOLDER_MAP_PATH = REPO_ROOT / "pipeline" / "carpetas.csv"

# Marcadores especiales en carpetas.csv
UNIDENTIFIED = "#sin-identificar"
MULTIPLE = "#varias-aves"
ROOT_FOLDER = "."  # fotos sueltas directamente en Aves/


@dataclass
class Config:
    bird_project: Path
    db_path: Path
    observer: str

    @property
    def photos_dir(self) -> Path:
        return self.bird_project / "Aves"

    @property
    def observations_csv(self) -> Path:
        return self.bird_project / "observations.csv"


def load_config(path: Path = CONFIG_PATH) -> Config:
    if not path.exists():
        raise SystemExit(f"Falta {path}. Ejecuta primero:  aves init --bird-project \"RUTA\\Bird-Project\"")
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    root = Path(data["bird_project"])
    db = Path(data.get("db", "db/aves.sqlite"))
    return Config(root, db if db.is_absolute() else root / db, data.get("observador", ""))


def write_config(bird_project: Path, observer: str = "", path: Path = CONFIG_PATH) -> None:
    esc = lambda s: s.replace("\\", "/").replace('"', '\\"')
    path.write_text(
        "# Configuración local de la base de datos de aves (no se sube a GitHub)\n"
        f'bird_project = "{esc(str(bird_project))}"\n'
        'db = "db/aves.sqlite"          # relativo a bird_project\n'
        f'observador = "{esc(observer)}"  # se usa en observaciones importadas desde fotos\n',
        encoding="utf-8",
    )


def load_folder_map(path: Path = FOLDER_MAP_PATH) -> dict[str, str]:
    """carpeta -> nombre común de especie, o un marcador especial (#sin-identificar, #varias-aves)."""
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {r["carpeta"].strip(): r["especie"].strip() for r in csv.DictReader(f) if (r.get("carpeta") or "").strip()}
