# Formato de datos

## Observaciones (CSV)

La web exporta un CSV en UTF-8 **con BOM** (para que Excel muestre bien las tildes). En Python se lee con `encoding="utf-8-sig"`. El orden de las columnas es estable, y las columnas nuevas se agregan siempre al final.

| Columna | Descripción |
|---|---|
| `observation_id` | ID único (`obs_<timestamp36>_<aleatorio>`). Es la clave para combinar archivos. |
| `observer` | Nombre del observador |
| `datetime` | Fecha y hora local de la observación, `YYYY-MM-DDTHH:MM` |
| `place` | Nombre del lugar (texto libre) |
| `latitude`, `longitude` | Grados decimales (WGS84), 6 decimales. Vacíos si no se capturó el GPS. |
| `gps_accuracy_m` | Precisión reportada por el GPS, en metros |
| `species` | Nombre común (de `chile_birds.json` o texto libre) |
| `scientific_name` | Nombre científico. Vacío si la especie no está en la lista. |
| `status` | `confirmed` · `tentative` · `unidentified` |
| `count` | Número de individuos (vacío = no contado) |
| `behavior` | Lista separada por `; ` (Posado, Cantando, …) |
| `habitat` | Un valor (Bosque, Matorral, Humedal, …) |
| `weather` | Texto libre |
| `notes` | Texto libre |
| `photo_files`, `audio_files` | Nombres de archivo separados por `; ` (los archivos quedan en OneDrive) |
| `id_source` | `manual` · más adelante `image-model` / `audio-model` |
| `id_confidence` | Confianza del modelo (0–1). Vacío si la identificación es manual. |
| `review_flag` | `1` = requiere revisión (tentativa o sin ID), `0` = confirmada |
| `created_at`, `updated_at` | ISO 8601 UTC. `updated_at` decide qué versión gana al combinar archivos. |

### Combinar archivos

Al importar o enlazar un CSV, las filas se combinan por `observation_id`:

- Las filas con un ID nuevo se agregan.
- Si el ID ya existe, gana la fila con `updated_at` más reciente.

**Limitación conocida:** las eliminaciones no se propagan. Si borras una observación en el celular pero ya estaba en el archivo maestro, reaparecerá al importar. Hay que borrarla también en el computador.

### Compatibilidad

La web también importa CSV de la versión anterior (`field-note.html`, en inglés). Los valores de comportamiento y hábitat en inglés se traducen automáticamente.

## Especies (`web/data/chile_birds.json`)

Hay 565 especies en orden taxonómico. Cada entrada tiene:

- `c`: nombre común en español
- `s`: nombre científico
- `t` (opcional): nota del listado original para especies de islas oceánicas (`E-Ins`, `A-Ins`, `H-Ins`, `Ins`)

Esta es la lista cerrada de candidatos para la identificación automática (fases 4+).
