-- Esquema de la base de datos de observaciones (versión 1).
-- Fechas locales como texto ISO 'YYYY-MM-DDTHH:MM[:SS]'; marcas de sistema en UTC ISO 8601.

CREATE TABLE species (
    species_id      INTEGER PRIMARY KEY,
    taxon_order     INTEGER NOT NULL,          -- orden en chile_birds.json (taxonómico)
    common_name     TEXT NOT NULL UNIQUE,
    scientific_name TEXT NOT NULL UNIQUE,
    note            TEXT                       -- E-Ins, A-Ins, ... (islas oceánicas)
);

CREATE TABLE observations (
    observation_id  TEXT PRIMARY KEY,          -- obs_… (web) o foto_… (importada de fotos)
    origin          TEXT NOT NULL CHECK (origin IN ('web', 'photos')),
    photo_folder    TEXT,                      -- carpeta de origen dentro de Aves/ (solo origin='photos')
    observer        TEXT,
    datetime        TEXT,
    place           TEXT,
    latitude        REAL,
    longitude       REAL,
    gps_accuracy_m  REAL,
    species_id      INTEGER REFERENCES species(species_id),
    species_text    TEXT,                      -- nombre tal como se ingresó (puede no estar en la lista)
    status          TEXT NOT NULL CHECK (status IN ('confirmed', 'tentative', 'unidentified')),
    count           INTEGER,
    behavior        TEXT,
    habitat         TEXT,
    weather         TEXT,
    notes           TEXT,
    photo_files     TEXT,                      -- nombres de archivo anotados en la web (texto)
    audio_files     TEXT,
    id_source       TEXT,                      -- manual | image-model | audio-model
    id_confidence   REAL,
    review_flag     INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE INDEX idx_obs_species ON observations(species_id);
CREATE INDEX idx_obs_datetime ON observations(datetime);
CREATE INDEX idx_obs_folder ON observations(photo_folder);

CREATE TABLE media (
    media_id        INTEGER PRIMARY KEY,
    observation_id  TEXT REFERENCES observations(observation_id) ON DELETE SET NULL,
    kind            TEXT NOT NULL CHECK (kind IN ('photo', 'audio')),
    rel_path        TEXT NOT NULL UNIQUE,      -- relativa a la carpeta Bird-Project, con '/'
    folder          TEXT NOT NULL,             -- primera carpeta bajo Aves/ ('' = sueltas en Aves/)
    file_name       TEXT NOT NULL,
    size_bytes      INTEGER NOT NULL,
    mtime_ns        INTEGER NOT NULL,
    sha256          TEXT NOT NULL,
    taken_at        TEXT,
    taken_at_source TEXT CHECK (taken_at_source IN ('exif', 'filename', 'file-mtime')),
    latitude        REAL,
    longitude       REAL,
    camera          TEXT,
    width           INTEGER,
    height          INTEGER,
    missing         INTEGER NOT NULL DEFAULT 0, -- 1 = el archivo ya no está en disco
    imported_at     TEXT NOT NULL
);
CREATE INDEX idx_media_obs ON media(observation_id);
CREATE INDEX idx_media_sha ON media(sha256);
CREATE INDEX idx_media_folder ON media(folder, taken_at);

-- Historial de identificaciones: quién/qué propuso cada especie y si se aceptó.
CREATE TABLE identifications (
    identification_id INTEGER PRIMARY KEY,
    observation_id  TEXT NOT NULL REFERENCES observations(observation_id) ON DELETE CASCADE,
    media_id        INTEGER REFERENCES media(media_id) ON DELETE SET NULL,
    species_id      INTEGER REFERENCES species(species_id),
    species_text    TEXT,
    source          TEXT NOT NULL,             -- manual | folder | image-model | audio-model
    confidence      REAL,
    status          TEXT NOT NULL CHECK (status IN ('suggested', 'accepted', 'rejected')),
    note            TEXT,
    created_at      TEXT NOT NULL
);
CREATE INDEX idx_ident_obs ON identifications(observation_id);

CREATE TABLE imports (
    import_id       INTEGER PRIMARY KEY,
    kind            TEXT NOT NULL,             -- csv | photos
    source          TEXT NOT NULL,
    started_at      TEXT NOT NULL,
    stats           TEXT                       -- JSON
);
