# SPHEREx Sky Diary — NASA Space Apps Challenge 2026
**Challenge:** Planet X and SPHEREx  
**Contract Version:** `1.0` (Defined in [`docs/schema.json`](file:///docs/schema.json))

---

## Overview

**SPHEREx Sky Diary** is a public scientific web tool enabling astronomers and citizen scientists to enter celestial coordinates (RA/Dec) or target names to:
1. View a multi-epoch time-lapse of SPHEREx infrared sky images for that sky patch.
2. Inspect automatically detected moving Solar System objects (asteroids, comets, Centaurs, TNOs, Planet X candidates).
3. Distinguish **Known** cataloged bodies from newly discovered **Unknown** movers.
4. Explore extracted 102-channel SPHEREx reflectance spectra (0.75 – 5.0 µm) with characteristic solar-reflectance and absorption features.

---

## Architecture

The project follows a decoupled, static-file architecture:
- **Offline Python Pipeline:** Runs scientific processing offline (source extraction, difference imaging, track linking, ephemeris matching, spectral extraction). Writes static files:
  - `data/output/candidates.json` (strict `schema_version: "1.0"`)
  - `data/output/cutouts/*.png` (postage-stamp image cutouts)
- **Static Web Frontend (Next.js):** Pure consumer of static files. Zero heavy computation or DB at request time.
- **Contract Enforcement:** Every pipeline stage adheres to `docs/schema.json`. Format breaks fail loudly.

---

## Monorepo Folder Map

```
spherex-sky-diary/
├── config/             # YAML configuration (data_source: mock | irsa, sky regions, seed)
│   └── settings.yaml
├── data/
│   ├── mock/           # Reproducible synthetic mock generator
│   │   └── generate_mock.py
│   └── output/         # Generated candidate catalogs and image cutouts
│       ├── candidates.json
│       └── cutouts/
├── detection/          # Source extraction and mover trajectory linking
├── docs/               # Contract schema, specification, and validator
│   ├── CONTRACT.md     # Plain-language specification and full JSON example
│   ├── schema.json     # JSON Schema Draft 2020-12
│   └── validate.py     # Schema and domain invariant validation CLI / helper
├── matching/           # Ephemeris matching (IMCCE SkyBoT / JPL Horizons)
├── spectra/            # 102-channel spectral extraction and classification
├── tests/              # Pytest test suite covering schema, invariants, and mocks
│   └── test_schema.py
├── web/                # Next.js web application
├── Makefile            # Standard execution targets
├── pyproject.toml      # Pinned Python package dependencies
├── requirements.txt    # Pinned requirements
└── README.md
```

---

## Getting Started

### 1. Prerequisites
- Python 3.11+
- Node.js 18+ (for web UI)

### 2. Setup
Install Python dependencies:
```bash
make setup
# or: pip install -r requirements.txt
```

### 3. Generate Mock Data
Synthesize ~25 reproducible moving objects, 102-channel spectra, and cutout stamps:
```bash
make mock
# or: python data/mock/generate_mock.py
```

### 4. Validate Contract
Verify any candidate file against the JSON Schema and domain invariants:
```bash
python docs/validate.py data/output/candidates.json
```

### 5. Run Test Suite
Execute the pytest suite:
```bash
make test
# or: pytest tests/
```

### 6. Launch Web App
Start the local frontend server:
```bash
make web
# or: npm run dev
```

---

## Key Development Rules

1. **SPHEREx File Handling:** Real SPHEREx FITS layouts are unverified until data release. Never invent FITS extension names. Isolate all I/O in the data adapter and label assumptions with `TODO(VERIFY)`.
2. **Data Transparency:** All synthetic data must have `is_synthetic: true` and display the **TEST DATA** badge in the UI.
3. **Data Source Toggle:** A single switch in `config/settings.yaml` (`data_source: mock | irsa`) toggles mock vs real data.
4. **Contract Invariant:** Schema version `1.0` is strictly enforced. Never modify schema structure without bumping the version.
