"""SPHEREx Sky Diary — Mover Confidence Scoring (Module 3).

Computes calibrated detection confidence scores in [0.0, 1.0] from a composite
of signal-to-noise ratio, astrometric fit residuals, number of confirmed epochs,
and filter-response chromatic stability.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional

import numpy as np

from detection.movers.linking import Tracklet


def compute_confidence(
    tracklet: Tracklet,
    filter_response_score: float = 0.0,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Compute confidence score in [0.0, 1.0] for a moving object tracklet.

    Scoring Formulation:
    --------------------
    1. S/N Subscore:
       c_snr = min(1.0, mean_snr / snr_scale)       (default scale: 15.0)
    2. Epoch Count Subscore:
       c_det = min(1.0, max(0.0, (n_dets - 2) / 4.0)) (3 epochs -> 0.25, 6 epochs -> 1.0)
    3. Trajectory Fit Subscore:
       c_fit = max(0.0, 1.0 - (rms_residual / max_residual_scale)) (0" -> 1.0, 3" -> 0.0)
    4. Chromatic Cleanliness Subscore:
       c_filter = max(0.0, 1.0 - filter_response_score)

    Weighted Composite Score:
       Z = w_snr * c_snr + w_det * c_det + w_fit * c_fit + w_filter * c_filter
       confidence = clip(Z, 0.0, 1.0)

    Args:
        tracklet: Tracklet candidate.
        filter_response_score: Score from flag_filter_response in [0, 1].
        config: Optional detection configuration dictionary.

    Returns:
        Confidence score rounded to 3 decimal places in [0.0, 1.0].
    """
    cfg = config or {}
    score_cfg = cfg.get("scoring", {})
    weights = score_cfg.get(
        "weights",
        {"snr": 0.35, "detections": 0.30, "residual": 0.25, "filter_response": 0.10},
    )

    snr_scale = float(score_cfg.get("snr_scale", 15.0))
    max_res_scale = float(score_cfg.get("max_residual_scale", 3.0))

    w_snr = float(weights.get("snr", 0.35))
    w_det = float(weights.get("detections", 0.30))
    w_fit = float(weights.get("residual", 0.25))
    w_filter = float(weights.get("filter_response", 0.10))

    # 1. Mean S/N component
    snrs = [float(d.get("snr", 5.0)) for d in tracklet.detections]
    mean_snr = float(np.mean(snrs)) if snrs else 5.0
    c_snr = min(1.0, max(0.0, mean_snr / snr_scale))

    # 2. Number of detections component
    n_dets = len(tracklet.detections)
    c_det = min(1.0, max(0.0, (n_dets - 2) / 4.0))

    # 3. Fit quality component
    rms_res = tracklet.rms_residual_arcsec
    c_fit = max(0.0, 1.0 - (rms_res / max_res_scale))

    # 4. Filter response component
    c_filter = max(0.0, 1.0 - float(filter_response_score))

    # Weighted composite sum
    total_score = (
        w_snr * c_snr
        + w_det * c_det
        + w_fit * c_fit
        + w_filter * c_filter
    )

    norm_sum = w_snr + w_det + w_fit + w_filter
    if norm_sum > 0:
        total_score /= norm_sum

    confidence = min(1.0, max(0.0, total_score))
    return round(float(confidence), 3)
