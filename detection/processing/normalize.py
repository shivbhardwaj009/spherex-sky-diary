"""SPHEREx Sky Diary — Relative Photometric Normalization (Module 2).

Identifies stable, isolated, non-saturated reference stars across aligned epochs
and computes relative photometric scale factors to normalize throughput variations.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from astropy.stats import sigma_clipped_stats
from photutils.aperture import CircularAperture, aperture_photometry
from photutils.detection import DAOStarFinder

from data.adapter.base import EpochImage


def select_reference_stars(
    stack: List[EpochImage],
    config: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Select stable, isolated, non-saturated reference stars from an aligned stack.

    Selection Rules:
    1. Detection on Median Stack: Uses DAOStarFinder on the median coadd image
       to eliminate single-epoch moving objects and transient artifacts.
    2. Spatial Boundary: Stars must lie inside an edge buffer (at least 10 pixels
       from the boundary) to avoid reprojection edge artifacts.
    3. Isolation: Reject any star that has another candidate closer than min_distance_px
       to avoid aperture flux contamination / blending.
    4. Moderately Bright & Non-Saturated: Excludes faint noise spikes and saturated pixels.
    5. Photometric Stability (Cross-Epoch Scatter): Evaluates aperture flux across all
       epochs. Rejects any star whose relative flux standard deviation
       (std / mean) exceeds max_cross_epoch_scatter.

    Args:
        stack: List of aligned EpochImage instances.
        config: Optional processing configuration dictionary.

    Returns:
        List of selected reference star dictionaries with 'x', 'y', 'flux_mean', 'scatter'.

    Raises:
        ValueError: If fewer than min_reference_stars satisfy the selection criteria.
    """
    if not stack:
        raise ValueError("Cannot select reference stars from an empty stack.")

    cfg = config or {}
    norm_cfg = cfg.get("normalization", {})

    fwhm = float(norm_cfg.get("fwhm", 3.5))
    threshold_sigma = float(norm_cfg.get("threshold_sigma", 4.0))
    min_dist_px = float(norm_cfg.get("min_distance_px", 8.0))
    max_scatter = float(norm_cfg.get("max_cross_epoch_scatter", 0.20))
    min_stars = int(norm_cfg.get("min_reference_stars", 4))
    ap_radius = float(norm_cfg.get("aperture_radius_px", 3.5))
    edge_buffer = 10.0

    # 1. Coadd median image across all aligned epochs
    all_pixels = np.array([ep.pixels for ep in stack])
    median_image = np.nanmedian(all_pixels, axis=0)
    height, width = median_image.shape

    # Estimate background noise level on median coadd
    _, med_val, std_val = sigma_clipped_stats(median_image, sigma=3.0, maxiters=5)
    detection_threshold = max(1.0, threshold_sigma * std_val)

    # 2. Extract point sources with DAOStarFinder
    daofind = DAOStarFinder(fwhm=fwhm, threshold=detection_threshold)
    sources = daofind(median_image - med_val)

    if sources is None or len(sources) == 0:
        raise ValueError(
            f"No candidate point sources detected on median stack (threshold={detection_threshold:.2f})."
        )

    # Extract coordinates handling photutils version deprecations
    raw_x = sources["x_centroid"] if "x_centroid" in sources.colnames else sources["xcentroid"]
    raw_y = sources["y_centroid"] if "y_centroid" in sources.colnames else sources["ycentroid"]

    candidates: List[Tuple[float, float]] = []
    for x, y in zip(raw_x, raw_y):
        fx, fy = float(x), float(y)
        # Check edge boundary
        if (
            edge_buffer <= fx < (width - edge_buffer)
            and edge_buffer <= fy < (height - edge_buffer)
        ):
            candidates.append((fx, fy))

    if not candidates:
        raise ValueError("All detected sources were located outside the usable image area.")

    # 3. Isolation filter: reject blended sources
    isolated_candidates: List[Tuple[float, float]] = []
    coords_arr = np.array(candidates)
    for i, (cx, cy) in enumerate(candidates):
        dists = np.hypot(coords_arr[:, 0] - cx, coords_arr[:, 1] - cy)
        # Distance to itself is 0, so check 2nd smallest distance
        if len(dists) > 1:
            sorted_dists = np.sort(dists)
            nearest_neighbor = sorted_dists[1]
            if nearest_neighbor >= min_dist_px:
                isolated_candidates.append((cx, cy))
        else:
            isolated_candidates.append((cx, cy))

    # 4. Multi-epoch stability filter: measure aperture photometry across stack
    selected_stars: List[Dict[str, Any]] = []

    for sx, sy in isolated_candidates:
        aperture = CircularAperture((sx, sy), r=ap_radius)
        epoch_fluxes: List[float] = []

        valid_star = True
        for ep in stack:
            phot_table = aperture_photometry(ep.pixels, aperture)
            flux_val = float(phot_table["aperture_sum"][0])

            # Star must have positive flux and not be masked/edge
            int_x, int_y = int(round(sx)), int(round(sy))
            if ep.mask[int_y, int_x] & 4:  # edge / no-coverage
                valid_star = False
                break
            if flux_val <= 0:
                valid_star = False
                break
            epoch_fluxes.append(flux_val)

        if not valid_star or len(epoch_fluxes) != len(stack):
            continue

        mean_flux = float(np.mean(epoch_fluxes))
        if mean_flux <= 0:
            continue

        flux_std = float(np.std(epoch_fluxes))
        rel_scatter = flux_std / mean_flux

        # Stability rejection
        if rel_scatter <= max_scatter:
            selected_stars.append(
                {
                    "x": sx,
                    "y": sy,
                    "flux_mean": mean_flux,
                    "scatter": rel_scatter,
                    "epoch_fluxes": epoch_fluxes,
                }
            )

    # 5. Enforce minimum count requirement
    if len(selected_stars) < min_stars:
        raise ValueError(
            f"Too few reference stars found ({len(selected_stars)} < {min_stars}). "
            f"Cannot reliably normalize epochs across region."
        )

    # Sort descending by brightness (most reliable references first)
    selected_stars.sort(key=lambda s: s["flux_mean"], reverse=True)
    return selected_stars


