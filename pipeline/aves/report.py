"""Resumen legible del contenido de la base de datos."""
import sqlite3

STATUS_ES = {"confirmed": "confirmadas", "tentative": "tentativas", "unidentified": "sin identificar"}


def summary(con: sqlite3.Connection) -> str:
    q = lambda sql, *a: con.execute(sql, a).fetchall()
    one = lambda sql, *a: con.execute(sql, a).fetchone()[0]
    out = []

    n_obs = one("SELECT COUNT(*) FROM observations")
    by_status = dict(q("SELECT status, COUNT(*) FROM observations GROUP BY status"))
    by_origin = dict(q("SELECT origin, COUNT(*) FROM observations GROUP BY origin"))
    n_species = one("SELECT COUNT(DISTINCT species_id) FROM observations WHERE status = 'confirmed' AND species_id IS NOT NULL")
    out.append(f"Observaciones: {n_obs}  (desde fotos: {by_origin.get('photos', 0)}, desde la web: {by_origin.get('web', 0)})")
    out.append("  " + " · ".join(f"{STATUS_ES[s]}: {by_status.get(s, 0)}" for s in STATUS_ES))
    out.append(f"Especies confirmadas: {n_species}")

    n_media = one("SELECT COUNT(*) FROM media WHERE missing = 0")
    src = dict(q("SELECT taken_at_source, COUNT(*) FROM media WHERE missing = 0 GROUP BY taken_at_source"))
    gps = one("SELECT COUNT(*) FROM media WHERE missing = 0 AND latitude IS NOT NULL")
    missing = one("SELECT COUNT(*) FROM media WHERE missing = 1")
    out.append(f"Fotos: {n_media}  (fecha desde EXIF: {src.get('exif', 0)}, nombre de archivo: {src.get('filename', 0)}, "
               f"fecha del archivo: {src.get('file-mtime', 0)}; con GPS: {gps})")
    if missing:
        out.append(f"  ⚠ {missing} fotos ya no están en disco")

    rows = q("""SELECT s.common_name, s.scientific_name, COUNT(DISTINCT o.observation_id) AS n,
                       COUNT(m.media_id) AS fotos, MIN(o.datetime) AS primera, MAX(o.datetime) AS ultima
                FROM observations o JOIN species s USING (species_id)
                LEFT JOIN media m ON m.observation_id = o.observation_id AND m.missing = 0
                WHERE o.status = 'confirmed' GROUP BY s.species_id ORDER BY n DESC, s.taxon_order""")
    if rows:
        out.append("")
        out.append(f"{'Especie':<28} {'Obs.':>5} {'Fotos':>6}   Primera → última")
        for r in rows:
            out.append(f"{r['common_name']:<28} {r['n']:>5} {r['fotos']:>6}   {(r['primera'] or '')[:10]} → {(r['ultima'] or '')[:10]}")

    pending = q("""SELECT COALESCE(NULLIF(o.photo_folder, ''), '(sueltas)') AS carpeta, COUNT(DISTINCT o.observation_id) AS n,
                          COUNT(m.media_id) AS fotos
                   FROM observations o LEFT JOIN media m ON m.observation_id = o.observation_id AND m.missing = 0
                   WHERE o.review_flag = 1 GROUP BY carpeta ORDER BY fotos DESC""")
    if pending:
        out.append("")
        out.append("Pendientes de revisión:")
        for r in pending:
            out.append(f"  {r['carpeta']:<26} {r['n']:>4} obs. · {r['fotos']} fotos")
    return "\n".join(out)
