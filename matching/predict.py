"""SPHEREx Sky Diary — Position Prediction & Interpolation.

Interpolates or propagates predicted celestial positions (RA/Dec) and apparent motion
rates for known Solar System objects across arbitrary observation epochs.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from matching.query import KnownObject, PredictedPosition


def _parse_utc_timestamp(date_val: str | datetime) -> datetime:
    """Parse string or datetime to timezone-aware UTC datetime."""
    if isinstance(date_val, datetime):
        return date_val
    norm = date_val.replace("Z", "+00:00")
    return datetime.fromisoformat(norm)


def _diff_ra_deg(ra2: float, ra1: float) -> float:
    """Signed shortest angular difference ra2 - ra1 in degrees (-180 to +180)."""
    diff = (ra2 - ra1 + 180.0) % 360.0 - 180.0
    return diff


def predict_positions(
    known_object: KnownObject,
    target_epochs: List[Dict[str, str]],
) -> List[PredictedPosition]:
    """Generate or interpolate positions for a known object at specified observation epochs.

    Args:
        known_object: KnownObject containing ephemeris positions.
        target_epochs: List of epoch dictionaries with 'epoch_id' and 'date'.

    Returns:
        List of PredictedPosition aligned with target_epochs.
    """
    if not known_object.positions:
        return []

    # Map existing positions by normalized ISO date
    existing_by_date: Dict[str, PredictedPosition] = {}
    for p in known_object.positions:
        p_dt = _parse_utc_timestamp(p.date)
        existing_by_date[p_dt.isoformat()] = p

    # Sort existing positions chronologically
    sorted_positions = sorted(
        known_object.positions,
        key=lambda p: _parse_utc_timestamp(p.date),
    )

    results: List[PredictedPosition] = []

    for ep in target_epochs:
        ep_id = ep.get("epoch_id", "epoch")
        ep_date_str = ep["date"]
        ep_dt = _parse_utc_timestamp(ep_date_str)
        iso_key = ep_dt.isoformat()

        # 1. Exact date match exists
        if iso_key in existing_by_date:
            pos = existing_by_date[iso_key]
            results.append(
                PredictedPosition(
                    epoch_id=ep_id,
                    date=ep_date_str,
                    ra=pos.ra,
                    dec=pos.dec,
                    ra_rate_arcsec_per_day=pos.ra_rate_arcsec_per_day,
                    dec_rate_arcsec_per_day=pos.dec_rate_arcsec_per_day,
                    v_mag=pos.v_mag,
                )
            )
            continue

        # 2. Need interpolation or extrapolation
        pos_dates = [_parse_utc_timestamp(p.date) for p in sorted_positions]

        # Case A: Only one position exists -> extrapolate with constant velocity
        if len(sorted_positions) == 1:
            base_pos = sorted_positions[0]
            dt_days = (ep_dt - pos_dates[0]).total_seconds() / 86400.0
            cos_dec = max(0.01, math.cos(math.radians(base_pos.dec)))

            d_ra_deg = (base_pos.ra_rate_arcsec_per_day * dt_days) / (3600.0 * cos_dec)
            d_dec_deg = (base_pos.dec_rate_arcsec_per_day * dt_days) / 3600.0

            pred_ra = (base_pos.ra + d_ra_deg) % 360.0
            pred_dec = max(-90.0, min(90.0, base_pos.dec + d_dec_deg))

            results.append(
                PredictedPosition(
                    epoch_id=ep_id,
                    date=ep_date_str,
                    ra=pred_ra,
                    dec=pred_dec,
                    ra_rate_arcsec_per_day=base_pos.ra_rate_arcsec_per_day,
                    dec_rate_arcsec_per_day=base_pos.dec_rate_arcsec_per_day,
                    v_mag=base_pos.v_mag,
                )
            )
            continue

        # Case B: ep_dt falls between two known positions -> linear interpolation with RA wrapping
        interpolated = False
        for idx in range(len(pos_dates) - 1):
            t1 = pos_dates[idx]
            t2 = pos_dates[idx + 1]
            if t1 <= ep_dt <= t2:
                total_span = (t2 - t1).total_seconds()
                frac = 0.0 if total_span == 0 else (ep_dt - t1).total_seconds() / total_span

                p1 = sorted_positions[idx]
                p2 = sorted_positions[idx + 1]

                ra_diff = _diff_ra_deg(p2.ra, p1.ra)
                pred_ra = (p1.ra + frac * ra_diff) % 360.0
                pred_dec = p1.dec + frac * (p2.dec - p1.dec)

                pred_ra_rate = p1.ra_rate_arcsec_per_day + frac * (
                    p2.ra_rate_arcsec_per_day - p1.ra_rate_arcsec_per_day
                )
                pred_dec_rate = p1.dec_rate_arcsec_per_day + frac * (
                    p2.dec_rate_arcsec_per_day - p1.dec_rate_arcsec_per_day
                )

                mag = None
                if p1.v_mag is not None and p2.v_mag is not None:
                    mag = p1.v_mag + frac * (p2.v_mag - p1.v_mag)

                results.append(
                    PredictedPosition(
                        epoch_id=ep_id,
                        date=ep_date_str,
                        ra=pred_ra,
                        dec=pred_dec,
                        ra_rate_arcsec_per_day=pred_ra_rate,
                        dec_rate_arcsec_per_day=pred_dec_rate,
                        v_mag=mag,
                    )
                )
                interpolated = True
                break

        if interpolated:
            continue

        # Case C: Extrapolate beyond range
        if ep_dt < pos_dates[0]:
            ref_p = sorted_positions[0]
            ref_t = pos_dates[0]
        else:
            ref_p = sorted_positions[-1]
            ref_t = pos_dates[-1]

        dt_days = (ep_dt - ref_t).total_seconds() / 86400.0
        cos_dec = max(0.01, math.cos(math.radians(ref_p.dec)))
        d_ra_deg = (ref_p.ra_rate_arcsec_per_day * dt_days) / (3600.0 * cos_dec)
        d_dec_deg = (ref_p.dec_rate_arcsec_per_day * dt_days) / 3600.0

        pred_ra = (ref_p.ra + d_ra_deg) % 360.0
        pred_dec = max(-90.0, min(90.0, ref_p.dec + d_dec_deg))

        results.append(
            PredictedPosition(
                epoch_id=ep_id,
                date=ep_date_str,
                ra=pred_ra,
                dec=pred_dec,
                ra_rate_arcsec_per_day=ref_p.ra_rate_arcsec_per_day,
                dec_rate_arcsec_per_day=ref_p.dec_rate_arcsec_per_day,
                v_mag=ref_p.v_mag,
            )
        )

    return results
