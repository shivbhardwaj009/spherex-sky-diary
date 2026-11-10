"""SPHEREx Sky Diary — Transient Source Extraction (Module 3).

Detects candidate point sources on difference significance maps using DAOStarFinder,
computes aperture fluxes, translates coordinates via WCS, and filters out
edge artifacts and bright-star subtraction residuals.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from photutils.aperture import CircularAperture, aperture_photometry
from photutils.detection import DAOStarFinder

from data.adapter.base import EpochImage


def extract_sources(
    significance_map: np.ndarray,
    epoch: EpochImage,
    diff_pixels: Optional[np.ndarray] = None,
    bright_stars: Optional[List[Dict[str, Any]]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Extract transient point source candidates from a significance map.

    Args:
        significance_map: 2D float significance map (signal-to-noise ratio).
        epoch: Corresponding EpochImage providing WCS, mask, and wavelength map.
        diff_pixels: Optional 2D difference flux plane for aperture photometry.
        bright_stars: Optional list of bright reference star positions to mask out.
        config: Optional detection configuration dictionary.

    Returns:
        List of candidate detection dictionaries.
    """
    cfg = config or {}
    extract_cfg = cfg.get("extraction", {})

    snr_thresh = float(extract_cfg.get("snr_threshold", 3.5))
    fwhm = float(extract_cfg.get("fwhm", 3.0))
    bright_star_mask_rad = float(extract_cfg.get("bright_star_mask_radius_px", 6.0))
    edge_buffer = 4

    height, width = significance_map.shape

    # Zero out masked pixels prior to peak detection
    clean_sig = significance_map.copy()
    invalid_mask = (epoch.mask & 7) > 0  # bad, outlier, edge
    clean_sig[invalid_mask] = 0.0

    daofind = DAOStarFinder(fwhm=fwhm, threshold=snr_thresh)
    sources = daofind(clean_sig)

    if sources is None or len(sources) == 0:
        return []

    # Coordinates handling photutils version deprecations
    raw_x = sources["x_centroid"] if "x_centroid" in sources.colnames else sources["xcentroid"]
    raw_y = sources["y_centroid"] if "y_centroid" in sources.colnames else sources["ycentroid"]
    peaks = sources["peak"]
    sharpness = sources["sharpness"] if "sharpness" in sources.colnames else np.zeros(len(sources))
    roundness1 = sources["roundness1"] if "roundness1" in sources.colnames else np.zeros(len(sources))

    # Bright star rejection centers
    bright_star_coords: List[Tuple[float, float]] = []
    if bright_stars:
        for bs in bright_stars:
            if "x" in bs and "y" in bs:
                bright_star_coords.append((float(bs["x"]), float(bs["y"])))
            elif "ra" in bs and "dec" in bs:
                px, py = epoch.wcs.all_world2pix(bs["ra"], bs["dec"], 0)
                bright_star_coords.append((float(px), float(py)))

    bright_arr = np.array(bright_star_coords) if bright_star_coords else None

    phot_plane = diff_pixels if diff_pixels is not None else epoch.pixels

    detections: List[Dict[str, Any]] = []

    for i in range(len(sources)):
        x_val = float(raw_x[i])
        y_val = float(raw_y[i])
        snr_val = float(peaks[i])

        ix = int(round(x_val))
        iy = int(round(y_val))

        # 1. Edge boundary filter
        if ix < edge_buffer or ix >= (width - edge_buffer) or iy < edge_buffer or iy >= (height - edge_buffer):
            continue

        # 2. Mask filter (bad pixels, cosmic ray outliers, edges)
        if epoch.mask[iy, ix] & 7:
            continue

        # 3. Bright star proximity filter (subtracting residuals)
        if bright_arr is not None and len(bright_arr) > 0:
            dists = np.hypot(bright_arr[:, 0] - x_val, bright_arr[:, 1] - y_val)
            if np.any(dists < bright_star_mask_rad):
                continue

        # 4. Measure aperture flux
        aperture = CircularAperture((x_val, y_val), r=fwhm)
        phot_tab = aperture_photometry(phot_plane, aperture)
        flux_val = float(phot_tab["aperture_sum"][0])

        # Require positive flux for genuine detections
        if flux_val <= 0:
            continue

        # 5. World coordinates (RA/Dec J2000)
        ra_arr, dec_arr = epoch.wcs.all_pix2world(x_val, y_val, 0)
        ra_deg = float(ra_arr) % 360.0
        dec_deg = float(dec_arr)

        # 6. Local wavelength at detection centroid
        wl_val = float(epoch.wavelength_map[iy, ix])

        detections.append(
            {
                "x": round(x_val, 3),
                "y": round(y_val, 3),
                "ra": round(ra_deg, 6),
                "dec": round(dec_deg, 6),
                "flux": round(flux_val, 2),
                "snr": round(snr_val, 2),
                "sharpness": round(float(sharpness[i]), 3),
                "roundness": round(float(roundness1[i]), 3),
                "wavelength_um": round(wl_val, 4),
                "epoch_id": epoch.epoch_id,
                "date": epoch.date.isoformat(),
            }
        )

    return detections

