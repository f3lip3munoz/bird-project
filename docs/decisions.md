# Decisiones del proyecto

Registro breve de decisiones de arquitectura, para retomar el trabajo entre sesiones.

## 2026-09-23: Repositorio en GitHub, medios en OneDrive

- El código vive en GitHub (`f3lip3munoz/bird-project`, público) y está clonado **fuera** de OneDrive (`C:\Users\felip\code\bird-project`), porque la sincronización de OneDrive y la carpeta `.git` no se llevan bien.
- Las fotos, los audios y los CSV de observaciones se quedan en `OneDrive/Bird-Project` y nunca se suben al repositorio. `.gitignore` los excluye por si acaso. Motivos: el tamaño (~2 GB de fotos) y la privacidad (coordenadas GPS).

## 2026-09-23: Libreta de campo como PWA estática, sin framework

- Usa HTML, CSS y JS (módulos ES) sin paso de compilación. Es simple de mantener y GitHub Pages lo sirve directo.
- Un service worker con caché versionada permite usarla sin conexión en terreno. Hay que subir `VERSION` en `web/sw.js` en cada cambio.
- Se publica en GitHub Pages mediante GitHub Actions (`.github/workflows/pages.yml`), que sube solo la carpeta `web/`.

## 2026-09-23: Observaciones sin servidor (opción a)

- Los datos se guardan en `localStorage` en cada dispositivo. Se pide almacenamiento persistente (`navigator.storage.persist()`).
- El respaldo y la sincronización se hacen por CSV:
  - En el celular se exporta y comparte el CSV a OneDrive (`Bird-Project/entrada/`).
  - En el computador (Chrome/Edge) se enlaza `Bird-Project/observations.csv` como archivo maestro con la File System Access API. Cada cambio se escribe ahí, y los CSV del celular se importan y combinan por ID.
- La app avisa cuando hay cambios sin exportar.
- Pasar a un backend (por ejemplo, Supabase) queda como opción si la sincronización manual se vuelve molesta.

## 2026-09-23: Lista de especies

- `web/data/chile_birds.json` es la fuente única. Viene de `chile_birds.json` original, con cuatro errores de tipeo corregidos (rojiza, Pilpilén, Gaviotín, Pacífico) y las notas de islas (`E-Ins`, etc.) movidas del nombre a un campo `t`.
