"""SPHEREx Sky Diary — Difference Imaging & Significance Mapping (Module 3).

Computes static-subtracted difference images, pixel significance maps (S/N),
and pairwise epoch-minus-epoch difference planes for transient visualization.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import numpy as np

from data.adapter.base import EpochImage


def difference_epoch(
    epoch: EpochImage,
    model: np.ndarray,
    scatter: np.ndarray,
    config: Optional[Dict[str, Any]] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Subtract stationary sky model from epoch image and generate significance map.

    Args:
        epoch: Input aligned and normalized EpochImage.
        model: 2D static sky model plane.
        scatter: 2D empirical noise scatter (MAD-derived) plane.
        config: Optional detection configuration dictionary.

    Returns:
        Tuple of (difference_pixels, significance_map, updated_mask).
    """
    if epoch.pixels.shape != model.shape or epoch.pixels.shape != scatter.shape:
        raise ValueError(
            f"Shape mismatch: epoch {epoch.pixels.shape}, model {model.shape}, scatter {scatter.shape}"
        )

    # 1. Image differencing
    diff = epoch.pixels - model

    # 2. Combined uncertainty: detector/photon variance + model empirical scatter^2
    var_clean = np.nan_to_num(epoch.variance, nan=9.0)
    scatter_clean = np.nan_to_num(scatter, nan=3.0)
    combined_var = np.maximum(1e-6, var_clean + (scatter_clean**2))
    total_sigma = np.sqrt(combined_var)

    # 3. Significance map (signal-to-noise ratio per pixel)
    significance = diff / np.maximum(1e-4, total_sigma)

    # 4. Mask handling: zero out invalid/edge pixels
    updated_mask = epoch.mask.copy()
    invalid = (updated_mask & 7) > 0  # bad, outlier, edge
    diff[invalid] = 0.0
    significance[invalid] = 0.0

    return diff, significance, updated_mask


def pairwise_difference(
    epoch_a: EpochImage,
    epoch_b: EpochImage,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute direct pairwise difference between two observation epochs.

    Useful for interactive blink comparison and confirmation.

    Args:
        epoch_a: First EpochImage (positive transient).
        epoch_b: Second EpochImage (reference template).

    Returns:
        Tuple of (diff_pixels, significance_map, combined_mask).
    """
    if epoch_a.pixels.shape != epoch_b.pixels.shape:
        raise ValueError(
            f"Shape mismatch between epochs: {epoch_a.pixels.shape} vs {epoch_b.pixels.shape}"
        )

    diff = epoch_a.pixels - epoch_b.pixels
    combined_var = np.nan_to_num(epoch_a.variance, nan=9.0) + np.nan_to_num(epoch_b.variance, nan=9.0)
    total_sigma = np.sqrt(np.maximum(1e-6, combined_var))
    significance = diff / np.maximum(1e-4, total_sigma)

    combined_mask = epoch_a.mask | epoch_b.mask
    invalid = (combined_mask & 7) > 0
    diff[invalid] = 0.0
    significance[invalid] = 0.0

    return diff, significance, combined_mask

