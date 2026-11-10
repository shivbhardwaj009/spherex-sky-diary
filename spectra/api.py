"""SPHEREx Sky Diary — Spectral Extraction API (Module 5).

Provides high-level programmatic interfaces to extract multi-epoch spectra for both
static celestial coordinates and moving Solar System targets following fitted tracks.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from data.adapter.base import EpochImage, EpochSource, Region
from data.adapter.factory import get_source
from spectra.assemble import build_spectrum
from spectra.photometry import PhotometryMeasurement, measure_source
from spectra.stacking import stack_epochs_by_band

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _parse_datetime(date_val: Any) -> datetime:
    """Parse string or datetime to timezone-aware UTC datetime."""
    if isinstance(date_val, datetime):
        if date_val.tzinfo is None:
            return date_val.replace(tzinfo=timezone.utc)
        return date_val
    norm = str(date_val).replace("Z", "+00:00")
    dt = datetime.fromisoformat(norm)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def get_spectrum(
    ra: float,
    dec: float,
    source: Optional[EpochSource] = None,
    region: Optional[Region] = None,
    fov_deg: float = 0.2,
    track: Optional[List[Dict[str, Any]]] = None,
    motion: Optional[Dict[str, float]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, List[float]]]:
    """Extract and assemble calibrated spectrum for a static position or moving track.

    Args:
        ra: Reference Right Ascension in degrees (J2000).
        dec: Reference Declination in degrees (J2000).
        source: Optional EpochSource data adapter. Defaults to factory mock/irsa source.
        region: Target observation region.
        fov_deg: Field of view size in degrees.
        track: List of detection dictionaries per epoch ({'epoch_id', 'date', 'ra', 'dec'}).
        motion: Apparent motion rates {'ra_rate_arcsec_per_day', 'dec_rate_arcsec_per_day'}.
        config: Spectra configuration parameters dictionary.

    Returns:
        Contract-compliant dictionary {'wavelength_um', 'flux', 'flux_err'}, or None if
        fewer than minimum valid measurements could be obtained.
    """
    cfg = config or {}
    phot_cfg = cfg.get("photometry", {})
    asm_cfg = cfg.get("assembly", {})
    stack_cfg = cfg.get("stacking", {})

    ap_rad = float(phot_cfg.get("aperture_radius_pix", 3.5))
    ann_in = float(phot_cfg.get("annulus_inner_pix", 6.0))
    ann_out = float(phot_cfg.get("annulus_outer_pix", 10.0))
    min_valid_frac = float(phot_cfg.get("min_valid_fraction", 0.75))
    mask_bits = int(phot_cfg.get("mask_invalid_bits", 7))
    en_ap_corr = bool(phot_cfg.get("enable_aperture_correction", False))
    ap_corr_factor = float(phot_cfg.get("aperture_correction_factor", 1.15))

    bin_width = float(asm_cfg.get("bin_width_um", 0.15))
    min_per_bin = int(asm_cfg.get("min_measurements_per_bin", 1))
    min_valid = int(asm_cfg.get("min_valid_measurements", 2))
    sigma_clip = float(asm_cfg.get("sigma_clip_outliers", 3.0))

    stack_by_band = bool(stack_cfg.get("stack_by_band", False))

    # Initialize adapter source if not provided
    if source is None:
        source = get_source(cfg.get("settings"))

    # Target region
    if region is None:
        region = Region(
            name="ecliptic_plane_test",
            ra_center=ra,
            dec_center=dec,
            radius_deg=fov_deg / 2.0,
        )

    epoch_infos = source.list_epochs(region)
    if not epoch_infos:
        logger.warning("No epochs found for region %s", region.name)
        return None

    # Load EpochImages
    epoch_images: List[EpochImage] = []
    for ep in epoch_infos:
        try:
            img = source.load_epoch(ep.epoch_id, region, fov_deg=fov_deg)
            epoch_images.append(img)
        except Exception as exc:
            logger.warning("Failed to load epoch %s: %s", ep.epoch_id, exc)

    if not epoch_images:
        return None

    # Optional band stacking
    if stack_by_band:
        epoch_images = stack_epochs_by_band(epoch_images)

    # Build detection coordinate lookup from track if provided
    track_by_epoch: Dict[str, Tuple[float, float]] = {}
    ref_dt = _parse_datetime(epoch_images[0].date)

    if track:
        for det in track:
            ep_id = det.get("epoch_id")
            if ep_id and "ra" in det and "dec" in det:
                track_by_epoch[ep_id] = (float(det["ra"]), float(det["dec"]))
            elif "date" in det and "ra" in det and "dec" in det:
                dt_key = _parse_datetime(det["date"]).isoformat()
                track_by_epoch[dt_key] = (float(det["ra"]), float(det["dec"]))

    cos_dec = max(0.01, math.cos(math.radians(dec)))
    ra_rate = float(motion.get("ra_rate_arcsec_per_day", 0.0)) if motion else 0.0
    dec_rate = float(motion.get("dec_rate_arcsec_per_day", 0.0)) if motion else 0.0

    measurements: List[PhotometryMeasurement] = []

    for img in epoch_images:
        ep_id = img.epoch_id
        img_dt = _parse_datetime(img.date)
        dt_key = img_dt.isoformat()

        # 1. Trajectory following: evaluate target (RA, Dec) at this epoch
        if ep_id in track_by_epoch:
            target_ra, target_dec = track_by_epoch[ep_id]
        elif dt_key in track_by_epoch:
            target_ra, target_dec = track_by_epoch[dt_key]
        elif motion is not None and (ra_rate != 0.0 or dec_rate != 0.0):
            # Propagate from reference position using fitted constant velocity
            delta_days = (img_dt - ref_dt).total_seconds() / 86400.0
            target_ra = ra + ((ra_rate * delta_days) / 3600.0) / cos_dec
            target_dec = dec + ((dec_rate * delta_days) / 3600.0)
        else:
            # Static target at fixed celestial position
            target_ra, target_dec = ra, dec

        # 2. Extract aperture measurement on this epoch
        meas, reason = measure_source(
            epoch_image=img,
            ra=target_ra,
            dec=target_dec,
            aperture_radius_pix=ap_rad,
            annulus_inner_pix=ann_in,
            annulus_outer_pix=ann_out,
            min_valid_fraction=min_valid_frac,
            mask_invalid_bits=mask_bits,
            enable_aperture_correction=en_ap_corr,
            aperture_correction_factor=ap_corr_factor,
        )

        if meas is not None:
            measurements.append(meas)
        else:
            logger.debug("Skipped measurement on epoch %s: %s", ep_id, reason)

    # 3. Assemble and bin spectrum
    spectrum = build_spectrum(
        measurements=measurements,
        bin_width_um=bin_width,
        min_measurements_per_bin=min_per_bin,
        min_valid_measurements=min_valid,
        sigma_clip_outliers=sigma_clip,
    )

    return spectrum
