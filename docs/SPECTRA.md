# SPHEREx Sky Diary — Spectral Extraction & Assembly (Module 5)

**Status:** Complete  
**Contract Version:** `1.0` (Validated via `docs/schema.json` and `docs/validate.py`)  
**Package:** `spectra/`  
**Configuration:** `config/spectra.yaml`  

---

## 1. Architectural Overview

The **Spectra Module** (`spectra/`) extracts calibrated near-infrared spectra (0.75 – 5.0 µm) from SPHEREx multi-epoch sky observations for both:
1. **Moving Solar System Targets:** Aperture dynamically tracks the object across observation epochs following its fitted celestial trajectory.
2. **Static Celestial Coordinates:** Fixed aperture extraction across epochs for stellar, brown dwarf, and challenge demo targets.

---

## 2. Linear Variable Filter (LVF) Wavelength Sampling

In SPHEREx's optical design, each detector pixel views a distinct narrow passband determined by its physical coordinates on the Linear Variable Filter:
$$\lambda = \lambda(x_{\text{detector}}, y_{\text{detector}})$$

Because the spacecraft scans the sky with dithered orientations across different survey epochs, an astronomical object samples **different wavelengths** across successive visits.

### Extraction & Assembly Pipeline:
1. **Photometry (`spectra/photometry.py`):**
   - Circular aperture photometry centered at the source's epoch coordinates.
   - Sky background estimated using a circular annulus with sigma-clipped median subtraction.
   - Photometric uncertainty propagated from detector variance plus local background variance.
   - Position-dependent central wavelength $\lambda_{\text{meas}}$ sampled directly from `epoch_image.wavelength_map[iy, ix]`.
2. **Assembly & Binning (`spectra/assemble.py`):**
   - Outliers clipped via sigma clipping within spectral bins.
   - Multi-epoch measurements binned via inverse-variance weighting:
     $$w_i = \frac{1}{\sigma_i^2}, \quad \bar{F} = \frac{\sum w_i F_i}{\sum w_i}, \quad \sigma_{\bar{F}} = \frac{1}{\sqrt{\sum w_i}}$$
   - Non-contiguous or empty wavelength bins are omitted rather than interpolated.
   - Guarantees schema invariant: $\text{len}(\lambda) = \text{len}(F) = \text{len}(\sigma_F)$.

---

## 3. Detector Band Stacking

The pipeline supports an optional pre-photometry co-addition step (`stack_by_band: true`) across SPHEREx's 6 physical detector arrays:
- **Band 1:** $0.75 - 1.11\,\mu\text{m}$
- **Band 2:** $1.11 - 1.64\,\mu\text{m}$
- **Band 3:** $1.64 - 2.42\,\mu\text{m}$
- **Band 4:** $2.42 - 3.82\,\mu\text{m}$
- **Band 5:** $3.82 - 4.42\,\mu\text{m}$
- **Band 6:** $4.42 - 5.00\,\mu\text{m}$

Co-adding $M$ aligned exposures within the same detector band reduces uncorrelated detector noise:
$$\text{Gain} = \frac{\text{SNR}_{\text{stacked}}}{\text{SNR}_{\text{single}}} \approx \sqrt{M}$$
Empirical tests on synthetic benchmark stacks yield an S/N gain $\ge 1.3\times$ (theoretical $\approx 2.0\times$ for $M=4$).

---

## 4. Space Apps Challenge Demo Targets

Static spectra are generated and saved to `data/output/spectra/<target>.json` for the five designated challenge targets:
1. **Barnard's Star:** High proper-motion red dwarf ($V \approx 9.5$, M4V).
2. **Epsilon Indi B:** Nearby brown dwarf binary system (T1 + T6 dwarfs).
3. **WISE 0855:** Coldest known sub-stellar brown dwarf (Y-dwarf, $T \sim 250\text{ K}$, RA 08h55m10.831s, Dec -07d14m42.53s).
4. **RW Aurigae:** Classical T Tauri star with dynamic circumstellar accretion disk.
5. **R Draconis:** Mira-type oxygen-rich asymptotic giant branch pulsating variable.

---

## 5. Items to Verify with Flight Data (`TODO(VERIFY)`)

1. **SPHEREx Detector Band Cutoffs:**
   - `TODO(VERIFY)`: Confirm exact physical wavelength cutoffs for SPHEREx focal plane arrays 1 through 6 against the final instrument calibration report.
2. **Aperture Correction Curve:**
   - `TODO(VERIFY)`: In real flight observations, replace the constant aperture correction factor ($1.15\times$) with the verified SPHEREx Encircled Energy (EE) profile as a function of wavelength and field angle.
3. **IRSA Spectrophotometry Tool Export Headers:**
   - `TODO(VERIFY)`: Verify column headers in CSV files exported from the IPAC/IRSA Spectrophotometry web tool.
4. **Target Proper Motion Epochs:**
   - `TODO(VERIFY)`: For high proper-motion demonstration targets (Barnard's Star ~10.4"/yr, WISE 0855 ~8.1"/yr), ensure proper motion propagation from Gaia DR3 (epoch 2016.0) to SPHEREx survey epoch (~2026.0).
