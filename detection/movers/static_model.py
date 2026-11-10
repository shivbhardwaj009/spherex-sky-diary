"""SPHEREx Sky Diary — Static-Sky Model & Noise Estimation (Module 3).

Synthesizes a deep static sky reference model and per-pixel empirical noise
scatter (MAD) from an aligned multi-epoch stack, incorporating wavelength
comparability gating.
"""

from __future__ import annotations

import warnings
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from data.adapter.base import EpochImage


def build_static_model(
    stack: List[EpochImage],
    config: Optional[Dict[str, Any]] = None,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    """Build a stationary reference sky model and empirical scatter map.

    Methodology:
    1. Stacks all aligned epochs and excludes masked pixels (bad pixels, cosmic
       rays, edges/no-coverage).
    2. Incorporates position-dependent wavelength filtering: for each pixel, selects
       only epochs whose local central wavelength is within `wavelength_tol_um`
       of the median wavelength across available epochs.
    3. If sufficient comparable epochs exist (>= min_comparable_epochs), computes
       the median across those comparable epochs. Otherwise, falls back to the
       full-stack masked median and logs the fallback occurrence.
    4. Computes per-pixel empirical scatter using the Median Absolute Deviation (MAD),
       scaled by 1.4826 for consistency with normal distribution standard deviation.

    Args:
        stack: List of aligned, background-subtracted, and normalized EpochImages.
        config: Optional detection configuration dictionary.

    Returns:
        Tuple of (static_model_2d, scatter_2d, metadata_dict).
    """
    if not stack:
        raise ValueError("Cannot build static model from an empty epoch stack.")

    cfg = config or {}
    model_cfg = cfg.get("static_model", {})
    tol_um = float(model_cfg.get("wavelength_tol_um", 0.15))
    min_comp = int(model_cfg.get("min_comparable_epochs", 2))

    n_epochs = len(stack)
    h, w = stack[0].pixels.shape

    pixels_3d = np.array([ep.pixels for ep in stack], dtype=np.float64)
    masks_3d = np.array([ep.mask for ep in stack], dtype=np.int32)
    wl_3d = np.array([ep.wavelength_map for ep in stack], dtype=np.float64)
    var_3d = np.array([ep.variance for ep in stack], dtype=np.float64)

    # Valid pixel: not flagged as bad (bit 1), cosmic ray outlier (bit 2), or edge (bit 4)
    valid_3d = (masks_3d & 7) == 0

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)

        # 1. Plain masked median (across all unmasked epochs)
        masked_pixels = np.where(valid_3d, pixels_3d, np.nan)
        plain_median = np.nanmedian(masked_pixels, axis=0)

        # 2. Wavelength comparability gating
        masked_wl = np.where(valid_3d, wl_3d, np.nan)
        median_wl = np.nanmedian(masked_wl, axis=0)

        wl_diff = np.abs(wl_3d - median_wl[None, :, :])
        comparable_3d = valid_3d & (wl_diff <= tol_um)
        comp_count = np.sum(comparable_3d, axis=0)

        use_comparable = comp_count >= min_comp
        comp_pixels = np.where(comparable_3d, pixels_3d, np.nan)
        comp_median = np.nanmedian(comp_pixels, axis=0)

        # Combine: use comparable median where available, fallback to plain median elsewhere
        static_model = np.where(use_comparable, comp_median, plain_median)
        # For areas with no valid observations across all epochs, set 0.0
        static_model = np.nan_to_num(static_model, nan=0.0)

        # 3. Empirical noise scatter via Median Absolute Deviation (MAD)
        residuals = np.abs(np.where(valid_3d, pixels_3d - static_model[None, :, :], np.nan))
        raw_mad = np.nanmedian(residuals, axis=0)
        scatter = 1.4826 * raw_mad

        # Fallback for scatter: where MAD is 0 or NaN, substitute median variance-based noise
        mean_var_noise = np.sqrt(np.nanmedian(np.where(valid_3d, var_3d, np.nan), axis=0))
        mean_var_noise = np.nan_to_num(mean_var_noise, nan=3.0)
        invalid_scatter = (scatter <= 1e-4) | np.isnan(scatter)
        scatter[invalid_scatter] = mean_var_noise[invalid_scatter]
        scatter = np.maximum(0.5, scatter)

    fallback_fraction = float(np.mean(~use_comparable))

    metadata: Dict[str, Any] = {
        "n_epochs": n_epochs,
        "wavelength_tol_um": tol_um,
        "min_comparable_epochs": min_comp,
        "fallback_pixel_fraction": round(fallback_fraction, 4),
        "mean_scatter": round(float(np.mean(scatter)), 3),
        "median_scatter": round(float(np.median(scatter)), 3),
    }

    return static_model, scatter, metadata

