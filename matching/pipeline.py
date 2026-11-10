"""SPHEREx Sky Diary — Catalog Matching Pipeline.

Executes end-to-end solar system cross-matching, candidate classification,
schema validation, and performance evaluation.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from docs.validate import validate_dict, validate_file
from matching.match import match_candidates
from matching.query import query_known_objects
from matching.validate_matches import evaluate_catalog_matching, save_validation_reports

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("matching.pipeline")


def load_yaml(path: Path | str) -> Dict[str, Any]:
    """Load YAML config file."""
    p = Path(path)
    if not p.exists():
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def build_pipeline_config(
    settings_path: Path | str = REPO_ROOT / "config" / "settings.yaml",
    matching_config_path: Path | str = REPO_ROOT / "config" / "matching.yaml",
    overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Merge system settings and matching configuration."""
    cfg = load_yaml(matching_config_path)
    settings = load_yaml(settings_path)

    # Base settings
    cfg["settings"] = settings
    if overrides:
        for k, v in overrides.items():
            if isinstance(v, dict) and k in cfg:
                cfg[k].update(v)
            else:
                cfg[k] = v
    return cfg


def run(
    config: Optional[Dict[str, Any]] = None,
    offline: bool = False,
    candidates_file: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Run catalog matching pipeline.

    Args:
        config: Combined configuration dictionary.
        offline: If True, bypass live network queries and use offline cache.
        candidates_file: Optional explicit path to candidates.json.

    Returns:
        Evaluation report dictionary.
    """
    cfg = config or build_pipeline_config()
    out_cfg = cfg.get("output", {})

    cand_path = (
        Path(candidates_file)
        if candidates_file
        else REPO_ROOT / out_cfg.get("candidates_file", "data/output/candidates.json")
    )

    if not cand_path.exists():
        raise FileNotFoundError(
            f"Candidate catalog not found at {cand_path}. Run detection pipeline first."
        )

    with open(cand_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    region = catalog.get("region", {})
    ra_center = float(region.get("ra_center", 60.0))
    dec_center = float(region.get("dec_center", 20.0))
    radius_deg = float(region.get("radius_deg", 0.2))
    epochs = catalog.get("epochs", [])
    movers = catalog.get("movers", [])

    logger.info("Loaded %d candidates from %s", len(movers), cand_path)

    # Automatically set offline=True if settings.data_source is mock
    settings = cfg.get("settings", {})
    if settings.get("data_source") == "mock":
        offline = True

    # 1. Query known bodies
    known_objects, source_label = query_known_objects(
        ra=ra_center,
        dec=dec_center,
        radius_deg=radius_deg,
        epochs=epochs,
        offline=offline,
        config=cfg,
    )
    logger.info("Obtained %d known objects from source: '%s'", len(known_objects), source_label)

    # 2. Match candidate tracklets
    updated_movers = match_candidates(
        candidates=movers,
        known_objects=known_objects,
        config=cfg,
    )

    # 3. Update catalog in-place
    catalog["movers"] = updated_movers
    catalog["metadata"] = {
        "matching_source": source_label,
        "matched_at": datetime.now(timezone.utc).isoformat(),
        "known_objects_polled": len(known_objects),
    }

    # Validate against JSON schema & contract domain rules
    validate_dict(catalog)

    with open(cand_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2)
    logger.info("Wrote updated candidates catalog to %s", cand_path)

    # Validate written file
    validate_file(cand_path)

    # 4. Generate validation report
    report = evaluate_catalog_matching(
        candidates_catalog=catalog,
        known_objects=known_objects,
        config=cfg,
    )

    json_report_path = REPO_ROOT / out_cfg.get(
        "validation_report_json", "data/output/validation_report.json"
    )
    md_report_path = REPO_ROOT / out_cfg.get(
        "validation_report_md", "data/output/validation_report.md"
    )

    save_validation_reports(report, json_report_path, md_report_path)

    summary = report["summary"]
    logger.info("==================================================")
    logger.info("MODULE 4 MATCHING COMPLETE")
    logger.info("  Candidates Processed: %d", summary["total_candidates"])
    logger.info("  Labeled Known:        %d", summary["labeled_known_count"])
    logger.info("  Labeled Unknown:      %d", summary["labeled_unknown_count"])
    logger.info("  Known Objects Poll:   %d", summary["total_known_in_field"])
    logger.info("  Recovery Recall:      %.1f%%", summary["known_recovery_recall"] * 100.0)
    logger.info("  Mean Residual:        %.3f arcsec", summary["mean_match_distance_arcsec"])
    logger.info("  Matching Source:      %s", source_label)
    logger.info("==================================================")

    return report
