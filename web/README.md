# SPHEREx Sky Diary — Web Frontend

Static Next.js web application consuming `data/output/candidates.json` and `data/output/cutouts/`.

## Architecture
- Reads static JSON files produced by the offline Python pipeline (`schema_version: "1.0"`).
- Zero heavy processing in the browser or at request time.
- Integrated Aladin Lite interactive sky viewer.
- Displays "TEST DATA" badge when `is_synthetic: true`.