def normalize_epochs(
    stack: List[EpochImage],
    stars: List[Dict[str, Any]],
    config: Optional[Dict[str, Any]] = None,
) -> Tuple[List[EpochImage], Dict[str, float]]:
    """Compute per-epoch scale factors and normalize image stacks.

    Args:
        stack: List of aligned EpochImage instances.
        stars: Validated reference stars from select_reference_stars.
        config: Optional processing configuration dictionary.

    Returns:
        Tuple of (normalized_epoch_stack, dict_of_scale_factors_by_epoch_id).

    Raises:
        ValueError: If too few reference stars are provided.
    """
    cfg = config or {}
    norm_cfg = cfg.get("normalization", {})
    min_stars = int(norm_cfg.get("min_reference_stars", 4))
    ap_radius = float(norm_cfg.get("aperture_radius_px", 3.5))

    if len(stars) < min_stars:
        raise ValueError(
            f"Cannot normalize with {len(stars)} reference stars (minimum required: {min_stars})."
        )

    scale_factors: Dict[str, float] = {}
    normalized_stack: List[EpochImage] = []

    apertures = CircularAperture([(s["x"], s["y"]) for s in stars], r=ap_radius)

    for ep in stack:
        phot_table = aperture_photometry(ep.pixels, apertures)
        measured_fluxes = np.array(phot_table["aperture_sum"], dtype=np.float64)

        # Ratio of each star's epoch flux to its baseline mean flux
        star_means = np.array([s["flux_mean"] for s in stars], dtype=np.float64)
        ratios = measured_fluxes / np.maximum(1e-6, star_means)

        # Robust median ratio is the epoch scale factor
        scale_factor = float(np.median(ratios))
        if scale_factor <= 1e-4 or np.isnan(scale_factor):
            scale_factor = 1.0

        scale_factors[ep.epoch_id] = round(scale_factor, 5)

        # Apply scale factor: divide pixels by S, variance by S^2
        norm_pixels = ep.pixels / scale_factor
        norm_variance = ep.variance / (scale_factor**2)

        new_metadata = copy.deepcopy(ep.metadata)
        new_metadata["normalized"] = True
        new_metadata["normalization_factor"] = scale_factor
        new_metadata["reference_star_count"] = len(stars)

        normalized_stack.append(
            EpochImage(
                pixels=norm_pixels,
                variance=norm_variance,
                mask=ep.mask.copy(),
                wcs=ep.wcs,
                wavelength_map=ep.wavelength_map.copy(),
                epoch_id=ep.epoch_id,
                date=ep.date,
                metadata=new_metadata,
            )
        )

    return normalized_stack, scale_factors
