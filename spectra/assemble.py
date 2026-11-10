"""SPHEREx Sky Diary — Spectral Assembly & Binning (Module 5).

Assembles multi-epoch photometric measurements sampled across Linear Variable Filters
into a sorted, binned, inverse-variance weighted spectrum conforming to the contract.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

import numpy as np

from spectra.photometry import PhotometryMeasurement

logger = logging.getLogger(__name__)


def build_spectrum(
    measurements: List[Optional[PhotometryMeasurement]],
    bin_width_um: float = 0.15,
    min_measurements_per_bin: int = 1,
    min_valid_measurements: int = 2,
    sigma_clip_outliers: float = 3.0,
) -> Optional[Dict[str, List[float]]]:
    """Assemble individual epoch measurements into a calibrated binned spectrum.

    Args:
        measurements: List of PhotometryMeasurement objects from observation epochs.
        bin_width_um: Wavelength bin width in microns.
        min_measurements_per_bin: Minimum measurement points required per bin.
        min_valid_measurements: Minimum total valid measurements required to build spectrum.
        sigma_clip_outliers: Outlier rejection threshold in standard deviations within bin.

    Returns:
        Contract-compliant dictionary with 'wavelength_um', 'flux', and 'flux_err' lists,
        or None if insufficient valid measurements exist.
    """
    # 1. Filter valid clean measurements
    valid: List[PhotometryMeasurement] = []
    for m in measurements:
        if m is None:
            continue
        if m.quality_flag != 0:
            continue
        if math.isnan(m.flux) or math.isnan(m.flux_err) or m.flux_err <= 0.0:
            continue
        if math.isnan(m.wavelength_um) or m.wavelength_um <= 0.0:
            continue
        valid.append(m)

    if len(valid) < min_valid_measurements:
        logger.debug(
            "Insufficient valid measurements (%d < %d)", len(valid), min_valid_measurements
        )
        return None

    # 2. Sort chronologically / positionally independent measurements by wavelength
    valid.sort(key=lambda item: item.wavelength_um)

    # 3. Create wavelength bin intervals across observed spectral coverage
    min_wl = valid[0].wavelength_um
    max_wl = valid[-1].wavelength_um

    # If all measurements fall within a very narrow span, single bin
    if (max_wl - min_wl) < bin_width_um:
        bin_edges = [min_wl - 0.01, max_wl + 0.01]
    else:
        # Standard contiguous binning grid
        n_steps = max(1, int(math.ceil((max_wl - min_wl) / bin_width_um)))
        bin_edges = [min_wl + i * bin_width_um for i in range(n_steps + 1)]
        if bin_edges[-1] < max_wl:
            bin_edges.append(bin_edges[-1] + bin_width_um)

    out_wavelengths: List[float] = []
    out_fluxes: List[float] = []
    out_flux_errs: List[float] = []

    # 4. Bin measurements using inverse-variance weighting
    for i in range(len(bin_edges) - 1):
        low_wl = bin_edges[i]
        high_wl = bin_edges[i + 1]

        # Select points in this bin [low_wl, high_wl)
        # Include high boundary for the final bin
        if i == len(bin_edges) - 2:
            in_bin = [m for m in valid if low_wl <= m.wavelength_um <= high_wl]
        else:
            in_bin = [m for m in valid if low_wl <= m.wavelength_um < high_wl]

        if not in_bin:
            # Leave empty bins out rather than interpolating across large gaps
            continue

        # Optional outlier clipping within bin if multiple points exist
        if sigma_clip_outliers > 0.0 and len(in_bin) >= 3:
            flux_vals = [m.flux for m in in_bin]
            med_f = float(np.median(flux_vals))
            std_f = float(np.std(flux_vals))
            if std_f > 0.0:
                in_bin = [m for m in in_bin if abs(m.flux - med_f) <= sigma_clip_outliers * std_f]

        if len(in_bin) < min_measurements_per_bin:
            continue

        # Inverse-variance weighted mean: w_i = 1 / sigma_i^2
        weights = [1.0 / (m.flux_err**2) for m in in_bin]
        sum_w = sum(weights)

        if sum_w <= 0.0:
            continue

        weighted_flux = sum(w * m.flux for w, m in zip(weights, in_bin)) / sum_w
        weighted_wl = sum(w * m.wavelength_um for w, m in zip(weights, in_bin)) / sum_w
        weighted_err = 1.0 / math.sqrt(sum_w)

        out_wavelengths.append(round(weighted_wl, 4))
        out_fluxes.append(round(weighted_flux, 4))
        out_flux_errs.append(round(weighted_err, 4))

    if not out_wavelengths:
        return None

    # Ensure Contract Invariant: len(wavelength_um) == len(flux) == len(flux_err)
    assert len(out_wavelengths) == len(out_fluxes) == len(out_flux_errs)

    return {
        "wavelength_um": out_wavelengths,
        "flux": out_fluxes,
        "flux_err": out_flux_errs,
    }
