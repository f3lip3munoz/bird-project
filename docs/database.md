# Base de datos (`aves.sqlite`)

Es un archivo SQLite en `Bird-Project/db/aves.sqlite`. Antes de cada importación se guarda un respaldo en `db/respaldos/` (se conservan los 10 más recientes). Se puede abrir con [DB Browser for SQLite](https://sqlitebrowser.org/).

> **No abrirla desde dos computadores a la vez**: OneDrive podría crear copias en conflicto.

## Tablas

| Tabla | Una fila por… |
|---|---|
| `species` | especie de Chile (565, en orden taxonómico) |
| `observations` | avistamiento. `origin` = `web` (libreta) o `photos` (creado a partir de fotos) |
| `media` | archivo de foto, con ruta relativa a `Bird-Project`, hash SHA-256 y datos EXIF (fecha, GPS, cámara) |
| `identifications` | propuesta de especie: quién o qué la hizo (`manual`, `folder`, `image-model`, `audio-model`), con qué confianza y si se aceptó |
| `imports` | ejecución de un importador (para auditoría) |

El esquema completo está en [pipeline/aves/schema.sql](../pipeline/aves/schema.sql).

## Reglas de importación de fotos

1. **La especie sale de la carpeta.** Se usa la primera carpeta bajo `Aves/`: primero se busca en [pipeline/carpetas.csv](../pipeline/carpetas.csv) y, si no está ahí, una especie con el mismo nombre (sin importar mayúsculas, tildes ni guiones). Las carpetas que no se reconocen se omiten y aparecen en un aviso.
2. **Las fotos de carpetas de especie quedan confirmadas.** Las de `Revisión`, `Desconocidos` y las sueltas en `Aves/` quedan como *sin identificar* y marcadas para revisión. `Varias aves` (`#varias-aves`) también queda para revisión, con una nota.
3. **Agrupación en observaciones:** las fotos de la misma carpeta separadas por 30 minutos o menos forman una sola observación. La ventana se cambia con `--ventana`.
4. **Fecha de cada foto:** se toma del EXIF (`DateTimeOriginal`). Si no está, se saca del nombre del archivo (`20230214_192906`) y, como último recurso, de la fecha de modificación del archivo.
5. **Se puede repetir sin problemas:**
   - Los archivos sin cambios (mismo tamaño y fecha) se saltan.
   - Un archivo movido de carpeta se reconoce por su hash: cambia de observación y hereda la especie de la nueva carpeta.
   - Las observaciones que quedan vacías se eliminan.
   - Los archivos borrados se marcan con `missing = 1`.
6. **Cambiar una equivalencia** en `carpetas.csv` reasigna las observaciones de esa carpeta y deja el cambio registrado en `identifications`.

## Consultas útiles

```sql
-- Fotos pendientes de ordenar
SELECT rel_path, taken_at FROM media m JOIN observations o USING (observation_id)
WHERE o.review_flag = 1 ORDER BY taken_at;

-- Especies por mes
SELECT substr(datetime, 6, 2) AS mes, species_text, COUNT(*) FROM observations
WHERE status = 'confirmed' GROUP BY mes, species_text ORDER BY mes;
```
