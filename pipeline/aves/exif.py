"""Lectura de metadatos de fotos: fecha de captura, GPS, cámara y dimensiones."""
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PIL import ExifTags, Image

TAG_DATETIME = 306            # IFD0 DateTime (última modificación en cámara)
TAG_MAKE, TAG_MODEL = 271, 272
TAG_DATETIME_ORIGINAL = 36867  # Exif IFD DateTimeOriginal (momento de la toma)

# 20230214_192906.jpg, IMG_20230214_192906.jpg, PXL_20230214_192906123.jpg
FILENAME_DT = re.compile(r"(20\d{2})(\d{2})(\d{2})[_-](\d{2})(\d{2})(\d{2})")


@dataclass
class PhotoInfo:
    taken_at: str
    taken_at_source: str  # exif | filename | file-mtime
    latitude: float | None = None
    longitude: float | None = None
    camera: str | None = None
    width: int | None = None
    height: int | None = None


def _exif_datetime(value) -> str | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value).strip("\x00 ")[:19], "%Y:%m:%d %H:%M:%S").isoformat()
    except ValueError:
        return None


def gps_to_decimal(dms, ref) -> float | None:
    """Convert EXIF (deg, min, sec) rationals + N/S/E/W reference to decimal degrees."""
    try:
        d, m, s = (float(x) for x in dms)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    value = d + m / 60 + s / 3600
    if str(ref).upper().startswith(("S", "W")):
        value = -value
    return round(value, 6)


def read_photo_info(path: Path) -> PhotoInfo:
    taken, source = None, None
    lat = lon = None
    camera = width = height = None
    try:
        with Image.open(path) as im:
            width, height = im.size
            exif = im.getexif()
            taken = _exif_datetime(exif.get_ifd(ExifTags.IFD.Exif).get(TAG_DATETIME_ORIGINAL)) \
                or _exif_datetime(exif.get(TAG_DATETIME))
            if taken:
                source = "exif"
            gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
            if gps.get(2) and gps.get(4):
                lat, lon = gps_to_decimal(gps[2], gps.get(1, "N")), gps_to_decimal(gps[4], gps.get(3, "E"))
                if lat is None or lon is None or (lat == 0 and lon == 0):
                    lat = lon = None
            make, model = (str(exif.get(t) or "").strip("\x00 ") for t in (TAG_MAKE, TAG_MODEL))
            camera = (model if make and model.lower().startswith(make.lower().split()[0]) else f"{make} {model}").strip() or None
    except (OSError, SyntaxError, ValueError):
        pass  # unreadable image: fall back to the file name / modification time below

    if not taken and (m := FILENAME_DT.search(path.name)):
        y, mo, d, h, mi, s = m.groups()
        try:
            taken, source = datetime(int(y), int(mo), int(d), int(h), int(mi), int(s)).isoformat(), "filename"
        except ValueError:
            pass
    if not taken:
        taken, source = datetime.fromtimestamp(path.stat().st_mtime).replace(microsecond=0).isoformat(), "file-mtime"

    return PhotoInfo(taken, source, lat, lon, camera, width, height)
