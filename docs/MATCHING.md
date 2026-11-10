# SPHEREx Sky Diary — Solar System Catalog Matching (Module 4)

**Status:** Complete  
**Contract Version:** `1.0` (Validated via `docs/schema.json` and `docs/validate.py`)  
**Package:** `matching/`  
**Configuration:** `config/matching.yaml`  

---

## 1. Architectural Overview

The **Matching Module** (`matching/`) takes detected mover candidate tracklets from Module 3 (stored in `data/output/candidates.json`) and cross-matches them against known Solar System bodies (asteroids, comets, planets, and minor planets).

The matching engine:
1. Determines whether each candidate is a **Known** cataloged body or an **Unknown** newly detected mover.
2. Resolves catalog identification ambiguities (e.g. multiple candidate bodies close to a tracklet).
3. Assigns catalog designations (`match_name`), records mean astrometric separation residuals (`match_distance_arcsec`), and boosts confidence scores.
4. Operates 100% offline via local disk caching and offline ephemeris catalogs, ensuring network outages never crash the scientific pipeline.
5. Produces comprehensive validation reports (`data/output/validation_report.json` and `validation_report.md`).

---

## 2. Ephemeris Query & Caching Architecture

### Primary Provider: IMCCE SkyBoT
- Service: IMCCE `SkyBoT` cone search via `astroquery.imcce.Skybot`.
- Searches across the target field cone expanded by maximum expected apparent motion:
  $$\Delta\theta_{\text{pad}} = \frac{v_{\text{max}} \cdot \Delta t_{\text{span}}}{3600}$$
  where $v_{\text{max}} = 50.0''/\text{day}$ and $\Delta t_{\text{span}}$ is the time delta between first and last epochs.
- Returns target designations, physical types, predicted coordinates (RA/Dec), apparent motion rates ($d\text{RA}/dt$, $d\text{Dec}/dt$), and visual magnitudes ($V$).

### Secondary Provider: JPL Horizons
- Accessible via `astroquery.jplhorizons.Horizons` for precision orbit refinement of specific high-priority bodies.

### Hermetic Caching & Offline Fallback
- **Deterministic Disk Cache (`matching/cache/`):** All queries are hashed using SHA-256 over celestial coordinates, search radius, and sorted observation epochs. Repeated queries are served from disk with zero network latency.
- **Offline Fallback Catalog (`matching/cache/offline_known.json`):** When live network requests encounter timeouts or connection errors (or when `--offline` is passed), the pipeline falls back to a curated offline ephemeris catalog.
- **Metadata Provenance:** The catalog records `metadata.matching_source` (`"skybot"`, `"cache"`, or `"offline_catalog"`), allowing the UI to display appropriate provenance badges.

---

## 3. Trajectory Matching Algorithm

Given a candidate tracklet with detections at epochs $\{t_1, t_2, \dots, t_k\}$:

1. **Positional Separation:**
   For each epoch, calculate exact spherical angular separation:
   $$\Delta\theta_i = \text{sep}((\alpha_{\text{det}, i}, \delta_{\text{det}, i}), (\alpha_{\text{pred}, i}, \delta_{\text{pred}, i}))$$
   Handles spherical geometry and RA wraparound ($0^\circ \leftrightarrow 360^\circ$).

2. **Motion Vector Consistency:**
   - Apparent speed difference: $\Delta v = |v_{\text{cand}} - v_{\text{pred}}| \le \Delta v_{\text{tol}}$ (default $8.0''/\text{day}$).
   - Motion direction difference: $\Delta\phi = |\phi_{\text{cand}} - \phi_{\text{pred}}| \le \Delta\phi_{\text{tol}}$ (default $35.0^\circ$).

3. **Detection Agreement Criteria:**
   An epoch matches if $\Delta\theta_i \le \theta_{\text{tol}}$ (default $8.0'' \approx 1.3$ SPHEREx pixels).
   The overall match is validated if:
   - $\text{matched\_epochs} \ge \text{min\_matched\_epochs}$ (default 2)
   - $\frac{\text{matched\_epochs}}{N_{\text{detections}}} \ge \text{min\_matched\_fraction}$ (default 50%)
   - Motion vector tolerances are satisfied.

4. **Ambiguity Resolution:**
   If multiple catalog bodies match a candidate, the body with the lowest mean separation residual $\bar{\Delta\theta}$ is selected as primary, and the second-closest is recorded as `runner_up_match`.

---

## 4. Contract v1.0 Fields Added

As permitted by the design rules, four optional fields were added to `docs/schema.json` and documented in `docs/CONTRACT.md`:

- **Top-Level:**
  - `metadata` (`object`, optional): Pipeline provenance info, including `matching_source`.
- **In `movers[]`:**
  - `match_distance_arcsec` (`number`, optional): Mean separation in arcseconds between candidate detections and ephemeris.
  - `matched_epoch_count` (`integer`, optional): Number of epochs confirming the match.
  - `runner_up_match` (`string | null`, optional): Ambiguity runner-up body designation.

---

## 5. Items to Verify with Real SPHEREx Operations (`TODO(VERIFY)`)

1. **Observer Coordinate Frame / Parallax:**
   - `TODO(VERIFY)`: SkyBoT queries currently specify geocentric observer code `'500'`. SPHEREx operates in a Sun-synchronous Low Earth Orbit (~700 km altitude, 97° inclination) or Sun-Earth L2. Topocentric parallax can displace fast-moving Near-Earth Objects (NEOs) by several arcseconds relative to geocentric ephemerides. Verify spacecraft ephemeris integration with JPL Horizons or IAU MPC observatory code assignment.
2. **SkyBoT Rate Coordinates:**
   - `TODO(VERIFY)`: Verify whether SkyBoT `RA_rate` column represents true angular motion on the sky ($d\alpha/dt \cdot \cos\delta$) or coordinate motion ($d\alpha/dt$). Current implementation treats it as arcsec/hr and converts to arcsec/day.
3. **Apparent Magnitude Calibration:**
   - `TODO(VERIFY)`: SkyBoT provides Johnson $V$-band magnitudes. For SPHEREx near-infrared bands (0.75 – 5.0 µm), Solar System asteroid reflectance spectra peak with red/neutral slopes and infrared thermal emission tails. Verify infrared color transformations ($V - J$, $V - K$) for magnitude cutoffs.
