"""SPHEREx Sky Diary — Artifact Rejection Filters (Module 3).

Modular quality filters for screening stationary subtraction residuals, single-epoch
cosmic rays/transients, chromatic filter-response artifacts, and poor trajectory fits.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from data.adapter.base import EpochImage
from detection.movers.linking import Tracklet, angular_separation_arcsec


def reject_single_epoch(tracklet: Tracklet) -> bool:
    """Reject tracklets whose detections only span a single observation epoch.

    Returns:
        True if rejected (single-epoch transient / cosmic ray), False if valid.
    """
    epochs = set(d.get("epoch_id") for d in tracklet.detections)
    return len(epochs) < 2


def reject_stationary(
    tracklet: Tracklet,
    min_motion_arcsec: float = 3.0,
) -> bool:
    """Reject stationary or unmoving artifacts (e.g., variable star subtraction residuals).

    Evaluates the total angular separation between the first and last observation.

    Args:
        tracklet: Tracklet candidate.
        min_motion_arcsec: Minimum angular displacement in arcseconds.

    Returns:
        True if rejected (stationary), False if valid moving object.
    """
    if len(tracklet.detections) < 2:
        return True

    d_first = tracklet.detections[0]
    d_last = tracklet.detections[-1]

    _, _, total_sep_arcsec = angular_separation_arcsec(
        d_first["ra"], d_first["dec"], d_last["ra"], d_last["dec"]
    )

    return total_sep_arcsec < min_motion_arcsec


def flag_filter_response(
    tracklet: Tracklet,
    stack: Optional[List[EpochImage]] = None,
    correlation_threshold: float = 0.85,
) -> Tuple[bool, float]:
    """Flag tracklets whose flux variations correlate with Linear Variable Filter (LVF) shifts.

    TODO(VERIFY):
    In real SPHEREx flight data, a stationary source observed at varying focal plane
    locations across epochs will experience changing effective central wavelengths.
    If the source has an intrinsic spectral slope (e.g. red stellar continuum), its
    measured flux will vary systematically with wavelength, mimicking a transient.
    Because true asteroids also possess spectral slopes and rotational lightcurves,
    this filter provides an informative diagnostic flag and correlation score rather
    than a hard veto. Once flight filter transmission profiles are published, this
    heuristic should be updated.

    Args:
        tracklet: Tracklet candidate.
        stack: Optional aligned EpochImage stack.
        correlation_threshold: Absolute Pearson correlation threshold for flagging.

    Returns:
        Tuple of (is_flagged_bool, correlation_score_0_to_1).
    """
    if len(tracklet.detections) < 3:
        return False, 0.0

    fluxes = [float(d["flux"]) for d in tracklet.detections]
    wavelengths = [float(d.get("wavelength_um", 0.0)) for d in tracklet.detections]

    std_f = float(np.std(fluxes))
    std_w = float(np.std(wavelengths))

    if std_f < 1e-4 or std_w < 1e-4:
        return False, 0.0

    # Pearson correlation coefficient between flux and wavelength
    corr_matrix = np.corrcoef(fluxes, wavelengths)
    r_val = float(corr_matrix[0, 1]) if not np.isnan(corr_matrix[0, 1]) else 0.0
    abs_r = min(1.0, max(0.0, abs(r_val)))

    is_flagged = abs_r >= correlation_threshold
    return is_flagged, round(abs_r, 3)


def reject_bad_fit(
    tracklet: Tracklet,
    max_residual_arcsec: float = 3.5,
) -> bool:
    """Reject tracklets with excessive trajectory fit residuals.

    Args:
        tracklet: Tracklet candidate.
        max_residual_arcsec: Maximum permissible RMS fit residual in arcseconds.

    Returns:
        True if rejected (poor fit), False if valid tracklet.
    """
    return tracklet.rms_residual_arcsec > max_residual_arcsec
