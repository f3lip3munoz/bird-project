# Libreta de Aves 🐦

Base de datos personal de observaciones de aves de Chile y, más adelante, un asistente de identificación por foto y audio. El contexto completo está en [docs/project-brief.md](docs/project-brief.md).

## Libreta de campo (web)

**App:** https://f3lip3munoz.github.io/bird-project/

Es una aplicación web instalable (PWA) para anotar observaciones en terreno:

- Buscador de las 565 especies de Chile, sin importar tildes y por nombre común o científico
- Estado de identificación (confirmada / tentativa / sin identificar), número de individuos, comportamiento, hábitat y clima
- GPS del dispositivo, que funciona sin señal de datos
- **Funciona sin conexión** una vez abierta por primera vez
- Registro con búsqueda y filtros, y una lista de vida por especie
- Exportar/importar CSV y, en Chrome/Edge de computador, guardado automático en un archivo enlazado

Las observaciones **no se suben a ningún servidor**: quedan en el navegador de cada dispositivo y se respaldan como CSV en OneDrive. Ver [docs/data-format.md](docs/data-format.md).

### Instalar en el celular

- **Android (Chrome):** abre la URL, luego ⋮ → *Instalar app*, o usa el botón en la sección *Datos*.
- **iPhone (Safari):** abre la URL, luego *Compartir* → *Agregar a pantalla de inicio*.

### Desarrollo local

No hay paso de compilación: es HTML, CSS y JavaScript sin dependencias.

```bash
python -m http.server 8765 --directory web
```

Luego abre http://localhost:8765. En `localhost` el service worker está desactivado para que los cambios se vean al instante; agrega `?sw` a la URL para probar el modo sin conexión.

Al publicar cambios en archivos de `web/`, sube `VERSION` en [web/sw.js](web/sw.js) para que los dispositivos instalados se actualicen.

## Base de datos (Python)

La carpeta `pipeline/` contiene el paquete `aves`, que junta en una base SQLite (`Bird-Project/db/aves.sqlite`, en OneDrive) las observaciones de la web y las fotos ordenadas en `Bird-Project/Aves/`. Sus tablas y reglas están en [docs/database.md](docs/database.md).

```bash
python -m pip install -e pipeline
python -m aves init --bird-project "C:/Users/felip/OneDrive - Universidad Católica de Chile/Bird-Project" --observador "Felipe Muñoz"
python -m aves actualizar
```

`actualizar` importa `Bird-Project/observations.csv` (si existe) y las fotos, y luego muestra un resumen. Se puede repetir las veces que quieras: solo entra lo nuevo, y si mueves una foto de `Revisión/` a la carpeta de una especie, se reasigna sola.

Pruebas: `python -m unittest discover -s pipeline/tests`

## Estructura

```
web/                 App web (se publica en GitHub Pages)
  data/chile_birds.json   Lista de especies de Chile (fuente única)
docs/                Brief, formato de datos y decisiones del proyecto
pipeline/            Paquete Python `aves` (SQLite, importadores) y carpetas.csv
tools/               Scripts auxiliares (íconos)
.github/workflows/   Publicación automática en GitHub Pages
```

Las **fotos, audios y CSV de observaciones no van en este repositorio**. Viven en la carpeta `Bird-Project` de OneDrive.

## Hoja de ruta

- [x] Fase 0: repositorio y publicación
- [x] Fase 1: libreta de campo web (PWA sin conexión)
- [x] Fase 2: respaldo por CSV, sin servidor
- [x] Fase 3: base de datos SQLite e importador en Python
- [ ] Fase 4: clasificar las fotos sin ordenar por similitud con las ya ordenadas (ver docs/decisions.md)
- [ ] Fase 5+: BirdNET (audio), interfaz de revisión y detector en vivo
