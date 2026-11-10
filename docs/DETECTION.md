# SPHEREx Sky Diary — Mover Detection & Trajectory Linking

**Module:** Module 3  
**Status:** Implemented  
**Maintainer:** Detection & Orbital Tracking Team  

---

## 1. Architectural Overview

The **Mover Detection Module** processes the background-subtracted, astrometrically aligned, and normalized image stacks output by Module 2. It detects moving Solar System bodies (asteroids, comets, Centaurs, TNOs) across unevenly spaced observation epochs:

```
          ┌───────────────────────────────────────────────┐
          │ Module 2 Processed Stack (load_processed_stack)│
          └───────────────────────┬───────────────────────┘
                                  │
                                  ▼
          ┌───────────────────────────────────────────────┐
          │   1. Static-Sky Reference Model & MAD Scatter │
          │      (build_static_model, wavelength gated)   │
          └───────────────────────┬───────────────────────┘
                                  │
                                  ▼
          ┌───────────────────────────────────────────────┐
          │   2. Image Differencing & Significance Maps   │
          │      (difference_epoch, Var + Scatter^2)      │
          └───────────────────────┬───────────────────────┘
                                  │
                                  ▼
          ┌───────────────────────────────────────────────┐
          │   3. Point Source Transient Extraction        │
          │      (extract_sources, DAOStarFinder)         │
          └───────────────────────┬───────────────────────┘
                                  │
                                  ▼
          ┌───────────────────────────────────────────────┐
          │   4. Constant-Velocity Tracklet Linking       │
          │      (link_detections, RA wraparound safe)    │
          └───────────────────────┬───────────────────────┘
                                  │
                                  ▼
          ┌───────────────────────────────────────────────┐
          │   5. Artifact Filtering (Single, Stationary,  │
          │      Bad Fit, Chromatic Response)             │
          └───────────────────────┬───────────────────────┘
                                  │
                                  ▼
          ┌───────────────────────────────────────────────┐
          │   6. Confidence Scoring                       │
          │      (compute_confidence)                     │
          └───────────────────────┬───────────────────────┘
                                  │ Writes
                                  ▼
          ┌───────────────────────────────────────────────┐
          │ data/output/candidates.json & cutouts/*.png   │
          │ data/output/detection_eval.json               │
          └───────────────────────────────────────────────┘
```

---

## 2. Confidence Scoring Formulation

The composite confidence score $C \in [0.0, 1.0]$ integrates four independent statistical and astrometric indicators:

$$C = \frac{w_{\text{snr}} c_{\text{snr}} + w_{\text{det}} c_{\text{det}} + w_{\text{fit}} c_{\text{fit}} + w_{\text{filter}} c_{\text{filter}}}{w_{\text{snr}} + w_{\text{det}} + w_{\text{fit}} + w_{\text{filter}}}$$

### Component Subscores:
1. **Signal-to-Noise Ratio ($c_{\text{snr}}$):**
   $$c_{\text{snr}} = \min\left(1.0, \frac{\overline{\text{SNR}}}{15.0}\right)$$
   Measures peak significance above local noise and static template residuals.
2. **Multi-Epoch Confirmation ($c_{\text{det}}$):**
   $$c_{\text{det}} = \min\left(1.0, \max\left(0.0, \frac{N_{\text{det}} - 2}{4.0}\right)\right)$$
   Gives $0.25$ for 3 detections, up to $1.0$ for 6 confirmed epochs.
3. **Astrometric Fit Quality ($c_{\text{fit}}$):**
   $$c_{\text{fit}} = \max\left(0.0, 1.0 - \frac{\text{RMS Residual (arcsec)}}{3.0}\right)$$
   Penalizes trajectories deviating from Keplerian/linear apparent motion.
4. **Chromatic Cleanliness ($c_{\text{filter}}$):**
   $$c_{\text{filter}} = \max(0.0, 1.0 - S_{\text{filter}})$$
   Penalizes detections whose brightness changes correlate ($r > 0.80$) with focal-plane wavelength shifts rather than true sky motion.

Default weights configured in `config/detection.yaml`:
- $w_{\text{snr}} = 0.35$
- $w_{\text{det}} = 0.30$
- $w_{\text{fit}} = 0.25$
- $w_{\text{filter}} = 0.10$

---

## 3. Real SPHEREx Cadence & Wavelength TODO(VERIFY) Checklist

> [!IMPORTANT]
> The flight cadence and Linear Variable Filter (LVF) passband shifts will be verified once official survey schedules and in-orbit calibrations are released.

Items for Shiv, Chaitanya, and Harnoor:
- [ ] **1. Survey Cadence & Velocity Limits:**
  - SPHEREx visits sky patches multiple times over 6-month survey epochs.
  - Verify whether `max_rate_arcsec_per_day` ($45.0''/\text{day}$) accommodates fast Near-Earth Objects (NEOs) or if multi-hypothesis linking needs a hierarchical rate grid.
- [ ] **2. Chromatic Lightcurve Correlation:**
  - In `flag_filter_response`, stationary sources observed at changing LVF central wavelengths mimic transients due to stellar spectral slopes.
  - Verify whether SPHEREx Level 3/4 pipelines provide synthetic forward-modeled static templates or raw coadd differencing.
- [ ] **3. Cutout Extraction Selection:**
  - Cutouts are currently extracted from the difference images centered on the mover centroid. Confirm whether the web UI displays difference cutouts or raw calibrated cutouts.
