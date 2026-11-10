# SPHEREx Sky Diary — Data Contract Specification

**Contract Version:** `1.0`  
**JSON Schema:** [`schema.json`](file:///docs/schema.json) (Draft 2020-12)  
**Status:** Frozen for Module 0  

---

## 1. Architectural Overview

The **SPHEREx Sky Diary** operates on a decoupled, static-file architecture:

1. **Offline Pipeline (Python):** Ingests SPHEREx sky cubes (or mock generators), performs source extraction, transient/motion tracking, solar system ephemeris matching (IMCCE/SkyBoT/JPL Horizons), and spectral extraction across SPHEREx's 102 spectral channels (0.75 – 5.0 µm).
2. **Static Output Artifacts:** The pipeline writes out:
   - A single unified candidate catalog: `data/output/candidates.json`
   - Cutout image postage stamps: `data/output/cutouts/`
3. **Frontend (Next.js):** Purely static consumer. Reads `candidates.json` and associated cutouts. Performs **no heavy processing** at request time.
4. **Contract Immutability:** Any modification to the data structure requires a version bump (e.g., `1.1` or `2.0`) and team alignment.

---

## 2. Specification & Fields

### Top-Level Properties

| Field | Type | Required | Description / Constraints |
| :--- | :--- | :---: | :--- |
| `schema_version` | `string` | **Yes** | Exact constant `"1.0"`. Format breaks fail loudly. |
| `data_version` | `string` | No | Semantic version or build tag of the dataset (e.g., `"v2026.1-preview"`). |
| `generated_at` | `string` | No | ISO 8601 UTC timestamp of creation (e.g., `"2026-03-29T12:00:00Z"`). |
| `fov_deg` | `number` | No | Field of view size (width/diameter) in degrees (`> 0.0`). |
| `metadata` | `object` | No | Pipeline and matching execution metadata (e.g. `matching_source`). |
| `region` | `object` | **Yes** | Geographic / celestial targeting definition. |
| `epochs` | `array` | **Yes** | Ordered list of observation epochs (`minItems: 1`). |
| `movers` | `array` | **Yes** | List of detected moving objects / track candidates. |

---

### `region` Object

| Field | Type | Required | Description / Constraints |
| :--- | :--- | :---: | :--- |
| `name` | `string` | **Yes** | Sky region descriptor (e.g., `"ecliptic_plane_test"`). |
| `ra_center` | `number` | **Yes** | Right Ascension center (J2000) in degrees (`0.0 <= ra <= 360.0`). |
| `dec_center` | `number` | **Yes** | Declination center (J2000) in degrees (`-90.0 <= dec <= 90.0`). |
| `radius_deg` | `number` | **Yes** | Angular radius in degrees (`> 0.0`). |

---

### `epochs[]` Array Items

| Field | Type | Required | Description / Constraints |
| :--- | :--- | :---: | :--- |
| `epoch_id` | `string` | **Yes** | Identifier for this visit/observation (e.g., `"epoch_01"`). |
| `date` | `string` | **Yes** | Observation timestamp in ISO 8601 format (`YYYY-MM-DDTHH:MM:SSZ`). |
| `band_count` | `integer`| **Yes** | Number of spectral bands observed (typically `102` for full SPHEREx survey). |

---

### `movers[]` Array Items

| Field | Type | Required | Description / Constraints |
| :--- | :--- | :---: | :--- |
| `object_id` | `string` | **Yes** | Unique identifier for the mover candidate (e.g., `"mov_001"`). |
| `ra` | `number` | **Yes** | Reference RA in degrees (`0.0 <= ra <= 360.0`). |
| `dec` | `number` | **Yes** | Reference Dec in degrees (`-90.0 <= dec <= 90.0`). |
| `type` | `string` | **Yes** | Enumeration: `"known"` (matched) or `"unknown"` (unmatched/new candidate). |
| `match_name` | `string \| null` | **Yes** | Name of matched solar system object (e.g., `"(433) Eros"`), or `null` if unknown. |
| `match_distance_arcsec` | `number` | No | Mean positional separation (arcsec) from predicted ephemeris. |
| `matched_epoch_count` | `integer` | No | Number of observation epochs confirming the ephemeris track. |
| `runner_up_match` | `string \| null` | No | Ambiguity resolution runner-up matched body name, or `null`. |
| `confidence` | `number` | **Yes** | Classification confidence score between `0.0` and `1.0`. |
| `is_synthetic` | `boolean` | **Yes** | `true` if synthetic test data. **Mandates "TEST DATA" badge in UI**. |
| `motion` | `object` | **Yes** | Apparent velocity vector. |
| `motion.ra_rate_arcsec_per_day` | `number` | **Yes** | RA apparent motion in arcsec/day ($d\text{RA}/dt \cdot \cos(\text{Dec})$). |
| `motion.dec_rate_arcsec_per_day` | `number` | **Yes** | Dec apparent motion in arcsec/day ($d\text{Dec}/dt$). |
| `detections` | `array` | **Yes** | List of detections across epochs (`minItems: 1`). |
| `spectrum` | `object \| null` | **Yes** | Extracted SPHEREx spectrum or `null`. |

#### `detections[]` Object
- `epoch_id` (`string`): Must correspond to a registered `epoch_id` in top-level `epochs`.
- `date` (`string`): ISO 8601 timestamp.
- `ra` (`number`): Measured RA at this epoch (`0.0` to `360.0`).
- `dec` (`number`): Measured Dec at this epoch (`-90.0` to `90.0`).
- `flux` (`number`): Integrated aperture flux.
- `cutout_url` (`string`): Relative URL/path to postage-stamp image (e.g., `"cutouts/mov_001_epoch_01.png"`).

#### `spectrum` Object (when not null)
- `wavelength_um` (`number[]`): SPHEREx channel wavelengths in micrometers (typically 102 channels from 0.75 µm to 5.0 µm).
- `flux` (`number[]`): Calibrated flux values.
- `flux_err` (`number[]`): 1-sigma uncertainty per wavelength channel.

---

## 3. Supplementary Validation Rules (Enforced in `docs/validate.py`)

JSON Schema (draft 2020-12) handles structural validation, types, numeric ranges, and regex/formats. The following relational and logical invariants are enforced via Python in `docs/validate.py`:

1. **Spectral Array Length Invariant:** If `spectrum` is non-null, `len(wavelength_um) == len(flux) == len(flux_err)`.
2. **Temporal Ordering Invariant:** Within `detections`, items must be sorted in ascending chronological order (`detection[i].date <= detection[i+1].date`).
3. **Epoch Referential Integrity:** Every detection's `epoch_id` must match an existing `epoch_id` declared in the top-level `epochs` list.
4. **Classification Consistency:** If `type == "known"`, `match_name` must be a non-empty string. If `type == "unknown"`, `match_name` must be `null`.

---

## 4. Full Example (`candidates.json`)

```json
{
  "schema_version": "1.0",
  "data_version": "v1.0-mock",
  "generated_at": "2026-03-29T12:00:00Z",
  "fov_deg": 0.2,
  "region": {
    "name": "ecliptic_plane_test",
    "ra_center": 60.0,
    "dec_center": 20.0,
    "radius_deg": 0.2
  },
  "epochs": [
    {
      "epoch_id": "epoch_01",
      "date": "2026-01-15T00:00:00Z",
      "band_count": 102
    },
    {
      "epoch_id": "epoch_02",
      "date": "2026-02-14T12:00:00Z",
      "band_count": 102
    },
    {
      "epoch_id": "epoch_03",
      "date": "2026-03-16T18:00:00Z",
      "band_count": 102
    }
  ],
  "movers": [
    {
      "object_id": "mov_001",
      "ra": 60.0125,
      "dec": 20.0042,
      "type": "known",
      "match_name": "99942 Apophis",
      "confidence": 0.98,
      "is_synthetic": true,
      "motion": {
        "ra_rate_arcsec_per_day": 24.5,
        "dec_rate_arcsec_per_day": -12.1
      },
      "detections": [
        {
          "epoch_id": "epoch_01",
          "date": "2026-01-15T00:00:00Z",
          "ra": 59.9980,
          "dec": 20.0112,
          "flux": 142.5,
          "cutout_url": "cutouts/mov_001_epoch_01.png"
        },
        {
          "epoch_id": "epoch_02",
          "date": "2026-02-14T12:00:00Z",
          "ra": 60.0055,
          "dec": 20.0076,
          "flux": 140.2,
          "cutout_url": "cutouts/mov_001_epoch_02.png"
        },
        {
          "epoch_id": "epoch_03",
          "date": "2026-03-16T18:00:00Z",
          "ra": 60.0125,
          "dec": 20.0042,
          "flux": 145.8,
          "cutout_url": "cutouts/mov_001_epoch_03.png"
        }
      ],
      "spectrum": {
        "wavelength_um": [0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0],
        "flux": [120.1, 135.4, 142.0, 138.2, 130.5, 125.0, 118.4, 110.2, 105.1, 98.3],
        "flux_err": [3.2, 3.1, 3.0, 3.0, 3.1, 3.2, 3.3, 3.5, 3.8, 4.0]
      }
    },
    {
      "object_id": "mov_002",
      "ra": 59.9850,
      "dec": 19.9920,
      "type": "unknown",
      "match_name": null,
      "confidence": 0.82,
      "is_synthetic": true,
      "motion": {
        "ra_rate_arcsec_per_day": 8.2,
        "dec_rate_arcsec_per_day": 5.4
      },
      "detections": [
        {
          "epoch_id": "epoch_01",
          "date": "2026-01-15T00:00:00Z",
          "ra": 59.9820,
          "dec": 19.9900,
          "flux": 45.1,
          "cutout_url": "cutouts/mov_002_epoch_01.png"
        },
        {
          "epoch_id": "epoch_02",
          "date": "2026-02-14T12:00:00Z",
          "ra": 59.9850,
          "dec": 19.9920,
          "flux": 44.8,
          "cutout_url": "cutouts/mov_002_epoch_02.png"
        }
      ],
      "spectrum": null
    }
  ]
}
```

