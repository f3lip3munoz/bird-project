"""Lista de especies de Chile y resolución de nombres."""
import json
import sqlite3
import unicodedata
from pathlib import Path

# Fuente única, compartida con la web
SPECIES_JSON = Path(__file__).resolve().parents[2] / "web" / "data" / "chile_birds.json"


def norm(s: str | None) -> str:
    """Lowercase, strip accents, treat '-' as space and collapse whitespace."""
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").replace("-", " ")
    return " ".join(s.split())


def load_species(con: sqlite3.Connection, path: Path = SPECIES_JSON) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    for i, sp in enumerate(data, start=1):
        con.execute(
            """INSERT INTO species (taxon_order, common_name, scientific_name, note) VALUES (?, ?, ?, ?)
               ON CONFLICT (scientific_name) DO UPDATE SET
                 taxon_order = excluded.taxon_order, common_name = excluded.common_name, note = excluded.note""",
            (i, sp["c"], sp["s"], sp.get("t")),
        )
    con.commit()
    return len(data)


class SpeciesIndex:
    def __init__(self, con: sqlite3.Connection):
        self.by_common: dict[str, sqlite3.Row] = {}
        self.by_sci: dict[str, sqlite3.Row] = {}
        for r in con.execute("SELECT * FROM species"):
            self.by_common[norm(r["common_name"])] = r
            self.by_sci[norm(r["scientific_name"])] = r

    def resolve(self, common: str | None = None, scientific: str | None = None) -> sqlite3.Row | None:
        """Find a species by scientific name first (more stable), then by common name."""
        if scientific and (r := self.by_sci.get(norm(scientific))):
            return r
        if common and (r := self.by_common.get(norm(common))):
            return r
        return None
