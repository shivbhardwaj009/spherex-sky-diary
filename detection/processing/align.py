"""SPHEREx Sky Diary — Astrometric Alignment & Reprojection (Module 2).

Reprojects multi-epoch observation planes onto an unprivileged celestial
reference grid defined purely by the region center and field-of-view.
Propagates pixels, variance, masks, and position-dependent wavelength maps.
"""

from __future__ import annotations

import copy
import math
from typing import Any, Dict, Optional, Tuple

import numpy as np
from astropy.wcs import WCS
from reproject import reproject_exact, reproject_interp

from data.adapter.base import EpochImage, Region
from detection.processing.masking import BIT_EDGE


def build_reference_grid(
    region: Region,
    fov_deg: float = 0.2,
    pixel_scale_arcsec: float = 6.2,
    image_size: Optional[int] = None,
) -> Tuple[WCS, Tuple[int, int]]:
    """Construct an unprivileged celestial reference grid (WCS and shape).

    The reference grid is strictly defined by the target region center and FOV,
    ensuring that no individual observation epoch's pointing or pixel grid is favored.

    Args:
        region: Target sky region.
        fov_deg: Angular field of view size in degrees.
        pixel_scale_arcsec: Nominal pixel scale in arcseconds (default: 6.2 for SPHEREx).
        image_size: Optional explicit pixel grid size. If None, derived from fov_deg.

    Returns:
        Tuple of (ref_wcs, (height, width)).
    """
    pixel_scale_deg = pixel_scale_arcsec / 3600.0

    if image_size is None:
        npix = max(32, int(round(fov_deg / pixel_scale_deg)))
    else:
        npix = image_size
        pixel_scale_deg = fov_deg / float(npix)

    ref_wcs = WCS(naxis=2)
    # FITS CRPIX is 1-based; in 0-based python indexing, center is (npix / 2.0)
    ref_wcs.wcs.crpix = [(npix / 2.0) + 1.0, (npix / 2.0) + 1.0]
    ref_wcs.wcs.cdelt = [-pixel_scale_deg, pixel_scale_deg]
    ref_wcs.wcs.crval = [region.ra_center, region.dec_center]
    ref_wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]

    return ref_wcs, (npix, npix)


def reproject_epoch(
    epoch: EpochImage,
    ref_wcs: WCS,
    ref_shape: Tuple[int, int],
    config: Optional[Dict[str, Any]] = None,
) -> EpochImage:
    """Reproject an EpochImage onto the common reference celestial grid.

    Reprojection rules:
    - Pixels: Bilinear interpolation (or exact flux-conserving if configured).
    - Variance: Bilinear interpolation of the variance map.
      [Approximation Note]: True covariance-aware variance propagation for
      reprojected pixels is Var(I_out) = sum(w_i^2 * sigma_i^2) <= sum(w_i * sigma_i^2).
      Interpolating the variance plane directly implements sum(w_i * sigma_i^2),
      which is the standard astronomical approximation (used in SWarp/Drizzle)
      and acts as a safe, slightly conservative uncertainty upper-bound.
    - Wavelength map: Bilinear interpolation, preserving spatial dispersion gradients.
    - Mask: Nearest-neighbor interpolation (order=0) to preserve discrete bit flags.
      Pixels outside the input footprint (no coverage) are flagged with BIT_EDGE (4).

    Args:
        epoch: Input EpochImage to reproject.
        ref_wcs: Target reference WCS.
        ref_shape: Target grid dimensions (height, width).
        config: Optional processing configuration dictionary.

    Returns:
        New aligned EpochImage on the reference grid.
    """
    cfg = config or {}
    align_cfg = cfg.get("alignment", {})
    method = align_cfg.get("method", "reproject_interp")
    order = align_cfg.get("order", "bilinear")

    # 1. Reproject image flux
    if method == "reproject_exact":
        rep_pixels, footprint = reproject_exact(
            (epoch.pixels, epoch.wcs),
            output_projection=ref_wcs,
            shape_out=ref_shape,
        )
    else:
        rep_pixels, footprint = reproject_interp(
            (epoch.pixels, epoch.wcs),
            output_projection=ref_wcs,
            shape_out=ref_shape,
            order=order,
        )

    # 2. Reproject variance plane
    rep_variance, _ = reproject_interp(
        (epoch.variance, epoch.wcs),
        output_projection=ref_wcs,
        shape_out=ref_shape,
        order=order,
    )

    # 3. Reproject wavelength map
    rep_wavelength, _ = reproject_interp(
        (epoch.wavelength_map, epoch.wcs),
        output_projection=ref_wcs,
        shape_out=ref_shape,
        order=order,
    )

    # 4. Reproject quality mask with nearest-neighbor interpolation
    rep_mask_float, _ = reproject_interp(
        (epoch.mask.astype(np.float64), epoch.wcs),
        output_projection=ref_wcs,
        shape_out=ref_shape,
        order="nearest-neighbor",
    )
    # Round to nearest integer bitmask
    rep_mask = np.nan_to_num(rep_mask_float, nan=0.0).round().astype(np.int32)

    # 5. Flag border / no-coverage regions as BIT_EDGE (4)
    no_coverage = (footprint <= 1e-4) | np.isnan(rep_pixels)
    rep_mask[no_coverage] |= BIT_EDGE
    rep_pixels[no_coverage] = 0.0
    rep_variance[no_coverage] = np.nan
    rep_wavelength[no_coverage] = np.nan

    new_metadata = copy.deepcopy(epoch.metadata)
    new_metadata["aligned"] = True
    new_metadata["reproject_method"] = method
    new_metadata["coverage_fraction"] = float(np.mean(footprint > 1e-4))

    return EpochImage(
        pixels=rep_pixels,
        variance=rep_variance,
        mask=rep_mask,
        wcs=ref_wcs,
        wavelength_map=rep_wavelength,
        epoch_id=epoch.epoch_id,
        date=epoch.date,
        metadata=new_metadata,
    )
