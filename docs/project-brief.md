# Project Brief: Chilean Bird Observation Database & Identification Assistant

Use this as the guiding prompt/context for an AI assistant (e.g. Claude Code, ChatGPT, or any coding agent) working on this project across sessions.

---

## Project overview

I'm building a personal database of bird observations from Chile. Each observation may include one or more of:
- **Photos** of the bird
- **Audio recordings** of bird calls/song
- **Written notes** (location, behavior, habitat, date/time, etc.)

The long-term goal has two parts:
1. A well-organized, queryable database of my observations.
2. Automating species identification where possible — both from photos and from audio — eventually culminating in a **standalone audio bird detector** that can listen to a recording (or live audio) and flag which species are present.

## Scope constraint

This is a **Chile-specific** project. Species candidates, reference taxonomy, and any pretrained models should be filtered/prioritized to birds found in Chile (~500 species) rather than global species lists, to reduce false positives and keep results relevant.

## Core data model (per observation)

- `observation_id`
- `datetime`
- `location` (place name + optional lat/long)
- `species` — with a status: `confirmed` / `tentative` / `unidentified`
- `id_confidence` (if auto-identified) and `id_source` (manual / image-model / audio-model)
- `photo_paths[]`
- `audio_paths[]`
- `notes` (free text)
- `review_flag` (needs human review vs. confirmed)

## Suggested technical approach (adjust as needed)

**Storage:** SQLite (simplest, local, no server) with a media folder structure alongside it, or Postgres if it needs to grow. Avoid cloud dependencies unless explicitly requested.

**Species reference list:** Use a Chile checklist (e.g. eBird/Clements Chile taxonomy, or the list maintained by Chile's birding community — ROC / Red de Observadores de Aves) as the closed set of candidate species for classification, instead of a global list.

**Image identification:** Start with an existing pretrained computer-vision model (e.g. iNaturalist's vision API, or a similar bird-focused classifier) as a first-pass suggestion, rather than training a model from scratch. Store its confidence score and always allow manual correction — corrections should be logged so the system improves over time.

**Audio identification / detector:** This is the most tractable "automate it" piece. **BirdNET-Analyzer** (open-source, pretrained, includes South American/Chilean species) is the standard tool for this: it can scan an audio file and output detected species + timestamps + confidence. Two stages:
1. **Batch mode** — run BirdNET over existing/incoming audio recordings and auto-populate candidate species for each observation (still flagged for human review).
2. **Live/continuous detector** (the "audio bird detector" end goal) — capture from a microphone, run a rolling BirdNET (or similar) inference, and log/alert on detections in real time.

**Human-in-the-loop by design:** every automated identification (image or audio) is a *suggestion* with a confidence score and a review flag — never silently auto-confirmed. This keeps the database trustworthy and gives labeled data to improve accuracy later.

## Suggested build order

1. Design and implement the database schema + folder conventions for media.
2. Build simple ingestion (script or small UI) to log a new observation with photos/notes/audio.
3. Integrate BirdNET-Analyzer in batch mode for audio → candidate species.
4. Integrate an image-ID model for photos → candidate species.
5. Build a lightweight review interface (confirm/reject/correct candidate IDs).
6. Build the live/continuous audio detector.
7. Iterate based on real observation data and correction history.

## How I want the AI to work with me

- Default to open-source, locally-runnable tools; don't assume cloud services unless I ask.
- Prefer Python for the pipeline/backend.
- Before big architecture decisions (e.g., choice of DB, UI framework), briefly check in rather than assuming.
- Keep the species list and any model choices Chile-specific, not global defaults.
- Document schema and pipeline decisions as the project evolves, since this will be built incrementally across sessions.
