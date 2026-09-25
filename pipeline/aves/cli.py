"""Interfaz de línea de comandos:  aves <comando>

  aves init --bird-project RUTA [--observador NOMBRE]
  aves importar-csv [ARCHIVO.csv ...]     (por defecto Bird-Project/observations.csv)
  aves importar-fotos [--ventana 30]
  aves actualizar                         (CSV + fotos + resumen)
  aves resumen
"""
import argparse
from contextlib import closing
import sys
from pathlib import Path

from . import config
from .db import backup, connect
from .import_csv import import_csv
from .import_photos import DEFAULT_GAP_MIN, import_photos
from .report import summary
from .species import load_species


def _open(cfg: config.Config, make_backup: bool):
    if make_backup and (dest := backup(cfg.db_path)):
        print(f"Respaldo: {dest.name}")
    con = connect(cfg.db_path)
    if not con.execute("SELECT COUNT(*) FROM species").fetchone()[0]:
        load_species(con)
    return con


def cmd_init(args):
    root = Path(args.bird_project).expanduser().resolve()
    if not (root / "Aves").is_dir():
        sys.exit(f"No encuentro la carpeta Aves dentro de {root}")
    config.write_config(root, args.observador or "")
    cfg = config.load_config()
    con = connect(cfg.db_path)
    n = load_species(con)
    print(f"Configuración guardada en {config.CONFIG_PATH}")
    print(f"Base de datos: {cfg.db_path}  ({n} especies cargadas)")


def _csv(con, paths):
    for p in paths:
        if not p.exists():
            print(f"(no existe {p}, se omite)")
            continue
        s = import_csv(con, p)
        print(f"CSV {p.name}: {s.get('new', 0)} nuevas, {s.get('updated', 0)} actualizadas, {s.get('unchanged', 0)} sin cambios")
        if s["unknown_species"]:
            print("  Especies que no están en la lista de Chile (quedan como texto):",
                  ", ".join(f"{k} ({v})" for k, v in s["unknown_species"].items()))


def _photos(con, cfg, gap):
    print(f"Revisando fotos en {cfg.photos_dir} … (la primera vez OneDrive puede tardar en descargarlas)")
    s = import_photos(con, cfg.bird_project, config.load_folder_map(), cfg.observer, gap)
    print(f"Fotos: {s.get('new', 0)} nuevas, {s.get('moved', 0)} movidas, {s.get('updated', 0)} modificadas, "
          f"{s.get('unchanged', 0)} sin cambios, {s.get('missing', 0)} eliminadas")
    print(f"Observaciones: {s['observations_created']} creadas, {s['observations_removed']} eliminadas (quedaron vacías), "
          f"{s['species_changed']} con especie reasignada")
    if s["unmapped_folders"]:
        print("⚠ Carpetas sin especie reconocida (se omitieron). Agrégalas a pipeline/carpetas.csv:")
        for f in s["unmapped_folders"]:
            print(f"    {f}")


def cmd_importar_csv(args):
    cfg = config.load_config()
    with closing(_open(cfg, True)) as con:
        _csv(con, [Path(p) for p in args.archivos] or [cfg.observations_csv])


def cmd_importar_fotos(args):
    cfg = config.load_config()
    with closing(_open(cfg, True)) as con:
        _photos(con, cfg, args.ventana)


def cmd_actualizar(args):
    cfg = config.load_config()
    with closing(_open(cfg, True)) as con:
        _csv(con, [cfg.observations_csv])
        _photos(con, cfg, args.ventana)
        print()
        print(summary(con))


def cmd_resumen(args):
    cfg = config.load_config()
    with closing(_open(cfg, False)) as con:
        print(summary(con))


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except AttributeError:
            pass
    ap = argparse.ArgumentParser(prog="aves", description="Base de datos de observaciones de aves de Chile")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="configura la ruta de Bird-Project y crea la base de datos")
    p.add_argument("--bird-project", required=True, help="carpeta Bird-Project de OneDrive")
    p.add_argument("--observador", help="nombre para las observaciones importadas desde fotos")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("importar-csv", help="importa CSV exportados por la libreta web")
    p.add_argument("archivos", nargs="*")
    p.set_defaults(fn=cmd_importar_csv)

    for name, fn, help_ in (("importar-fotos", cmd_importar_fotos, "importa y agrupa las fotos de Aves/"),
                            ("actualizar", cmd_actualizar, "observations.csv + fotos + resumen")):
        p = sub.add_parser(name, help=help_)
        p.add_argument("--ventana", type=int, default=DEFAULT_GAP_MIN, help="minutos para agrupar fotos (30)")
        p.set_defaults(fn=fn)

    sub.add_parser("resumen", help="muestra el contenido de la base").set_defaults(fn=cmd_resumen)

    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
