"""SPHEREx Sky Diary — Tracklet Linking & Trajectory Fitting (Module 3).

Links transient detections across observation epochs into constant-velocity
solar system orbital tracklets using seed-and-predict searching, robust
least-squares trajectory fitting, and greedy conflict resolution.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np


@dataclass
class Tracklet:
    """Linked trajectory candidate consisting of multiple epoch detections."""

    tracklet_id: str
    detections: List[Dict[str, Any]]
    ref_ra: float
    ref_dec: float
    ref_date: datetime
    ra_rate_arcsec_per_day: float  # dRA/dt * cos(dec)
    dec_rate_arcsec_per_day: float  # dDec/dt
    rms_residual_arcsec: float
    reduced_chi2: float
    metadata: Dict[str, Any] = field(default_factory=dict)


def _parse_date(date_val: Union[str, datetime]) -> datetime:
    """Parse ISO string or datetime to UTC datetime."""
    if isinstance(date_val, datetime):
        return date_val if date_val.tzinfo else date_val.replace(tzinfo=timezone.utc)
    # Standard string parse
    clean = str(date_val).replace("Z", "+00:00")
    dt = datetime.fromisoformat(clean)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def angular_separation_arcsec(
    ra1: float,
    dec1: float,
    ra2: float,
    dec2: float,
) -> Tuple[float, float, float]:
    """Compute (dRA*cos(dec), dDec, total_separation) in arcseconds with wraparound handling."""
    # RA difference in [-180, 180]
    dra_deg = ((ra2 - ra1 + 180.0) % 360.0) - 180.0
    mean_dec = math.radians((dec1 + dec2) / 2.0)
    dra_cosdec_arcsec = dra_deg * math.cos(mean_dec) * 3600.0
    ddec_arcsec = (dec2 - dec1) * 3600.0
    total_arcsec = math.hypot(dra_cosdec_arcsec, ddec_arcsec)
    return dra_cosdec_arcsec, ddec_arcsec, total_arcsec


def fit_constant_velocity_track(
    detections: List[Dict[str, Any]],
    pos_sigma_arcsec: float = 0.20,
) -> Tuple[float, float, float, float, float, float]:
    """Fit a constant-velocity linear trajectory through detections.

    Returns:
        Tuple of (ref_ra, ref_dec, ra_rate_arcsec_per_day, dec_rate_arcsec_per_day, rms_residual_arcsec, red_chi2)
    """
    sorted_dets = sorted(detections, key=lambda d: _parse_date(d["date"]))
    t0 = _parse_date(sorted_dets[0]["date"])

    times_days = np.array(
        [(_parse_date(d["date"]) - t0).total_seconds() / 86400.0 for d in sorted_dets],
        dtype=np.float64,
    )
    ras = np.array([float(d["ra"]) for d in sorted_dets], dtype=np.float64)
    decs = np.array([float(d["dec"]) for d in sorted_dets], dtype=np.float64)

    ref_ra0 = ras[0]
    ref_dec0 = decs[0]
    cos_dec0 = math.cos(math.radians(ref_dec0))

    # Unwrap RA relative to the first detection
    unwrapped_dra_deg = ((ras - ref_ra0 + 180.0) % 360.0) - 180.0
    u_arcsec = unwrapped_dra_deg * cos_dec0 * 3600.0
    v_arcsec = (decs - ref_dec0) * 3600.0

    n_points = len(sorted_dets)
    if n_points == 2:
        dt = times_days[1] - times_days[0]
        if abs(dt) < 1e-4:
            ra_rate = 0.0
            dec_rate = 0.0
        else:
            ra_rate = float((u_arcsec[1] - u_arcsec[0]) / dt)
            dec_rate = float((v_arcsec[1] - v_arcsec[0]) / dt)
        rms = 0.0
        red_chi2 = 1.0
        return ref_ra0, ref_dec0, ra_rate, dec_rate, rms, red_chi2

    # Linear regression: u(t) = u0 + ra_rate * t, v(t) = v0 + dec_rate * t
    fit_u = np.polyfit(times_days, u_arcsec, 1)  # [slope, intercept]
    fit_v = np.polyfit(times_days, v_arcsec, 1)

    ra_rate = float(fit_u[0])
    u0 = float(fit_u[1])
    dec_rate = float(fit_v[0])
    v0 = float(fit_v[1])

    # Residuals
    model_u = u0 + ra_rate * times_days
    model_v = v0 + dec_rate * times_days

    res_u = u_arcsec - model_u
    res_v = v_arcsec - model_v
    tot_residuals = np.hypot(res_u, res_v)
    rms = float(np.sqrt(np.mean(tot_residuals**2)))

    # Reduced chi-squared
    dof = max(1, 2 * n_points - 4)
    chi2 = float(np.sum((tot_residuals / pos_sigma_arcsec) ** 2))
    red_chi2 = chi2 / dof

    # Adjust reference position to the fitted intercept at t=0
    ref_dec = ref_dec0 + (v0 / 3600.0)
    cos_ref = math.cos(math.radians(ref_dec))
    ref_ra = (ref_ra0 + (u0 / (cos_ref * 3600.0))) % 360.0

    return ref_ra, ref_dec, ra_rate, dec_rate, rms, red_chi2


def link_detections(
    detections_by_epoch: Dict[str, List[Dict[str, Any]]],
    config: Optional[Dict[str, Any]] = None,
) -> List[Tracklet]:
    """Link multi-epoch point source detections into moving object tracklets.

    Args:
        detections_by_epoch: Mapping of epoch_id to list of detection dicts.
        config: Optional detection configuration dictionary.

    Returns:
        List of conflict-resolved Tracklet candidate instances.
    """
    cfg = config or {}
    link_cfg = cfg.get("linking", {})

    max_rate = float(link_cfg.get("max_rate_arcsec_per_day", 45.0))
    min_rate = float(link_cfg.get("min_rate_arcsec_per_day", 2.0))
    match_rad = float(link_cfg.get("match_radius_arcsec", 5.5))
    min_dets = int(link_cfg.get("min_detections", 3))
    max_res = float(link_cfg.get("max_fit_residual_arcsec", 3.5))

    # Flatten all detections and assign unique IDs
    all_detections: List[Dict[str, Any]] = []
    det_counter = 0
    for ep_id, det_list in detections_by_epoch.items():
        for d in det_list:
            d_copy = copy.deepcopy(d)
            d_copy["_det_id"] = f"det_{det_counter:04d}"
            det_counter += 1
            all_detections.append(d_copy)

    if not all_detections:
        return []

    # Group by epoch
    epochs_present = sorted(list(detections_by_epoch.keys()))
    if len(epochs_present) < min_dets:
        return []

    # 1. Seed candidate tracklets from pairs across different epochs
    candidate_tracks: List[Dict[str, Any]] = []

    for i in range(len(all_detections)):
        d1 = all_detections[i]
        t1 = _parse_date(d1["date"])
        for j in range(i + 1, len(all_detections)):
            d2 = all_detections[j]
            if d1["epoch_id"] == d2["epoch_id"]:
                continue

            t2 = _parse_date(d2["date"])
            delta_days = (t2 - t1).total_seconds() / 86400.0
            if abs(delta_days) < 1e-4:
                continue

            dra_cos, ddec, sep_arcsec = angular_separation_arcsec(
                d1["ra"], d1["dec"], d2["ra"], d2["dec"]
            )
            rate_arcsec_per_day = sep_arcsec / abs(delta_days)

            # Plausible velocity gate
            if not (min_rate <= rate_arcsec_per_day <= max_rate):
                continue

            ra_rate = dra_cos / delta_days
            dec_rate = ddec / delta_days

            # 2. Predict positions in other epochs and attach closest candidate
            track_dets = [d1, d2]
            attached_epochs = {d1["epoch_id"], d2["epoch_id"]}

            for target_epoch in epochs_present:
                if target_epoch in attached_epochs:
                    continue

                candidates_in_epoch = detections_by_epoch.get(target_epoch, [])
                if not candidates_in_epoch:
                    continue

                target_date = _parse_date(candidates_in_epoch[0]["date"])
                t_diff = (target_date - t1).total_seconds() / 86400.0

                # Predicted position
                pred_dec = d1["dec"] + ((dec_rate * t_diff) / 3600.0)
                cos_pred = math.cos(math.radians(pred_dec))
                pred_ra = (d1["ra"] + ((ra_rate * t_diff) / (cos_pred * 3600.0))) % 360.0

                # Find closest candidate within match_radius
                best_match = None
                min_sep = match_rad + 1.0

                for cand in all_detections:
                    if cand["epoch_id"] != target_epoch:
                        continue
                    _, _, dist = angular_separation_arcsec(pred_ra, pred_dec, cand["ra"], cand["dec"])
                    if dist < min_sep:
                        min_sep = dist
                        best_match = cand

                if best_match is not None and min_sep <= match_rad:
                    track_dets.append(best_match)
                    attached_epochs.add(target_epoch)

            # 3. If track has enough detections, fit trajectory
            if len(track_dets) >= min_dets:
                ref_ra, ref_dec, fit_ra_rate, fit_dec_rate, rms_res, red_chi2 = fit_constant_velocity_track(
                    track_dets
                )
                if rms_res <= max_res:
                    candidate_tracks.append(
                        {
                            "detections": track_dets,
                            "det_ids": set(d["_det_id"] for d in track_dets),
                            "ref_ra": ref_ra,
                            "ref_dec": ref_dec,
                            "ref_date": _parse_date(track_dets[0]["date"]),
                            "ra_rate": fit_ra_rate,
                            "dec_rate": fit_dec_rate,
                            "rms": rms_res,
                            "chi2": red_chi2,
                        }
                    )

    if not candidate_tracks:
        return []

    # 4. Conflict resolution: sort by (most detections descending, lowest rms ascending)
    candidate_tracks.sort(key=lambda t: (-len(t["detections"]), t["rms"]))

    assigned_det_ids: Set[str] = set()
    final_tracklets: List[Tracklet] = []
    track_count = 0

    for cand in candidate_tracks:
        # Check if detections are unassigned
        overlapping = cand["det_ids"] & assigned_det_ids
        if len(overlapping) > 0:
            continue

        assigned_det_ids.update(cand["det_ids"])
        track_count += 1
        t_id = f"trk_{track_count:03d}"

        final_tracklets.append(
            Tracklet(
                tracklet_id=t_id,
                detections=sorted(cand["detections"], key=lambda d: _parse_date(d["date"])),
                ref_ra=round(cand["ref_ra"], 6),
                ref_dec=round(cand["ref_dec"], 6),
                ref_date=cand["ref_date"],
                ra_rate_arcsec_per_day=round(cand["ra_rate"], 3),
                dec_rate_arcsec_per_day=round(cand["dec_rate"], 3),
                rms_residual_arcsec=round(cand["rms"], 3),
                reduced_chi2=round(cand["chi2"], 3),
            )
        )

    return final_tracklets
