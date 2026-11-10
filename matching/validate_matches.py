"""SPHEREx Sky Diary — Catalog Matching Validation & Performance Reporting.

Evaluates known asteroid recovery recall, identifies missed bodies with physical causes
(faint magnitude, high rate), flags marginal matches, and produces structured JSON
and Markdown validation reports.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from matching.query import KnownObject

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]


def evaluate_catalog_matching(
    candidates_catalog: Dict[str, Any],
    known_objects: List[KnownObject],
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Evaluate detector and matching performance against known Solar System bodies.

    Args:
        candidates_catalog: Full candidates JSON dictionary conforming to schema 1.0.
        known_objects: List of KnownObject ephemerides predicted in the region.
        config: Optional configuration dictionary.

    Returns:
        Structured evaluation metrics dictionary.
    """
    movers = candidates_catalog.get("movers", [])
    is_synthetic = any(m.get("is_synthetic", False) for m in movers)

    cfg = config or {}
    match_cfg = cfg.get("matching", {})
    pos_tol = float(match_cfg.get("position_tolerance_arcsec", 8.0))

    # Map candidate matches by matched name
    matched_candidates_by_name: Dict[str, Dict[str, Any]] = {}
    known_candidates: List[Dict[str, Any]] = []
    unknown_candidates: List[Dict[str, Any]] = []

    for m in movers:
        m_type = m.get("type")
        if m_type == "known":
            known_candidates.append(m)
            match_name = m.get("match_name")
            if match_name:
                matched_candidates_by_name[match_name] = m
        else:
            unknown_candidates.append(m)

    # 1. Known objects recovery analysis
    recovered_objects: List[Dict[str, Any]] = []
    missed_objects: List[Dict[str, Any]] = []
    match_distances: List[float] = []

    for obj in known_objects:
        speed = float(np.hypot(obj.mean_ra_rate, obj.mean_dec_rate))

        if obj.name in matched_candidates_by_name:
            cand = matched_candidates_by_name[obj.name]
            dist = float(cand.get("match_distance_arcsec", 0.0))
            match_distances.append(dist)
            recovered_objects.append(
                {
                    "name": obj.name,
                    "designation": obj.designation,
                    "object_type": obj.object_type,
                    "magnitude": obj.magnitude,
                    "speed_arcsec_day": round(speed, 2),
                    "matched_candidate_id": cand.get("object_id"),
                    "match_distance_arcsec": dist,
                    "matched_epochs": cand.get("matched_epoch_count", len(cand.get("detections", []))),
                }
            )
        else:
            # Diagnose reason for miss
            reason = "unrecovered_tracklet"
            if obj.magnitude is not None and obj.magnitude > 19.0:
                reason = "faint_magnitude_below_snr_threshold"
            elif speed > 45.0:
                reason = "fast_motion_exceeded_rate_limit"

            missed_objects.append(
                {
                    "name": obj.name,
                    "designation": obj.designation,
                    "object_type": obj.object_type,
                    "magnitude": obj.magnitude,
                    "speed_arcsec_day": round(speed, 2),
                    "probable_cause": reason,
                    "epoch_coverage": len(obj.positions),
                }
            )

    total_known = len(known_objects)
    num_recovered = len(recovered_objects)
    recall = round(num_recovered / total_known, 4) if total_known > 0 else 0.0

    # 2. Match quality & marginal / poor match flagging
    poor_matches: List[Dict[str, Any]] = []
    poor_match_threshold = 0.70 * pos_tol  # e.g., > 5.6" for 8" tolerance
    for cand in known_candidates:
        dist = cand.get("match_distance_arcsec")
        if dist is not None and dist > poor_match_threshold:
            poor_matches.append(
                {
                    "object_id": cand.get("object_id"),
                    "match_name": cand.get("match_name"),
                    "match_distance_arcsec": dist,
                    "tolerance_arcsec": pos_tol,
                    "confidence": cand.get("confidence"),
                }
            )

    mean_dist = round(float(np.mean(match_distances)), 3) if match_distances else 0.0
    median_dist = round(float(np.median(match_distances)), 3) if match_distances else 0.0

    report = {
        "evaluation_timestamp": datetime.now(timezone.utc).isoformat(),
        "is_synthetic": is_synthetic,
        "region": candidates_catalog.get("region", {}),
        "summary": {
            "total_candidates": len(movers),
            "labeled_known_count": len(known_candidates),
            "labeled_unknown_count": len(unknown_candidates),
            "total_known_in_field": total_known,
            "recovered_known_count": num_recovered,
            "missed_known_count": len(missed_objects),
            "known_recovery_recall": recall,
            "mean_match_distance_arcsec": mean_dist,
            "median_match_distance_arcsec": median_dist,
            "poor_match_count": len(poor_matches),
        },
        "recovered_objects": recovered_objects,
        "missed_objects": missed_objects,
        "poor_matches": poor_matches,
    }

    return report


