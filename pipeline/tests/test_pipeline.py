"""Pruebas de la base de datos con fotos sintéticas.  python -m unittest discover -s pipeline/tests"""
import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from aves.db import connect
from aves.exif import gps_to_decimal, read_photo_info
from aves.import_csv import import_csv
from aves.import_photos import import_photos
from aves.species import load_species, norm

FOLDER_MAP = {".": "#sin-identificar", "Revisión": "#sin-identificar", "Tenca": "Tenca chilena"}


def make_photo(path: Path, taken: str | None, color=(120, 80, 40)):
    """Tiny JPEG with EXIF DateTime ('YYYY:MM:DD HH:MM:SS'). Unique color → unique hash."""
    path.parent.mkdir(parents=True, exist_ok=True)
    exif = Image.Exif()
    if taken:
        exif[306] = taken
    Image.new("RGB", (8, 6), color).save(path, "JPEG", exif=exif.tobytes())


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "Bird-Project"
        self.aves = self.root / "Aves"
        self.con = connect(self.root / "db" / "aves.sqlite")
        load_species(self.con)
        make_photo(self.aves / "Chincol" / "IMG_1.JPG", "2024:05:11 10:00:00", (1, 0, 0))
        make_photo(self.aves / "Chincol" / "IMG_2.JPG", "2024:05:11 10:20:00", (2, 0, 0))  # 20 min → same obs
        make_photo(self.aves / "Chincol" / "IMG_3.JPG", "2024:05:11 12:00:00", (3, 0, 0))  # 100 min → new obs
        make_photo(self.aves / "Tenca" / "IMG_4.JPG", "2024:05:11 10:05:00", (4, 0, 0))
        make_photo(self.aves / "Revisión" / "20230214_192906.jpg", None, (5, 0, 0))     # date from file name
        make_photo(self.aves / "IMG_6.JPG", "2024:05:12 08:00:00", (6, 0, 0))           # loose in Aves/

    def tearDown(self):
        self.con.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_import(self):
        return import_photos(self.con, self.root, FOLDER_MAP, observer="Tester", log=lambda *_: None)

    def obs(self, where="1=1"):
        return self.con.execute(f"SELECT * FROM observations WHERE {where} ORDER BY datetime").fetchall()

    def test_grouping_and_species(self):
        s = self.run_import()
        self.assertEqual(s["new"], 6)
        chincol = self.obs("species_text = 'Chincol'")
        self.assertEqual([o["datetime"] for o in chincol], ["2024-05-11T10:00", "2024-05-11T12:00"])
        self.assertTrue(all(o["status"] == "confirmed" and o["review_flag"] == 0 for o in chincol))
        self.assertEqual(chincol[0]["photo_files"], "IMG_1.JPG; IMG_2.JPG")
        self.assertEqual(self.obs("species_text = 'Tenca chilena'")[0]["status"], "confirmed")
        unid = self.obs("status = 'unidentified'")
        self.assertEqual(len(unid), 2)
        self.assertTrue(all(o["review_flag"] == 1 for o in unid))
        rev = self.con.execute("SELECT * FROM media WHERE folder = 'Revisión'").fetchone()
        self.assertEqual((rev["taken_at"], rev["taken_at_source"]), ("2023-02-14T19:29:06", "filename"))
        # identification history: one 'folder' entry per confirmed observation
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM identifications WHERE source = 'folder'").fetchone()[0], 3)

    def test_rerun_is_idempotent(self):
        self.run_import()
        before = self.con.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
        s = self.run_import()
        self.assertEqual((s.get("new", 0), s["unchanged"], s["observations_created"]), (0, 6, 0))
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM observations").fetchone()[0], before)

    def test_sorting_a_review_photo_moves_it(self):
        self.run_import()
        # User sorts the review photo into Chincol, near the 12:00 sighting (its date comes from the file name,
        # so give it a Chincol-compatible time by renaming)
        src = self.aves / "Revisión" / "20230214_192906.jpg"
        dst = self.aves / "Chincol" / "20240511_120500.jpg"
        dst.write_bytes(src.read_bytes()); src.unlink()
        s = self.run_import()
        self.assertEqual((s["moved"], s["observations_removed"]), (1, 1))
        m = self.con.execute("SELECT * FROM media WHERE file_name = '20240511_120500.jpg'").fetchone()
        self.assertEqual(m["folder"], "Chincol")
        o = self.con.execute("SELECT * FROM observations WHERE observation_id = ?", (m["observation_id"],)).fetchone()
        self.assertEqual((o["species_text"], o["datetime"]), ("Chincol", "2024-05-11T12:00"))
        self.assertEqual(len(self.obs("status = 'unidentified'")), 1)

    def test_deleted_photo_is_flagged(self):
        self.run_import()
        (self.aves / "Tenca" / "IMG_4.JPG").unlink()
        s = self.run_import()
        self.assertEqual((s["missing"], s["observations_removed"]), (1, 1))
        self.assertEqual(self.con.execute("SELECT missing FROM media WHERE file_name = 'IMG_4.JPG'").fetchone()[0], 1)

    def test_unmapped_folder_is_reported(self):
        make_photo(self.aves / "Pajarito raro" / "x.jpg", "2024:01:01 00:00:00", (9, 9, 9))
        s = self.run_import()
        self.assertEqual(s["unmapped_folders"], ["Pajarito raro"])
        self.assertEqual(s["skipped_unmapped"], 1)

    def test_csv_import_and_update(self):
        csv_path = self.tmp / "obs.csv"
        header = "observation_id,observer,datetime,place,species,scientific_name,status,count,behavior,habitat,notes,created_at,updated_at\n"
        csv_path.write_text("﻿" + header +
                            'obs_a,Ana,2024-05-11T09:12,"Quebrada de Macul, Peñalolén",Loica común,Leistes loyca,confirmed,2,Perched,Shrubland / matorral,"con ""comillas""",2024-05-11T13:00:00Z,2024-05-11T13:00:00Z\n'
                            "obs_b,Ana,2024-05-11T09:30,,Ave rarísima,,tentative,,,,,2024-05-11T13:00:00Z,2024-05-11T13:00:00Z\n",
                            encoding="utf-8")
        s = import_csv(self.con, csv_path)
        self.assertEqual((s["new"], s["unknown_species"]), (2, {"Ave rarísima": 1}))
        a = self.con.execute("SELECT * FROM observations WHERE observation_id = 'obs_a'").fetchone()
        self.assertEqual((a["place"], a["behavior"], a["habitat"], a["notes"], a["count"]),
                         ("Quebrada de Macul, Peñalolén", "Posado", "Matorral", 'con "comillas"', 2))
        self.assertIsNotNone(a["species_id"])
        self.assertEqual(import_csv(self.con, csv_path)["unchanged"], 2)
        # Newer edit wins
        csv_path.write_text(header + "obs_a,Ana,2024-05-11T09:12,,Diuca común,Diuca diuca,confirmed,3,,,,2024-05-11T13:00:00Z,2024-06-01T00:00:00Z\n",
                            encoding="utf-8")
        self.assertEqual(import_csv(self.con, csv_path)["updated"], 1)
        self.assertEqual(self.con.execute("SELECT species_text FROM observations WHERE observation_id = 'obs_a'").fetchone()[0], "Diuca común")
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM identifications WHERE observation_id = 'obs_a'").fetchone()[0], 2)


class HelpersTest(unittest.TestCase):
    def test_norm(self):
        self.assertEqual(norm("Fío Fío"), norm("Fío-fío"))
        self.assertEqual(norm("  Cuervo de Pantano Común "), "cuervo de pantano comun")

    def test_gps(self):
        self.assertEqual(gps_to_decimal((33, 26, 24.0), "S"), -33.44)
        self.assertEqual(gps_to_decimal((70, 39, 0), "W"), -70.65)

    def test_mtime_fallback(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "sin_fecha.jpg"
            make_photo(p, None)
            self.assertEqual(read_photo_info(p).taken_at_source, "file-mtime")


if __name__ == "__main__":
    unittest.main()
