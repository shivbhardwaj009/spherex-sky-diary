"""SPHEREx Sky Diary — Solar System Candidate Matching Engine.

Cross-matches detected candidate tracklets against predicted Solar System ephemerides,
labels Known vs Unknown movers, resolves ambiguities, and updates confidence scores.
"""

from __future__ import annotations

import copy
import logging
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from astropy.coordinates import angular_separation

from matching.predict import predict_positions
from matching.query import KnownObject, PredictedPosition

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    """Detailed result of matching a candidate against a known object."""

    known_object: KnownObject
    mean_distance_arcsec: float
    matched_epoch_count: int
    total_epoch_count: int
    matched_fraction: float
    rate_diff_arcsec_day: float
    direction_diff_deg: float
    is_valid: bool


def _angular_separation_arcsec(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    """Compute exact spherical angular separation in arcseconds using astropy."""
    # Convert degrees to radians
    r1, d1 = math.radians(ra1), math.radians(dec1)
    r2, d2 = math.radians(ra2), math.radians(dec2)
    sep_rad = angular_separation(r1, d1, r2, d2)
    return math.degrees(sep_rad) * 3600.0


def _diff_angle_deg(ang1: float, ang2: float) -> float:
    """Smallest positive angular difference between two direction angles (0 to 180 deg)."""
    diff = abs((ang1 - ang2 + 180.0) % 360.0 - 180.0)
    return diff


def evaluate_single_match(
    candidate: Dict[str, Any],
    known_object: KnownObject,
    pos_tol_arcsec: float,
    rate_tol_arcsec_day: float,
    dir_tol_deg: float,
    min_fraction: float,
    min_epochs: int,
) -> MatchResult:
    """Evaluate tracklet consistency against one known object."""
    detections = candidate.get("detections", [])
    if not detections:
        return MatchResult(
            known_object=known_object,
            mean_distance_arcsec=9999.0,
            matched_epoch_count=0,
            total_epoch_count=0,
            matched_fraction=0.0,
            rate_diff_arcsec_day=999.0,
            direction_diff_deg=180.0,
            is_valid=False,
        )

    # Predict known object positions for all candidate detection epochs
    predicted_list = predict_positions(
        known_object,
        [{"epoch_id": d["epoch_id"], "date": d["date"]} for d in detections],
    )
    predicted_by_epoch = {p.epoch_id: p for p in predicted_list}

    distances: List[float] = []
    matched_count = 0

    for det in detections:
        ep_id = det["epoch_id"]
        pred_p = predicted_by_epoch.get(ep_id)
        if pred_p is None:
            continue

        sep_arcsec = _angular_separation_arcsec(
            det["ra"], det["dec"], pred_p.ra, pred_p.dec
        )
        if sep_arcsec <= pos_tol_arcsec:
            matched_count += 1
            distances.append(sep_arcsec)

    total_count = len(detections)
    frac = matched_count / total_count if total_count > 0 else 0.0
    mean_dist = float(sum(distances) / len(distances)) if distances else 9999.0

    # Compare motion vectors
    cand_motion = candidate.get("motion", {})
    c_ra_rate = float(cand_motion.get("ra_rate_arcsec_per_day", 0.0))
    c_dec_rate = float(cand_motion.get("dec_rate_arcsec_per_day", 0.0))
    c_speed = math.hypot(c_ra_rate, c_dec_rate)
    c_dir = math.degrees(math.atan2(c_dec_rate, c_ra_rate)) % 360.0

    # Object motion rate
    p_ra_rate = float(known_object.mean_ra_rate)
    p_dec_rate = float(known_object.mean_dec_rate)
    p_speed = math.hypot(p_ra_rate, p_dec_rate)
    p_dir = math.degrees(math.atan2(p_dec_rate, p_ra_rate)) % 360.0

    rate_diff = abs(c_speed - p_speed)

    # If speed is non-trivial (> 2.0 arcsec/day), verify direction
    if c_speed > 2.0 and p_speed > 2.0:
        dir_diff = _diff_angle_deg(c_dir, p_dir)
    else:
        dir_diff = 0.0

    # Validation criteria
    is_valid = (
        matched_count >= min_epochs
        and frac >= min_fraction
        and rate_diff <= rate_tol_arcsec_day
        and dir_diff <= dir_tol_deg
    )

    return MatchResult(
        known_object=known_object,
        mean_distance_arcsec=mean_dist,
        matched_epoch_count=matched_count,
        total_epoch_count=total_count,
        matched_fraction=frac,
        rate_diff_arcsec_day=rate_diff,
        direction_diff_deg=dir_diff,
        is_valid=is_valid,
    )


def match_candidates(
    candidates: List[Dict[str, Any]],
    known_objects: List[KnownObject],
    config: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Cross-match mover candidates against known Solar System objects.

    Modifies candidates in-place and returns the updated list.

    Args:
        candidates: List of mover dictionaries from candidate catalog.
        known_objects: List of KnownObject ephemerides.
        config: Matching parameters configuration dictionary.

    Returns:
        Updated list of candidate dictionaries.
    """
    cfg = config or {}
    match_cfg = cfg.get("matching", {})

    pos_tol = float(match_cfg.get("position_tolerance_arcsec", 8.0))
    rate_tol = float(match_cfg.get("rate_tolerance_arcsec_per_day", 8.0))
    dir_tol = float(match_cfg.get("direction_tolerance_deg", 35.0))
    min_fraction = float(match_cfg.get("min_matched_fraction", 0.50))
    min_epochs = int(match_cfg.get("min_matched_epochs", 2))

    updated_candidates: List[Dict[str, Any]] = []

    for cand in candidates:
        cand_copy = copy.deepcopy(cand)

        valid_matches: List[MatchResult] = []
        for obj in known_objects:
            res = evaluate_single_match(
                candidate=cand_copy,
                known_object=obj,
                pos_tol_arcsec=pos_tol,
                rate_tol_arcsec_day=rate_tol,
                dir_tol_deg=dir_tol,
                min_fraction=min_fraction,
                min_epochs=min_epochs,
            )
            if res.is_valid:
                valid_matches.append(res)

        if valid_matches:
            # Sort by mean separation distance ascending
            valid_matches.sort(key=lambda m: m.mean_distance_arcsec)
            best_match = valid_matches[0]
            runner_up = valid_matches[1] if len(valid_matches) > 1 else None

            cand_copy["type"] = "known"
            cand_copy["match_name"] = best_match.known_object.name
            cand_copy["match_distance_arcsec"] = round(best_match.mean_distance_arcsec, 3)
            cand_copy["matched_epoch_count"] = best_match.matched_epoch_count
            cand_copy["runner_up_match"] = runner_up.known_object.name if runner_up else None

            # Boost confidence for robust ephemeris match
            curr_conf = float(cand_copy.get("confidence", 0.80))
            # Match confidence scaling: 0.98 for 0" distance down to 0.90 at tolerance limit
            dist_factor = min(1.0, best_match.mean_distance_arcsec / max(0.1, pos_tol))
            match_conf = 0.98 - 0.08 * dist_factor
            cand_copy["confidence"] = round(max(curr_conf, match_conf), 3)

            logger.info(
                "Matched %s -> %s (mean dist: %.2f\", %d/%d epochs)",
                cand_copy.get("object_id"),
                cand_copy["match_name"],
                best_match.mean_distance_arcsec,
                best_match.matched_epoch_count,
                best_match.total_epoch_count,
            )
        else:
            cand_copy["type"] = "unknown"
            cand_copy["match_name"] = None
            cand_copy.pop("match_distance_arcsec", None)
            cand_copy.pop("matched_epoch_count", None)
            cand_copy.pop("runner_up_match", None)

        updated_candidates.append(cand_copy)

    return updated_candidates