def generate_markdown_report(report: Dict[str, Any]) -> str:
    """Format evaluation report as a clean Markdown document."""
    summary = report["summary"]
    is_synthetic = report.get("is_synthetic", False)

    badge = (
        "> [!IMPORTANT]\n"
        "> **SYNTHETIC TEST BENCHMARK:** Evaluated on synthetic mock data with known injected movers.\n"
        "> All metrics reflect algorithmic performance on synthetic test sets.\n\n"
        if is_synthetic
        else ""
    )

    lines = [
        "# SPHEREx Sky Diary — Catalog Matching Validation Report\n",
        badge,
        f"**Timestamp:** `{report.get('evaluation_timestamp')}`  ",
        f"**Target Region:** `{report.get('region', {}).get('name', 'unknown')}`  \n",
        "## 1. Executive Summary\n",
        "| Metric | Value | Description |",
        "| :--- | :--- | :--- |",
        f"| **Total Candidates** | `{summary['total_candidates']}` | Mover tracklets from detection pipeline |",
        f"| **Labeled Known** | `{summary['labeled_known_count']}` | Successfully matched to catalog ephemeris |",
        f"| **Labeled Unknown** | `{summary['labeled_unknown_count']}` | Unmatched (new mover / candidate) |",
        f"| **Known Bodies in Field** | `{summary['total_known_in_field']}` | Catalog bodies with ephemerides in cone |",
        f"| **Known Recovery Recall** | **`{summary['known_recovery_recall'] * 100:.1f}%`** | Recovered / Total predicted in field |",
        f"| **Mean Separation Residual** | `{summary['mean_match_distance_arcsec']}\"` | Mean astrometric offset from ephemeris |",
        f"| **Median Separation Residual**| `{summary['median_match_distance_arcsec']}\"` | Robust median astrometric offset |",
        f"| **Marginal Matches** | `{summary['poor_match_count']}` | Detections approaching tolerance limit |\n",
        "## 2. Recovered Known Asteroids\n",
    ]

    recovered = report.get("recovered_objects", [])
    if recovered:
        lines.extend(
            [
                "| Name | Type | V Mag | Speed (arcsec/day) | Candidate ID | Residual | Matched Epochs |",
                "| :--- | :--- | :---: | :---: | :---: | :---: | :---: |",
            ]
        )
        for r in recovered:
            mag_str = f"{r['magnitude']:.1f}" if r["magnitude"] is not None else "N/A"
            lines.append(
                f"| **{r['name']}** | {r['object_type']} | {mag_str} | {r['speed_arcsec_day']} | "
                f"`{r['matched_candidate_id']}` | {r['match_distance_arcsec']:.2f}\" | {r['matched_epochs']} |"
            )
    else:
        lines.append("_No known asteroids were recovered in this run._\n")

    lines.append("\n## 3. Missed Known Asteroids\n")
    missed = report.get("missed_objects", [])
    if missed:
        lines.extend(
            [
                "| Name | Type | V Mag | Speed (arcsec/day) | Diagnostic Cause |",
                "| :--- | :--- | :---: | :---: | :--- |",
            ]
        )
        for m in missed:
            mag_str = f"{m['magnitude']:.1f}" if m["magnitude"] is not None else "N/A"
            lines.append(
                f"| **{m['name']}** | {m['object_type']} | {mag_str} | {m['speed_arcsec_day']} | `{m['probable_cause']}` |"
            )
    else:
        lines.append("_Zero catalog asteroids were missed._\n")

    if report.get("poor_matches"):
        lines.append("\n## 4. Marginal / Poor Matches\n")
        lines.extend(
            [
                "| Candidate ID | Matched Name | Residual | Tolerance | Confidence |",
                "| :--- | :--- | :---: | :---: | :---: |",
            ]
        )
        for p in report["poor_matches"]:
            lines.append(
                f"| `{p['object_id']}` | {p['match_name']} | {p['match_distance_arcsec']:.2f}\" | {p['tolerance_arcsec']:.1f}\" | {p['confidence']:.3f} |"
            )

    return "\n".join(lines) + "\n"


def save_validation_reports(
    report: Dict[str, Any],
    json_path: Path | str = REPO_ROOT / "data" / "output" / "validation_report.json",
    md_path: Path | str = REPO_ROOT / "data" / "output" / "validation_report.md",
) -> Tuple[Path, Path]:
    """Write validation reports in both JSON and Markdown formats."""
    j_path = Path(json_path)
    m_path = Path(md_path)

    j_path.parent.mkdir(parents=True, exist_ok=True)
    m_path.parent.mkdir(parents=True, exist_ok=True)

    with open(j_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    md_content = generate_markdown_report(report)
    with open(m_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    logger.info("Saved validation reports to %s and %s", j_path, m_path)
    return j_path, m_path
