"""SPHEREx Sky Diary — Position-Dependent Wavelength Handling (Module 2).

Maintains reprojected 2D wavelength maps and evaluates spectral comparability
across observation epochs to prevent chromatic differencing false alarms.

TODO(VERIFY):
Real SPHEREx data handling for wavelength differences:
In SPHEREx's Linear Variable Filter (LVF) architecture, the effective passband
varies continuously across the detector focal plane. Depending on the telescope
scan cadence and orientation, the same sky coordinates observed in two different
epochs may be measured at slightly different central wavelengths.
There are two main strategies:
  Option A: Channel-matching differencing (only compute difference images between
            epochs where |lambda_A - lambda_B| < delta_lambda_tol).
  Option B: Spectral forward-modeling (use the multi-band SPHEREx source catalog
            to subtract modeled stationary source flux at the epoch's exact wavelength).
Until the cadence, passband overlap, and pipeline delivery formats are verified
with the flight team, this module implements Option A via comparable_mask and
wavelength_difference_map.
"""

from __future__ import annotations

from typing import Tuple

import numpy as np

from data.adapter.base import EpochImage


def comparable_mask(
    epoch_a: EpochImage,
    epoch_b: EpochImage,
    tol_um: float = 0.15,
) -> np.ndarray:
    """Return a boolean mask of pixels whose observed wavelengths match within tolerance.

    Used by difference imaging (Module 3) to ensure like-with-like spectral comparison.

    Args:
        epoch_a: First aligned EpochImage.
        epoch_b: Second aligned EpochImage.
        tol_um: Maximum permissible wavelength difference in microns.

    Returns:
        2D boolean array where True indicates comparable spectral coverage.
    """
    if epoch_a.wavelength_map.shape != epoch_b.wavelength_map.shape:
        raise ValueError(
            f"Wavelength map shapes mismatch: {epoch_a.wavelength_map.shape} vs {epoch_b.wavelength_map.shape}"
        )

    wl_a = epoch_a.wavelength_map
    wl_b = epoch_b.wavelength_map

    # Check valid numeric coverage (not NaN)
    valid_coverage = (~np.isnan(wl_a)) & (~np.isnan(wl_b))

    # Wavelength difference
    diff = np.abs(wl_a - wl_b)
    within_tol = diff <= tol_um

    return valid_coverage & within_tol


def wavelength_difference_map(
    epoch_a: EpochImage,
    epoch_b: EpochImage,
) -> np.ndarray:
    """Compute signed per-pixel wavelength difference (lambda_a - lambda_b) in microns.

    Provides diagnostic input to the transient false-alarm filter in Module 3.

    Args:
        epoch_a: First aligned EpochImage.
        epoch_b: Second aligned EpochImage.

    Returns:
        2D float array of wavelength differences.
    """
    if epoch_a.wavelength_map.shape != epoch_b.wavelength_map.shape:
        raise ValueError(
            f"Wavelength map shapes mismatch: {epoch_a.wavelength_map.shape} vs {epoch_b.wavelength_map.shape}"
        )

    return epoch_a.wavelength_map - epoch_b.wavelength_map

