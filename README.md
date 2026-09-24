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

## Estructura

```
web/                 App web (se publica en GitHub Pages)
  data/chile_birds.json   Lista de especies de Chile (fuente única)
docs/                Brief, formato de datos y decisiones del proyecto
tools/               Scripts auxiliares (íconos)
.github/workflows/   Publicación automática en GitHub Pages
```

Las **fotos, audios y CSV de observaciones no van en este repositorio**. Viven en la carpeta `Bird-Project` de OneDrive.

## Hoja de ruta

- [x] Fase 0: repositorio y publicación
- [x] Fase 1: libreta de campo web (PWA sin conexión)
- [x] Fase 2: respaldo por CSV, sin servidor
- [ ] Fase 3: base de datos SQLite e importador en Python
- [ ] Fase 4+: BirdNET (audio), identificación por imagen, revisión y detector en vivo
