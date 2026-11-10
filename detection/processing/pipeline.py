"""SPHEREx Sky Diary — Image Processing Pipeline (Module 2).

Orchestrates multi-epoch processing:
  1. Load raw epochs via EpochSource
  2. Data quality & outlier masking (cosmic rays, bad pixels, edges)
  3. 2D spatial background estimation and subtraction
  4. Reprojection onto an unprivileged celestial reference grid
  5. Isolated reference star extraction and relative photometric normalization
  6. Persistence of aligned stack and manifest to data/output/processed/
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import yaml
from astropy.io import fits
from astropy.wcs import WCS

# Ensure repository root is in path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data.adapter.base import EpochImage, EpochSource, Region
from data.adapter.factory import get_source
from detection.processing.align import build_reference_grid, reproject_epoch
from detection.processing.background import subtract_background
from detection.processing.masking import apply_mask, build_mask
from detection.processing.normalize import normalize_epochs, select_reference_stars

DEFAULT_SETTINGS_PATH = REPO_ROOT / "config" / "settings.yaml"
DEFAULT_PROCESSING_PATH = REPO_ROOT / "config" / "processing.yaml"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "output" / "processed"


def load_yaml(path: Path | str) -> Dict[str, Any]:
    """Load YAML file if exists, else return empty dict."""
    p = Path(path)
    if not p.exists():
        return {}
    with open(p, "r", encoding="utf-8") as f:
        res = yaml.safe_load(f)
        return res if isinstance(res, dict) else {}


def merge_configs(
    settings_cfg: Dict[str, Any],
    processing_cfg: Dict[str, Any],
) -> Dict[str, Any]:
    """Merge high-level settings and processing thresholds."""
    merged = copy.deepcopy(settings_cfg)
    for k, v in processing_cfg.items():
        if k in merged and isinstance(merged[k], dict) and isinstance(v, dict):
            merged[k].update(v)
        else:
            merged[k] = v
    return merged


def run(
    config: Optional[Union[Dict[str, Any], Path, str]] = None,
    output_dir: Optional[Union[Path, str]] = None,
) -> Path:
    """Execute the end-to-end image processing pipeline.

    Args:
        config: Path to settings YAML, dict of settings, or None (defaults to config/settings.yaml).
        output_dir: Optional directory override for processed output products.

    Returns:
        Path to the output processed directory containing npz files and manifest.json.
    """
    # 1. Resolve configuration
    if isinstance(config, dict):
        base_cfg = config
    elif config is not None:
        base_cfg = load_yaml(config)
    else:
        base_cfg = load_yaml(DEFAULT_SETTINGS_PATH)

    proc_file_cfg = load_yaml(DEFAULT_PROCESSING_PATH)
    cfg = merge_configs(base_cfg, proc_file_cfg)

    # 2. Output directory resolution
    if output_dir is not None:
        out_path = Path(output_dir)
    else:
        proc_sub = cfg.get("output", {}).get("processed_dir", "data/output/processed")
        out_path = REPO_ROOT / proc_sub
    out_path.mkdir(parents=True, exist_ok=True)

    # 3. Instantiate data adapter source and target region
    source: EpochSource = get_source(cfg)
    region_info = cfg.get("region", {})
    region = Region(
        name=str(region_info.get("name", "ecliptic_plane_test")),
        ra_center=float(region_info.get("ra_center", 60.0)),
        dec_center=float(region_info.get("dec_center", 20.0)),
        radius_deg=float(region_info.get("radius_deg", 0.2)),
    )
    fov_deg = float(cfg.get("fov_deg", 0.2))

    # 4. Enumerate epochs
    epochs_info = source.list_epochs(region)
    if not epochs_info:
        raise ValueError(f"No observation epochs available for region '{region.name}'.")

    # 5. Build unprivileged reference celestial grid
    ref_wcs, ref_shape = build_reference_grid(region, fov_deg=fov_deg)

    # 6. Process each epoch: Load -> Mask -> Background -> Reproject
    aligned_stack: List[EpochImage] = []
    is_synthetic_flags: List[bool] = []

    for ep_info in epochs_info:
        raw_epoch = source.load_epoch(ep_info.epoch_id, region, fov_deg=fov_deg)
        is_synthetic_flags.append(bool(raw_epoch.metadata.get("is_synthetic", False)))

        # A. Build quality bitmask (adapter bad pixels, cosmic ray outliers, growth)
        quality_mask = build_mask(raw_epoch, config=cfg)
        masked_epoch = apply_mask(raw_epoch, quality_mask)

        # B. 2D spatial background estimation and subtraction
        bkg_sub_epoch = subtract_background(masked_epoch, config=cfg)

        # C. Astrometric reprojection onto reference grid
        aligned_epoch = reproject_epoch(bkg_sub_epoch, ref_wcs, ref_shape, config=cfg)
        aligned_stack.append(aligned_epoch)

    # 7. Select reference stars and compute relative photometric normalization
    reference_stars = select_reference_stars(aligned_stack, config=cfg)
    normalized_stack, scale_factors = normalize_epochs(aligned_stack, reference_stars, config=cfg)

    # 8. Save aligned products (.npz per epoch)
    manifest_epochs: List[Dict[str, Any]] = []

    for ep in normalized_stack:
        fname = f"{ep.epoch_id}.npz"
        file_path = out_path / fname

        np.savez_compressed(
            file_path,
            pixels=ep.pixels.astype(np.float32),
            variance=ep.variance.astype(np.float32),
            mask=ep.mask.astype(np.int32),
            wavelength_map=ep.wavelength_map.astype(np.float32),
            wcs_header=ref_wcs.to_header_string(),
            epoch_id=ep.epoch_id,
            date=ep.date.isoformat(),
            normalization_factor=scale_factors.get(ep.epoch_id, 1.0),
        )

        try:
            rel_file = str(file_path.relative_to(REPO_ROOT)).replace("\\", "/")
        except ValueError:
            rel_file = str(file_path).replace("\\", "/")

        manifest_epochs.append(
            {
                "epoch_id": ep.epoch_id,
                "date": ep.date.isoformat(),
                "file": rel_file,
                "normalization_factor": scale_factors.get(ep.epoch_id, 1.0),
            }
        )

    # 9. Write manifest.json
    manifest_data: Dict[str, Any] = {
        "schema_version": "1.0",
        "pipeline_version": "v1.0-processing",
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "is_synthetic": any(is_synthetic_flags),
        "region": {
            "name": region.name,
            "ra_center": region.ra_center,
            "dec_center": region.dec_center,
            "radius_deg": region.radius_deg,
        },
        "fov_deg": fov_deg,
        "grid_shape": list(ref_shape),
        "ref_wcs_header": ref_wcs.to_header_string(),
        "epochs": manifest_epochs,
        "normalization_factors": scale_factors,
        "reference_stars_count": len(reference_stars),
        "reference_stars": [
            {
                "x": round(float(s["x"]), 2),
                "y": round(float(s["y"]), 2),
                "flux_mean": round(float(s["flux_mean"]), 2),
                "scatter": round(float(s["scatter"]), 4),
            }
            for s in reference_stars
        ],
        "config_used": cfg,
    }

    manifest_file = out_path / "manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    return out_path


def load_processed_stack(
    processed_dir: Union[Path, str] = DEFAULT_OUTPUT_DIR,
) -> Tuple[List[EpochImage], Dict[str, Any]]:
    """Load aligned and normalized EpochImage stack from disk (for Module 3).

    Args:
        processed_dir: Directory containing manifest.json and per-epoch .npz files.

    Returns:
        Tuple of (list_of_EpochImages, manifest_dictionary).
    """
    base_dir = Path(processed_dir)
    manifest_path = base_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Processing manifest not found at: {manifest_path}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # Reconstruct WCS from header string
    header = fits.Header.fromstring(manifest["ref_wcs_header"])
    ref_wcs = WCS(header)

    stack: List[EpochImage] = []
    for ep_entry in manifest["epochs"]:
        epoch_id = ep_entry["epoch_id"]
        npz_file = base_dir / f"{epoch_id}.npz"
        if not npz_file.exists():
            raise FileNotFoundError(f"Processed epoch file missing: {npz_file}")

        with np.load(npz_file) as npz:
            pixels = npz["pixels"].astype(np.float64)
            variance = npz["variance"].astype(np.float64)
            mask = npz["mask"].astype(np.int32)
            wavelength_map = npz["wavelength_map"].astype(np.float64)
            date_str = str(npz["date"])
            date = datetime.fromisoformat(date_str)
            norm_factor = float(npz["normalization_factor"])

        stack.append(
            EpochImage(
                pixels=pixels,
                variance=variance,
                mask=mask,
                wcs=ref_wcs,
                wavelength_map=wavelength_map,
                epoch_id=epoch_id,
                date=date,
                metadata={
                    "is_synthetic": manifest.get("is_synthetic", False),
                    "normalization_factor": norm_factor,
                    "aligned": True,
                },
            )
        )

    return stack, manifest


def main() -> None:
    """CLI entry point for image processing pipeline."""
    parser = argparse.ArgumentParser(
        description="SPHEREx Sky Diary — Image Processing Pipeline (Module 2)"
    )
    parser.add_argument(
        "--config",
        type=str,
        default=str(DEFAULT_SETTINGS_PATH),
        help="Path to settings.yaml configuration file.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Custom destination directory for processed outputs.",
    )
    args = parser.parse_args()

    print(f"[Module 2 Processing] Executing pipeline with config: {args.config}")
    out_dir = run(config=args.config, output_dir=args.output_dir)
    print(f"[Module 2 Processing] Successfully processed stack into: {out_dir}")


if __name__ == "__main__":
    main()
