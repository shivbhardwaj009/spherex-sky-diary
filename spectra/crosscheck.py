"""SPHEREx Sky Diary — Spectral Cross-Check Helper (Module 5).

Compares extracted pipeline spectra against reference spectra exported from the
NASA/IPAC Infrared Science Archive (IRSA) Spectrophotometry Tool.

Documented IRSA Column Names:
------------------------------
TODO(VERIFY): Actual IRSA Spectrophotometry export CSV headers:
- Wavelength column: 'wavelength' | 'wavelength_um' | 'lambda' | 'spectral_axis' (in microns)
- Flux column: 'flux' | 'flux_density' | 'fnu' | 'data' (in physical or detector units)
- Error column: 'flux_err' | 'uncertainty' | 'error' | 'sigma'
- Flag/Filter column: 'filter' | 'band' | 'quality_flag'
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_irsa_reference_csv(csv_path: Path | str) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Load reference spectrophotometry table from CSV.

    Supports flexible column detection for IRSA tool formats.

    Returns:
        Tuple of (wavelengths, flux, flux_err) as numpy float arrays.
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Reference CSV file not found: {path}")

    wavelengths: List[float] = []
    fluxes: List[float] = []
    errors: List[float] = []

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f"CSV file {path} contains no valid header row")

        # Normalize field names lowercase
        field_map = {col.lower().strip(): col for col in reader.fieldnames}

        # Resolve wavelength column
        wl_col = None
        for candidate in ["wavelength", "wavelength_um", "lambda", "spectral_axis", "wl"]:
            if candidate in field_map:
                wl_col = field_map[candidate]
                break

        # Resolve flux column
        flux_col = None
        for candidate in ["flux", "flux_density", "fnu", "data", "intensity"]:
            if candidate in field_map:
                flux_col = field_map[candidate]
                break

        # Resolve error column
        err_col = None
        for candidate in ["flux_err", "uncertainty", "error", "sigma", "err"]:
            if candidate in field_map:
                err_col = field_map[candidate]
                break

        if not wl_col or not flux_col:
            raise ValueError(
                f"Could not identify required wavelength and flux columns in {path}. "
                f"Available headers: {reader.fieldnames}"
            )

        for row in reader:
            try:
                w_val = float(row[wl_col])
                f_val = float(row[flux_col])
                e_val = float(row[err_col]) if err_col and row.get(err_col) else 0.05 * f_val
                wavelengths.append(w_val)
                fluxes.append(f_val)
                errors.append(e_val)
            except (ValueError, TypeError):
                continue

    if not wavelengths:
        raise ValueError(f"No valid numeric data rows found in {path}")

    # Sort by wavelength
    sort_idx = np.argsort(wavelengths)
    return (
        np.array(wavelengths)[sort_idx],
        np.array(fluxes)[sort_idx],
        np.array(errors)[sort_idx],
    )


def compare_to_reference(
    our_spectrum: Dict[str, List[float]],
    reference_csv_path: Path | str,
    output_plot_path: Path | str = REPO_ROOT / "data" / "output" / "crosscheck.png",
) -> Dict[str, float]:
    """Compare extracted pipeline spectrum with an external IRSA reference spectrum.

    Args:
        our_spectrum: Pipeline spectrum dict {'wavelength_um', 'flux', 'flux_err'}.
        reference_csv_path: Path to IRSA reference CSV file.
        output_plot_path: Destination PNG image for comparison plot.

    Returns:
        Dictionary with median_ratio, mean_ratio, and relative_scatter.
    """
    ref_wl, ref_flux, ref_err = load_irsa_reference_csv(reference_csv_path)

    our_wl = np.array(our_spectrum.get("wavelength_um", []), dtype=float)
    our_f = np.array(our_spectrum.get("flux", []), dtype=float)
    our_e = np.array(our_spectrum.get("flux_err", []), dtype=float)

    if len(our_wl) == 0:
        raise ValueError("Pipeline spectrum contains no wavelength data points.")

    # Interpolate reference onto our wavelength channels
    ref_interp_flux = np.interp(our_wl, ref_wl, ref_flux)

    # Compute flux ratios (safe against division by zero)
    valid_ratio = ref_interp_flux > 1e-9
    if not np.any(valid_ratio):
        raise ValueError("Reference flux contains no positive values for comparison.")

    ratios = our_f[valid_ratio] / ref_interp_flux[valid_ratio]
    median_ratio = float(np.median(ratios))
    mean_ratio = float(np.mean(ratios))
    scatter = float(np.std(ratios) / median_ratio) if median_ratio > 0 else 0.0

    print("==================================================")
    print("SPHEREx SPECTRUM VS IRSA REFERENCE CROSS-CHECK")
    print(f"  Reference file:     {Path(reference_csv_path).name}")
    print(f"  Channels evaluated: {np.sum(valid_ratio)}")
    print(f"  Median Flux Ratio:  {median_ratio:.4f}")
    print(f"  Mean Flux Ratio:    {mean_ratio:.4f}")
    print(f"  Relative Scatter:   {scatter * 100.0:.2f}%")
    print("==================================================")

    # Generate diagnostic cross-check plot using Pillow
    out_plot = Path(output_plot_path)
    out_plot.parent.mkdir(parents=True, exist_ok=True)

    img_w, img_h = 800, 600
    img = Image.new("RGB", (img_w, img_h), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Margins and boxes
    x_min, x_max = 80, 740
    # Top box: Flux spectra
    y1_min, y1_max = 60, 340
    # Bottom box: Ratio
    y2_min, y2_max = 390, 540

    draw.rectangle([x_min, y1_min, x_max, y1_max], outline=(200, 200, 200), width=1)
    draw.rectangle([x_min, y2_min, x_max, y2_max], outline=(200, 200, 200), width=1)

    # Title & text
    draw.text((x_min, 25), "SPHEREx Spectrum vs. IRSA Reference Cross-Check", fill=(30, 41, 59))
    draw.text((x_min, 45), f"Median Ratio: {median_ratio:.3f} | Relative Scatter: {scatter * 100.0:.1f}%", fill=(100, 116, 139))

    # Wavelength extent
    all_wl = np.concatenate([ref_wl, our_wl])
    min_w, max_w = float(np.min(all_wl)), float(np.max(all_wl))
    span_w = max(0.1, max_w - min_w)

    def to_x(w: float) -> float:
        return x_min + ((w - min_w) / span_w) * (x_max - x_min)

    # Top panel flux scaling
    all_f = np.concatenate([ref_flux, our_f])
    min_f = max(0.0, float(np.min(all_f)) * 0.9)
    max_f = float(np.max(all_f)) * 1.1
    span_f = max(1.0, max_f - min_f)

    def to_y1(f: float) -> float:
        return y1_max - ((f - min_f) / span_f) * (y1_max - y1_min)

    # Reference curve (Blue)
    ref_points = [(to_x(w), to_y1(fl)) for w, fl in zip(ref_wl, ref_flux)]
    if len(ref_points) >= 2:
        draw.line(ref_points, fill=(37, 99, 235), width=2)

    # Our spectrum points & errors (Red)
    for w, fl, err in zip(our_wl, our_f, our_e):
        px, py = to_x(w), to_y1(fl)
        py_up = to_y1(fl + err)
        py_dn = to_y1(fl - err)
        draw.line([(px, py_dn), (px, py_up)], fill=(220, 38, 38), width=1)
        draw.ellipse([px - 3, py - 3, px + 3, py + 3], fill=(220, 38, 38))

    # Legend for top panel
    draw.line([(x_max - 220, y1_min + 15), (x_max - 190, y1_min + 15)], fill=(37, 99, 235), width=2)
    draw.text((x_max - 180, y1_min + 8), "IRSA Reference", fill=(37, 99, 235))
    draw.ellipse([x_max - 210, y1_min + 30, x_max - 200, y1_min + 40], fill=(220, 38, 38))
    draw.text((x_max - 180, y1_min + 28), "SPHEREx Extracted", fill=(220, 38, 38))

    # Bottom panel: Ratios
    r_min, r_max = max(0.0, median_ratio - 0.5), median_ratio + 0.5
    span_r = max(0.2, r_max - r_min)

    def to_y2(r: float) -> float:
        return y2_max - ((r - r_min) / span_r) * (y2_max - y2_min)

    # Unity line (gray)
    draw.line([(x_min, to_y2(1.0)), (x_max, to_y2(1.0))], fill=(156, 163, 175), width=1)
    # Median ratio line (green dashed)
    draw.line([(x_min, to_y2(median_ratio)), (x_max, to_y2(median_ratio))], fill=(22, 163, 74), width=1)

    ratio_pts = [
        (to_x(w), to_y2(r)) for w, r, v in zip(our_wl, our_f / np.maximum(1e-9, ref_interp_flux), valid_ratio) if v
    ]
    if len(ratio_pts) >= 2:
        draw.line(ratio_pts, fill=(5, 150, 105), width=1)
    for px, py in ratio_pts:
        draw.ellipse([px - 2, py - 2, px + 2, py + 2], fill=(5, 150, 105))

    draw.text((x_min, y2_max + 10), f"Wavelength ({min_w:.2f} - {max_w:.2f} um)", fill=(71, 85, 105))
    draw.text((15, (y1_min + y1_max) // 2), "Flux (ADU)", fill=(71, 85, 105))
    draw.text((15, (y2_min + y2_max) // 2), "Ratio", fill=(71, 85, 105))

    img.save(out_plot, format="PNG")

    logger.info("Saved crosscheck comparison plot to %s", out_plot)

    return {
        "median_ratio": round(median_ratio, 4),
        "mean_ratio": round(mean_ratio, 4),
        "relative_scatter": round(scatter, 4),
        "plot_path": str(out_plot),
    }


def generate_mock_reference_csv(
    output_path: Path | str = REPO_ROOT / "data" / "mock_irsa_reference.csv",
) -> Path:
    """Generate a synthetic IRSA reference CSV for offline unit testing."""
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    wavelengths = np.linspace(0.8, 4.8, 50)
    # Solar continuum reflectance model
    base_flux = 500.0 * (1.0 + 0.15 * (wavelengths - 1.0))
    # 1 um absorption
    base_flux -= 60.0 * np.exp(-((wavelengths - 1.05) ** 2) / 0.05)

    with open(p, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["wavelength", "flux", "flux_err", "filter"])
        for wl, fl in zip(wavelengths, base_flux):
            writer.writerow([round(float(wl), 4), round(float(fl), 2), round(float(fl * 0.05), 2), "SPHEREx_LVF"])

    return p
