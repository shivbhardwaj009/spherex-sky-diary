"""SPHEREx Sky Diary — Mover Detection Evaluation (Module 3).

Evaluates candidate detections against simulation ground truth:
  - Cross-matches linked tracklets to injected solar system objects
  - Computes recall, precision, false-positive counts, and astrometric/rate accuracy
  - Performs S/N threshold sweep (recall vs false-positive trade-off)
  - Writes data/output/detection_eval.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from detection.movers.linking import angular_separation_arcsec

DEFAULT_CANDIDATES_PATH = REPO_ROOT / "data" / "output" / "candidates.json"
DEFAULT_GROUND_TRUTH_PATH = REPO_ROOT / "data" / "output" / "ground_truth.json"
DEFAULT_EVAL_OUTPUT_PATH = REPO_ROOT / "data" / "output" / "detection_eval.json"


def evaluate(
    candidates_path: Path | str = DEFAULT_CANDIDATES_PATH,
    ground_truth_path: Path | str = DEFAULT_GROUND_TRUTH_PATH,
    match_threshold_arcsec: float = 4.0,
) -> Dict[str, Any]:
    """Compare candidate catalog against injected simulation ground truth.

    Args:
        candidates_path: Path to candidates.json.
        ground_truth_path: Path to ground_truth.json.
        match_threshold_arcsec: Maximum average position error to match a mover.

    Returns:
        Evaluation dictionary of computed metrics.
    """
    c_path = Path(candidates_path)
    gt_path = Path(ground_truth_path)

    if not c_path.exists():
        raise FileNotFoundError(f"Candidates file not found: {c_path}")
    if not gt_path.exists():
        raise FileNotFoundError(f"Ground truth file not found: {gt_path}")

    with open(c_path, "r", encoding="utf-8") as f:
        candidates_data = json.load(f)
    with open(gt_path, "r", encoding="utf-8") as f:
        gt_data = json.load(f)

    cand_movers = candidates_data.get("movers", [])
    gt_movers = gt_data.get("movers", [])

    # Identify recoverable injected movers (at least 3 in-bounds detections)
    recoverable_gt = []
    for m in gt_movers:
        in_bounds_count = sum(1 for p in m["positions_per_epoch"] if p.get("in_bounds", True))
        if in_bounds_count >= 3:
            recoverable_gt.append(m)

    # Match candidate tracklets to ground truth movers
    # Matrix of average separation across common epochs
    matches: List[Dict[str, Any]] = []
    matched_gt_ids = set()
    matched_cand_ids = set()

    pair_distances = []
    for c_idx, cand in enumerate(cand_movers):
        cand_dets = {d["epoch_id"]: (d["ra"], d["dec"]) for d in cand["detections"]}
        for g_idx, gt_m in enumerate(recoverable_gt):
            gt_pos = {p["epoch_id"]: (p["ra"], p["dec"]) for p in gt_m["positions_per_epoch"]}

            common_epochs = set(cand_dets.keys()) & set(gt_pos.keys())
            if len(common_epochs) >= 2:
                errors = []
                for ep in common_epochs:
                    cra, cdec = cand_dets[ep]
                    gra, gdec = gt_pos[ep]
                    _, _, dist = angular_separation_arcsec(cra, cdec, gra, gdec)
                    errors.append(dist)
                mean_dist = float(np.mean(errors))
                pair_distances.append((mean_dist, c_idx, g_idx, errors))

    # Greedy best-match assignment
    pair_distances.sort(key=lambda x: x[0])
    for mean_dist, c_idx, g_idx, point_errors in pair_distances:
        cand = cand_movers[c_idx]
        gt_m = recoverable_gt[g_idx]

        if cand["object_id"] in matched_cand_ids or gt_m["object_id"] in matched_gt_ids:
            continue

        if mean_dist <= match_threshold_arcsec:
            matched_cand_ids.add(cand["object_id"])
            matched_gt_ids.add(gt_m["object_id"])

            # Compute motion rate difference
            c_motion = cand.get("motion", {})
            g_motion = gt_m.get("motion", {})
            dra_rate_err = abs(c_motion.get("ra_rate_arcsec_per_day", 0.0) - g_motion.get("ra_rate_arcsec_per_day", 0.0))
            ddec_rate_err = abs(c_motion.get("dec_rate_arcsec_per_day", 0.0) - g_motion.get("dec_rate_arcsec_per_day", 0.0))

            matches.append(
                {
                    "candidate_id": cand["object_id"],
                    "gt_object_id": gt_m["object_id"],
                    "mean_position_error_arcsec": round(mean_dist, 4),
                    "point_errors": [round(float(e), 4) for e in point_errors],
                    "ra_rate_error_arcsec_per_day": round(dra_rate_err, 4),
                    "dec_rate_error_arcsec_per_day": round(ddec_rate_err, 4),
                }
            )

    true_positives = len(matches)
    total_recoverable = len(recoverable_gt)
    total_candidates = len(cand_movers)
    false_positives = total_candidates - true_positives

    recall = float(true_positives / total_recoverable) if total_recoverable > 0 else 0.0
    fp_rate = float(false_positives / total_candidates) if total_candidates > 0 else 0.0

    all_point_errors = [e for m in matches for e in m["point_errors"]]
    all_ra_rate_errors = [m["ra_rate_error_arcsec_per_day"] for m in matches]
    all_dec_rate_errors = [m["dec_rate_error_arcsec_per_day"] for m in matches]

    mean_pos_err = float(np.mean(all_point_errors)) if all_point_errors else 0.0
    med_pos_err = float(np.median(all_point_errors)) if all_point_errors else 0.0
    max_pos_err = float(np.max(all_point_errors)) if all_point_errors else 0.0

    mean_ra_rate_err = float(np.mean(all_ra_rate_errors)) if all_ra_rate_errors else 0.0
    mean_dec_rate_err = float(np.mean(all_dec_rate_errors)) if all_dec_rate_errors else 0.0

    # S/N threshold sweep
    snr_levels = [3.0, 4.0, 6.0, 8.0, 10.0]
    snr_sweep_results = []
    for s_cut in snr_levels:
        # Filter candidates by mean S/N of detections
        filtered_cands = [
            c
            for c in cand_movers
            if np.mean([d.get("flux", 0.0) for d in c.get("detections", [])]) >= s_cut * 5.0
        ]
        sweep_tp = sum(1 for m in matches if m["candidate_id"] in [c["object_id"] for c in filtered_cands])
        sweep_fp = len(filtered_cands) - sweep_tp
        sweep_recall = float(sweep_tp / total_recoverable) if total_recoverable > 0 else 0.0
        snr_sweep_results.append(
            {
                "snr_threshold": s_cut,
                "candidates_count": len(filtered_cands),
                "true_positives": sweep_tp,
                "false_positives": sweep_fp,
                "recall": round(sweep_recall, 3),
            }
        )

    eval_results: Dict[str, Any] = {
        "is_synthetic": True,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "total_injected_movers": len(gt_movers),
        "recoverable_movers_count": total_recoverable,
        "detected_candidates_count": total_candidates,
        "true_positives": true_positives,
        "false_positives": false_positives,
        "recall": round(recall, 4),
        "false_positive_rate": round(fp_rate, 4),
        "astrometric_error_arcsec": {
            "mean": round(mean_pos_err, 4),
            "median": round(med_pos_err, 4),
            "max": round(max_pos_err, 4),
        },
        "rate_error_arcsec_per_day": {
            "mean_ra_rate_error": round(mean_ra_rate_err, 4),
            "mean_dec_rate_error": round(mean_dec_rate_err, 4),
        },
        "matched_movers": matches,
        "snr_sweep": snr_sweep_results,
    }

    return eval_results


def main() -> None:
    """CLI runner for evaluation script."""
    parser = argparse.ArgumentParser(description="SPHEREx Sky Diary — Detection Evaluator")
    parser.add_argument("--candidates", type=str, default=str(DEFAULT_CANDIDATES_PATH))
    parser.add_argument("--ground-truth", type=str, default=str(DEFAULT_GROUND_TRUTH_PATH))
    parser.add_argument("--output", type=str, default=str(DEFAULT_EVAL_OUTPUT_PATH))
    args = parser.parse_args()

    results = evaluate(candidates_path=args.candidates, ground_truth_path=args.ground_truth)

    out_file = Path(args.output)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("================================================================")
    print(" SPHEREx Mover Detection Evaluation (SYNTHETIC DATA ONLY)")
    print("================================================================")
    print(f" Total Injected Movers:        {results['total_injected_movers']}")
    print(f" Recoverable Movers (>=3 ep):  {results['recoverable_movers_count']}")
    print(f" Detected Candidates:          {results['detected_candidates_count']}")
    print(f" True Positives:               {results['true_positives']}")
    print(f" False Positives:              {results['false_positives']}")
    print(f" Detection Recall:             {results['recall'] * 100:.1f}%")
    print(f" Mean Position Error:          {results['astrometric_error_arcsec']['mean']:.4f} arcsec")
    print(f" Median Position Error:        {results['astrometric_error_arcsec']['median']:.4f} arcsec")
    print(f" Mean RA Rate Error:           {results['rate_error_arcsec_per_day']['mean_ra_rate_error']:.4f} arcsec/day")
    print(f" Mean Dec Rate Error:          {results['rate_error_arcsec_per_day']['mean_dec_rate_error']:.4f} arcsec/day")
    print("\n--- S/N Threshold Sweep Table ---")
    print(f"{'S/N Cut':<10} | {'Candidates':<12} | {'Recall':<8} | {'False Positives':<15}")
    print("-" * 55)
    for row in results["snr_sweep"]:
        print(f"{row['snr_threshold']:<10.1f} | {row['candidates_count']:<12} | {row['recall']*100:<7.1f}% | {row['false_positives']:<15}")
    print(f"\nSaved evaluation metrics to: {out_file}")


if __name__ == "__main__":
    main()

