"""SPHEREx Sky Diary — Data Quality & Outlier Masking (Module 2).

Combines adapter-level quality flags with a robust local outlier detector
(cosmic rays and spikes via median-filtered variance residuals) and morphological
dilation (mask growth).

Bitmask Schema:
    Bit 0 (value 1): Adapter-level bad/dead pixel
    Bit 1 (value 2): Robust statistical outlier / cosmic ray hit
    Bit 2 (value 4): Edge / no-coverage / reprojection border
"""

from __future__ import annotations

import copy
from typing import Any, Dict, Optional

import numpy as np
import scipy.ndimage as ndi

from data.adapter.base import EpochImage

# Canonical bit flags
BIT_ADAPTER_BAD: int = 1
BIT_OUTLIER: int = 2
BIT_EDGE: int = 4


def detect_outliers(
    pixels: np.ndarray,
    variance: np.ndarray,
    outlier_sigma: float = 5.0,
    filter_size: int = 5,
) -> np.ndarray:
    """Identify positive flux outliers (cosmic rays, sharp transients).

    Compares pixels against a local 2D median filter normalized by local 1-sigma
    noise derived from the variance plane.

    Args:
        pixels: 2D image plane.
        variance: 2D variance plane.
        outlier_sigma: Number of standard deviations above local median to flag.
        filter_size: Dimension of local median filter kernel (odd integer).

    Returns:
        2D boolean array where True represents an outlier.
    """
    local_median = ndi.median_filter(pixels, size=filter_size)
    noise_sigma = np.sqrt(np.maximum(1e-6, variance))
    residual = pixels - local_median
    return residual > (outlier_sigma * noise_sigma)


def grow_mask(
    mask_binary: np.ndarray,
    grow_pixels: int = 2,
) -> np.ndarray:
    """Morphologically dilate binary mask by a radius of grow_pixels."""
    if grow_pixels <= 0:
        return mask_binary.astype(bool)
    # 8-connectivity structure
    structure = ndi.generate_binary_structure(2, 2)
    return ndi.binary_dilation(mask_binary, structure=structure, iterations=grow_pixels)


def build_mask(
    epoch: EpochImage,
    config: Optional[Dict[str, Any]] = None,
) -> np.ndarray:
    """Construct combined quality bitmask for an EpochImage.

    Args:
        epoch: Input EpochImage.
        config: Optional processing configuration dictionary.

    Returns:
        2D int32 array conforming to the canonical bitmask schema.
    """
    cfg = config or {}
    mask_cfg = cfg.get("masking", {})

    outlier_sigma = float(mask_cfg.get("outlier_sigma", 5.0))
    filter_size = int(mask_cfg.get("local_median_filter_size", 5))
    grow_pixels = int(mask_cfg.get("grow_pixels", 2))

    bit_bad = int(mask_cfg.get("bit_adapter_bad", BIT_ADAPTER_BAD))
    bit_outlier = int(mask_cfg.get("bit_outlier", BIT_OUTLIER))
    bit_edge = int(mask_cfg.get("bit_edge", BIT_EDGE))

    combined = np.zeros(epoch.pixels.shape, dtype=np.int32)

    # 1. Ingest adapter mask
    if epoch.mask is not None:
        if epoch.mask.dtype == bool:
            combined[epoch.mask] |= bit_bad
        else:
            # Transfer existing bit flags
            if np.any(epoch.mask & 1):
                combined[(epoch.mask & 1) > 0] |= bit_bad
            if np.any(epoch.mask & 2):
                combined[(epoch.mask & 2) > 0] |= bit_outlier
            if np.any(epoch.mask & 4):
                combined[(epoch.mask & 4) > 0] |= bit_edge

    # 2. Detect statistical outliers / cosmic rays
    outliers = detect_outliers(
        pixels=epoch.pixels,
        variance=epoch.variance,
        outlier_sigma=outlier_sigma,
        filter_size=filter_size,
    )
    combined[outliers] |= bit_outlier

    # 3. Grow bad pixels and cosmic rays
    if grow_pixels > 0:
        bad_and_outliers = (combined & (bit_bad | bit_outlier)) > 0
        dilated = grow_mask(bad_and_outliers, grow_pixels=grow_pixels)
        # Apply outlier flag to newly grown boundary pixels
        new_grown_pixels = dilated & ~bad_and_outliers
        combined[new_grown_pixels] |= bit_outlier

    return combined


def apply_mask(
    epoch: EpochImage,
    new_mask: np.ndarray,
) -> EpochImage:
    """Return a new EpochImage with updated mask without mutating original."""
    new_metadata = copy.deepcopy(epoch.metadata)
    new_metadata["mask_summary"] = {
        "bad_pixels": int(np.sum((new_mask & BIT_ADAPTER_BAD) > 0)),
        "outliers": int(np.sum((new_mask & BIT_OUTLIER) > 0)),
        "edges": int(np.sum((new_mask & BIT_EDGE) > 0)),
    }

    return EpochImage(
        pixels=epoch.pixels.copy(),
        variance=epoch.variance.copy(),
        mask=new_mask.copy(),
        wcs=epoch.wcs,
        wavelength_map=epoch.wavelength_map.copy(),
        epoch_id=epoch.epoch_id,
        date=epoch.date,
        metadata=new_metadata,
    )
