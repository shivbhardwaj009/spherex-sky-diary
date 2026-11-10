"""SPHEREx Sky Diary — Mover Detection Pipeline (Module 3).

Executes full transient detection workflow:
  1. Loads aligned stack from Module 2 (load_processed_stack)
  2. Synthesizes stationary sky model and empirical noise maps
  3. Computes significance maps via difference imaging
  4. Extracts point source candidates per epoch
  5. Links candidate detections into constant-velocity tracklets
  6. Filters out single-epoch transients, stationary residuals, and bad fits
  7. Computes confidence scores
  8. Saves cutout postage stamps to data/output/cutouts/
  9. Writes candidates.json conforming strictly to contract v1.0
  10. Validates candidates.json via docs.validate.validate_file
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np
import yaml
from PIL import Image

# Ensure repository root is in path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from detection.movers.difference import difference_epoch
from detection.movers.extract import extract_sources
from detection.movers.filters import (
    flag_filter_response,
    reject_bad_fit,
    reject_single_epoch,
    reject_stationary,
)
from detection.movers.linking import Tracklet, link_detections
from detection.movers.score import compute_confidence
from detection.movers.static_model import build_static_model
from detection.processing.pipeline import load_processed_stack
from docs.validate import validate_file

DEFAULT_SETTINGS_PATH = REPO_ROOT / "config" / "settings.yaml"
DEFAULT_DETECTION_PATH = REPO_ROOT / "config" / "detection.yaml"


def load_yaml(path: Path | str) -> Dict[str, Any]:
    """Load YAML file if exists, else empty dict."""
    p = Path(path)
    if not p.exists():
        return {}
    with open(p, "r", encoding="utf-8") as f:
        res = yaml.safe_load(f)
        return res if isinstance(res, dict) else {}


def save_cutout_image(
    image: np.ndarray,
    cx: float,
    cy: float,
    save_path: Path,
    size: int = 48,
) -> None:
    """Save 8-bit PNG postage-stamp cutout centered at (cx, cy).

    Extracted from the difference flux plane with contrast stretch to visualize
    the transient source against local background noise.
    """
    height, width = image.shape
    rad = size // 2

    ix = int(round(cx))
    iy = int(round(cy))

    x0 = max(0, ix - rad)
    x1 = min(width, ix + rad)
    y0 = max(0, iy - rad)
    y1 = min(height, iy + rad)

    subpatch = image[y0:y1, x0:x1]
    # Pad to fixed size if on edge
    padded = np.zeros((size, size), dtype=np.float64)
    px0 = max(0, rad - (ix - x0))
    py0 = max(0, rad - (iy - y0))
    padded[py0 : py0 + subpatch.shape[0], px0 : px0 + subpatch.shape[1]] = subpatch

    # Min-max / percentile normalization to 8-bit image
    p_low = np.percentile(padded, 5.0)
    p_high = max(p_low + 1.0, np.percentile(padded, 99.5))
    norm = np.clip((padded - p_low) / (p_high - p_low) * 255.0, 0, 255).astype(np.uint8)

    save_path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.fromarray(norm, mode="L")
    img.save(save_path, format="PNG")


def run(
    config: Optional[Union[Dict[str, Any], Path, str]] = None,
    output_candidates_path: Optional[Union[Path, str]] = None,
) -> Path:
    """Run the complete mover detection pipeline.

    Args:
        config: Path to settings YAML, dict, or None.
        output_candidates_path: Optional override path for candidates.json.

    Returns:
        Path to validated candidates.json file.
    """
    if isinstance(config, dict):
        base_cfg = config
    elif config is not None:
        base_cfg = load_yaml(config)
    else:
        base_cfg = load_yaml(DEFAULT_SETTINGS_PATH)

    det_cfg_file = load_yaml(DEFAULT_DETECTION_PATH)
    # Start with default file settings, then apply user/caller overrides
    cfg = copy.deepcopy(det_cfg_file)
    for k, v in base_cfg.items():
        if k in cfg and isinstance(cfg[k], dict) and isinstance(v, dict):
            cfg[k].update(v)
        else:
            cfg[k] = v

    raw_proc_dir = cfg.get("output", {}).get("processed_dir", "data/output/processed")
    processed_dir = Path(raw_proc_dir) if Path(raw_proc_dir).is_absolute() else REPO_ROOT / raw_proc_dir

    raw_cutouts_dir = cfg.get("output", {}).get("cutouts_dir", "data/output/cutouts")
    cutouts_dir = Path(raw_cutouts_dir) if Path(raw_cutouts_dir).is_absolute() else REPO_ROOT / raw_cutouts_dir
    cutouts_dir.mkdir(parents=True, exist_ok=True)

    if output_candidates_path is not None:
        candidates_dest = Path(output_candidates_path)
    else:
        raw_cand = cfg.get("output", {}).get("candidates_file", "data/output/candidates.json")
        candidates_dest = Path(raw_cand) if Path(raw_cand).is_absolute() else REPO_ROOT / raw_cand
    candidates_dest.parent.mkdir(parents=True, exist_ok=True)

    # 1. Load aligned stack from Module 2
    stack, manifest = load_processed_stack(processed_dir)
    is_synthetic = bool(manifest.get("is_synthetic", True))
    region_info = manifest.get("region", {})
    fov_deg = float(manifest.get("fov_deg", 0.2))

    # Reference stars from manifest (to mask out subtraction residuals)
    bright_stars = manifest.get("reference_stars", [])

    # 2. Build static-sky reference model and noise scatter map
    static_model, scatter_map, model_meta = build_static_model(stack, config=cfg)

    # 3. Differencing and source extraction per epoch
    detections_by_epoch: Dict[str, List[Dict[str, Any]]] = {}
    diff_images_by_epoch: Dict[str, np.ndarray] = {}

    for ep in stack:
        diff_pixels, sig_map, updated_mask = difference_epoch(
            epoch=ep,
            model=static_model,
            scatter=scatter_map,
            config=cfg,
        )
        diff_images_by_epoch[ep.epoch_id] = diff_pixels

        epoch_dets = extract_sources(
            significance_map=sig_map,
            epoch=ep,
            diff_pixels=diff_pixels,
            bright_stars=bright_stars,
            config=cfg,
        )
        detections_by_epoch[ep.epoch_id] = epoch_dets

    # 4. Link detections into constant-velocity tracklets
    linked_tracks = link_detections(detections_by_epoch, config=cfg)

    # 5. Apply artifact rejection filters and score tracklets
    min_motion = float(cfg.get("filters", {}).get("min_motion_arcsec", 3.0))
    max_res = float(cfg.get("filters", {}).get("max_residual_arcsec", 3.5))
    corr_thresh = float(cfg.get("filters", {}).get("filter_response_corr_threshold", 0.80))

    passed_movers: List[Dict[str, Any]] = []
    mover_idx = 0

    for track in linked_tracks:
        # A. Filter: single epoch
        if reject_single_epoch(track):
            continue

        # B. Filter: stationary artifact
        if reject_stationary(track, min_motion_arcsec=min_motion):
            continue

        # C. Filter: bad trajectory fit
        if reject_bad_fit(track, max_residual_arcsec=max_res):
            continue

        # D. Diagnostic: filter response chromatic correlation
        is_lvf_flagged, lvf_score = flag_filter_response(
            track, stack=stack, correlation_threshold=corr_thresh
        )

        # Compute composite confidence score in [0.0, 1.0]
        confidence = compute_confidence(track, filter_response_score=lvf_score, config=cfg)

        mover_idx += 1
        obj_id = f"mov_{mover_idx:03d}"

        # Generate cutout PNGs for each detection in the track
        processed_detections: List[Dict[str, Any]] = []
        for det in track.detections:
            ep_id = det["epoch_id"]
            cutout_name = f"{obj_id}_{ep_id}.png"
            cutout_path = cutouts_dir / cutout_name

            # Save cutout centered on mover from difference image
            diff_img = diff_images_by_epoch.get(ep_id, stack[0].pixels)
            save_cutout_image(
                image=diff_img,
                cx=det["x"],
                cy=det["y"],
                save_path=cutout_path,
                size=int(cfg.get("output", {}).get("cutout_size_px", 48)),
            )

            processed_detections.append(
                {
                    "epoch_id": ep_id,
                    "date": det["date"],
                    "ra": det["ra"],
                    "dec": det["dec"],
                    "flux": det["flux"],
                    "cutout_url": f"cutouts/{cutout_name}",
                }
            )

        passed_movers.append(
            {
                "object_id": obj_id,
                "ra": round(track.ref_ra, 6),
                "dec": round(track.ref_dec, 6),
                "type": "unknown",  # Initial detection; matching module classifies
                "match_name": None,
                "confidence": confidence,
                "is_synthetic": is_synthetic,
                "motion": {
                    "ra_rate_arcsec_per_day": round(track.ra_rate_arcsec_per_day, 2),
                    "dec_rate_arcsec_per_day": round(track.dec_rate_arcsec_per_day, 2),
                },
                "detections": processed_detections,
                "spectrum": None,  # Extracted in Module 4/5
            }
        )

    # 6. Format final candidate catalog conforming to Contract v1.0
    epochs_catalog = [
        {
            "epoch_id": ep_entry["epoch_id"],
            "date": ep_entry["date"],
            "band_count": 102,
        }
        for ep_entry in manifest.get("epochs", [])
    ]

    candidates_catalog: Dict[str, Any] = {
        "schema_version": "1.0",
        "data_version": "v1.0-detection",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fov_deg": fov_deg,
        "region": {
            "name": str(region_info.get("name", "ecliptic_plane_test")),
            "ra_center": float(region_info.get("ra_center", 60.0)),
            "dec_center": float(region_info.get("dec_center", 20.0)),
            "radius_deg": float(region_info.get("radius_deg", 0.2)),
        },
        "epochs": epochs_catalog,
        "movers": passed_movers,
    }

    # Write candidates.json
    with open(candidates_dest, "w", encoding="utf-8") as f:
        json.dump(candidates_catalog, f, indent=2)

    # 7. Validate output against Contract Schema v1.0
    validate_file(candidates_dest)

    return candidates_dest


def main() -> None:
    """CLI entry point for mover detection pipeline."""
    parser = argparse.ArgumentParser(
        description="SPHEREx Sky Diary — Mover Detection Pipeline (Module 3)"
    )
    parser.add_argument(
        "--config",
        type=str,
        default=str(DEFAULT_SETTINGS_PATH),
        help="Path to settings.yaml configuration file.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Destination path for candidates.json output file.",
    )
    args = parser.parse_args()

    print(f"[Module 3 Detection] Running pipeline with config: {args.config}")
    out_file = run(config=args.config, output_candidates_path=args.output)
    print(f"[Module 3 Detection] Successfully generated candidate catalog: {out_file}")


if __name__ == "__main__":
    main()
