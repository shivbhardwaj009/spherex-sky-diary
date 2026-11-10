"""SPHEREx Sky Diary — Background Estimation & Subtraction (Module 2).

Estimates global and spatial 2D background surfaces using astropy sigma-clipped
statistics and photutils Background2D, producing background-subtracted EpochImage
instances without mutating inputs.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, Optional, Tuple

import numpy as np
from astropy.stats import SigmaClip, sigma_clipped_stats
from photutils.background import Background2D, MedianBackground

from data.adapter.base import EpochImage


def estimate_background(
    image: np.ndarray,
    mask: Optional[np.ndarray] = None,
    box_size: Tuple[int, int] = (32, 32),
    filter_size: Tuple[int, int] = (3, 3),
    sigma_clip_sigma: float = 3.0,
    sigma_clip_maxiters: int = 5,
) -> Tuple[float, np.ndarray]:
    """Estimate global scalar level and 2D spatial background map.

    Args:
        image: 2D float numpy array.
        mask: Optional 2D boolean mask or bitmask (True/non-zero = masked).
        box_size: Background mesh box dimensions (height, width).
        filter_size: Median filter size for smoothing background grid.
        sigma_clip_sigma: Sigma clipping threshold.
        sigma_clip_maxiters: Maximum clipping iterations.

    Returns:
        Tuple of (global_median_level, background_map_2d).
    """
    bool_mask = (mask > 0) if mask is not None and mask.dtype != bool else mask
    if bool_mask is not None and bool_mask.shape != image.shape:
        raise ValueError(f"Mask shape {bool_mask.shape} does not match image shape {image.shape}")

    # 1. Global background statistics using sigma-clipped stats
    sig_clip = SigmaClip(sigma=sigma_clip_sigma, maxiters=sigma_clip_maxiters)
    mean_val, median_val, std_val = sigma_clipped_stats(
        image,
        mask=bool_mask,
        sigma=sigma_clip_sigma,
        maxiters=sigma_clip_maxiters,
    )
    global_bkg = float(median_val if not np.isnan(median_val) else mean_val)

    # 2. 2D spatial background map using photutils Background2D
    # Adjust box_size if image is smaller than mesh box
    h, w = image.shape
    adj_box = (min(box_size[0], max(8, h // 2)), min(box_size[1], max(8, w // 2)))

    try:
        bkg = Background2D(
            image,
            box_size=adj_box,
            filter_size=filter_size,
            sigma_clip=sig_clip,
            bkg_estimator=MedianBackground(),
            mask=bool_mask,
            fill_value=global_bkg,
        )
        bkg_map = bkg.background.astype(np.float64)
    except Exception:
        # Fallback to constant global level if mesh fitting fails
        bkg_map = np.full_like(image, global_bkg, dtype=np.float64)

    return global_bkg, bkg_map


def subtract_background(
    epoch: EpochImage,
    config: Optional[Dict[str, Any]] = None,
) -> EpochImage:
    """Subtract 2D spatial background map from EpochImage without mutating input.

    Args:
        epoch: Input EpochImage.
        config: Optional processing configuration dictionary.

    Returns:
        New EpochImage with background removed and map stored in metadata.
    """
    cfg = config or {}
    bkg_cfg = cfg.get("background", {})

    box_size = tuple(bkg_cfg.get("box_size", (32, 32)))
    filter_size = tuple(bkg_cfg.get("filter_size", (3, 3)))
    sigma_clip_sigma = float(bkg_cfg.get("sigma_clip_sigma", 3.0))
    sigma_clip_maxiters = int(bkg_cfg.get("sigma_clip_maxiters", 5))

    global_level, bkg_map = estimate_background(
        image=epoch.pixels,
        mask=epoch.mask,
        box_size=box_size,
        filter_size=filter_size,
        sigma_clip_sigma=sigma_clip_sigma,
        sigma_clip_maxiters=sigma_clip_maxiters,
    )

    subtracted_pixels = epoch.pixels - bkg_map

    new_metadata = copy.deepcopy(epoch.metadata)
    new_metadata["background_global"] = global_level
    new_metadata["background_map"] = bkg_map

    return EpochImage(
        pixels=subtracted_pixels,
        variance=epoch.variance.copy(),
        mask=epoch.mask.copy(),
        wcs=epoch.wcs,
        wavelength_map=epoch.wavelength_map.copy(),
        epoch_id=epoch.epoch_id,
        date=epoch.date,
        metadata=new_metadata,
    )
