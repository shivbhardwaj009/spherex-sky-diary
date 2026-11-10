"""SPHEREx Sky Diary — Epoch Aperture Photometry (Module 5).

Measures source flux, photometric uncertainty, and local background on individual
EpochImage frames with exact position-dependent wavelength mapping.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import numpy as np
from astropy.stats import sigma_clipped_stats
from photutils.aperture import CircularAnnulus, CircularAperture

from data.adapter.base import EpochImage

logger = logging.getLogger(__name__)


@dataclass
class PhotometryMeasurement:
    """Photometric extraction result for a single epoch visit."""

    epoch_id: str
    date: str
    ra: float
    dec: float
    pixel_x: float
    pixel_y: float
    flux: float
    flux_err: float
    wavelength_um: float
    quality_flag: int  # 0 = clean measurement
    background: float
    background_rms: float


def measure_source(
    epoch_image: EpochImage,
    ra: float,
    dec: float,
    aperture_radius_pix: float = 3.5,
    annulus_inner_pix: float = 6.0,
    annulus_outer_pix: float = 10.0,
    min_valid_fraction: float = 0.75,
    mask_invalid_bits: int = 7,
    enable_aperture_correction: bool = False,
    aperture_correction_factor: float = 1.15,
) -> Tuple[Optional[PhotometryMeasurement], Optional[str]]:
    """Measure aperture flux, background, and position-dependent wavelength on an EpochImage.

    Args:
        epoch_image: Calibrated EpochImage from data adapter or processing module.
        ra: Right Ascension in degrees (J2000).
        dec: Declination in degrees (J2000).
        aperture_radius_pix: Circular aperture radius in detector pixels.
        annulus_inner_pix: Sky background annulus inner radius in pixels.
        annulus_outer_pix: Sky background annulus outer radius in pixels.
        min_valid_fraction: Minimum fraction of unmasked pixels required within aperture.
        mask_invalid_bits: Bitmask flags defining bad/unusable pixels.
        enable_aperture_correction: Whether to apply finite aperture correction.
        aperture_correction_factor: Multiplier for encircled energy correction.

    Returns:
        Tuple of (PhotometryMeasurement or None, skip_reason or None)
    """
    height, width = epoch_image.pixels.shape

    # 1. Coordinate conversion: RA/Dec to 0-based pixel coordinates
    try:
        px_raw, py_raw = epoch_image.wcs.all_world2pix(ra, dec, 0)
        px = float(px_raw)
        py = float(py_raw)
    except Exception as exc:
        return None, f"wcs_conversion_failed: {exc}"

    # 2. Check if source coordinate is inside image boundaries
    if px < 0.0 or px >= width or py < 0.0 or py >= height:
        return None, "source_outside_image_bounds"

    # 3. Check if aperture touches or falls outside image boundaries
    if (
        px - aperture_radius_pix < 0.0
        or px + aperture_radius_pix >= width
        or py - aperture_radius_pix < 0.0
        or py + aperture_radius_pix >= height
    ):
        return None, "aperture_touches_edge"

    # 4. Check aperture mask validity
    aperture = CircularAperture((px, py), r=aperture_radius_pix)
    ap_mask = aperture.to_mask(method="exact")
    if ap_mask is None:
        return None, "aperture_mask_generation_failed"

    mask_cutout = ap_mask.cutout(epoch_image.mask)
    if mask_cutout is None:
        return None, "aperture_cutout_failed"

    weights = ap_mask.data
    total_weights = np.sum(weights)
    if total_weights <= 0:
        return None, "empty_aperture_weights"

    bad_pixels = (mask_cutout & mask_invalid_bits) != 0
    masked_weight = np.sum(weights * bad_pixels)
    valid_fraction = 1.0 - (masked_weight / total_weights)

    if valid_fraction < min_valid_fraction:
        return None, f"aperture_masked_fraction_too_high: valid={valid_fraction:.2f} < {min_valid_fraction:.2f}"

    # 5. Local sky background estimation via circular annulus
    annulus = CircularAnnulus((px, py), r_in=annulus_inner_pix, r_out=annulus_outer_pix)
    ann_mask = annulus.to_mask(method="center")

    if ann_mask is not None:
        ann_pixels_cutout = ann_mask.cutout(epoch_image.pixels)
        ann_mask_cutout = ann_mask.cutout(epoch_image.mask)
        if ann_pixels_cutout is not None and ann_mask_cutout is not None:
            valid_ann = (ann_mask.data > 0) & ((ann_mask_cutout & mask_invalid_bits) == 0) & (~np.isnan(ann_pixels_cutout))
            ann_vals = ann_pixels_cutout[valid_ann]
        else:
            ann_vals = np.array([])
    else:
        ann_vals = np.array([])

    if len(ann_vals) >= 5:
        _, bg_median, bg_std = sigma_clipped_stats(ann_vals, sigma=3.0)
    else:
        # Fallback to local aperture median or 0.0 if annulus is near chip boundary
        bg_median = float(np.nanmedian(epoch_image.pixels))
        bg_std = float(np.nanstd(epoch_image.pixels))

    # 6. Aperture photometry extraction
    pix_cutout = ap_mask.cutout(epoch_image.pixels)
    var_cutout = ap_mask.cutout(epoch_image.variance)

    if pix_cutout is None or var_cutout is None:
        return None, "photometry_cutout_extraction_failed"

    # Replace bad pixels in cutout with local background to avoid skewing weighted sum
    good_pix = pix_cutout.copy()
    good_pix[bad_pixels] = bg_median

    raw_flux = float(np.sum(good_pix * weights))
    aperture_area = float(np.sum(weights))
    net_flux = raw_flux - (bg_median * aperture_area)

    # 7. Propagate photometric uncertainties (variance plane + background uncertainty)
    # Sum aperture variance weighted by weights^2
    var_clean = var_cutout.copy()
    var_clean[bad_pixels] = float(np.nanmedian(epoch_image.variance))
    var_sum = float(np.sum(var_clean * (weights**2)))

    # Background uncertainty on total aperture flux
    n_ann = max(1, len(ann_vals))
    bg_uncertainty_var = (aperture_area**2) * ((bg_std**2) / n_ann)

    total_variance = var_sum + bg_uncertainty_var
    flux_err = math.sqrt(max(1e-6, total_variance))

    # 8. Aperture correction (optional)
    # TODO(VERIFY): With real flight data, apply verified SPHEREx encircled energy curve
    if enable_aperture_correction:
        net_flux *= aperture_correction_factor
        flux_err *= aperture_correction_factor

    # 9. Position-dependent wavelength assignment
    # In SPHEREx linear variable filters, the effective passband is determined
    # by the source's pixel coordinates on the detector focal plane.
    ix = int(round(px))
    iy = int(round(py))
    ix = max(0, min(width - 1, ix))
    iy = max(0, min(height - 1, iy))

    wavelength_um = float(epoch_image.wavelength_map[iy, ix])

    # TODO(VERIFY): LVF spectral dispersion across detector sub-pixel offsets.
    # Flight pipeline may require bi-linear interpolation on wavelength_map.

    date_str = (
        epoch_image.date.isoformat()
        if hasattr(epoch_image.date, "isoformat")
        else str(epoch_image.date)
    )

    measurement = PhotometryMeasurement(
        epoch_id=epoch_image.epoch_id,
        date=date_str,
        ra=ra,
        dec=dec,
        pixel_x=round(px, 3),
        pixel_y=round(py, 3),
        flux=round(net_flux, 4),
        flux_err=round(flux_err, 4),
        wavelength_um=round(wavelength_um, 4),
        quality_flag=0,
        background=round(float(bg_median), 4),
        background_rms=round(float(bg_std), 4),
    )

    return measurement, None
