"""SPHEREx Sky Diary — Spectral Extraction Pipeline (Module 5).

Runs full spectral extraction across detected candidate movers in candidates.json,
writes static demo spectra for Space Apps challenge targets, validates outputs,
and logs extraction performance metrics.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from astropy.coordinates import SkyCoord

from data.adapter.base import Region
from data.adapter.factory import get_source
from docs.validate import validate_dict, validate_file
from spectra.api import get_spectrum

logger = logging.getLogger("spectra.pipeline")

# Offline fallback celestial coordinates (J2000) for Challenge Demo Targets
# TODO(VERIFY): Proper motion epoch propagation (J2000 -> 2026.0) for high-proper-motion
# targets (Barnard's Star ~10.4"/yr, WISE 0855 ~8.1"/yr).
OFFLINE_DEMO_COORDINATES: Dict[str, Tuple[float, float]] = {
    "Barnard's Star": (269.45208, 4.69339),
    "Epsilon Indi B": (330.84042, -56.78611),
    "WISE 0855": (133.79513, -7.24515),  # RA 08h55m10.831s, Dec -07d14m42.53s
    "RW Aurigae": (77.10625, 30.40139),
    "R Draconis": (248.33792, 66.86861),
}


def slugify(text: str) -> str:
    """Convert a name into a clean filesystem slug."""
    s = text.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "_", s)
    return s


def resolve_target_coordinates(name: str) -> Tuple[float, float]:
    """Resolve target coordinates via offline table or online SkyCoord.from_name."""
    # 1. Check verified offline dictionary
    if name in OFFLINE_DEMO_COORDINATES:
        return OFFLINE_DEMO_COORDINATES[name]

    # 2. Online resolution with fallback
    try:
        coord = SkyCoord.from_name(name)
        return float(coord.ra.deg), float(coord.dec.deg)
    except Exception as exc:
        logger.warning(
            "Could not resolve coordinates for '%s' online (%s). Defaulting to (0.0, 0.0)",
            name,
            exc,
        )
        return 0.0, 0.0


def load_yaml(path: Path | str) -> Dict[str, Any]:
    """Load YAML config file."""
    p = Path(path)
    if not p.exists():
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def build_pipeline_config(
    settings_path: Path | str = REPO_ROOT / "config" / "settings.yaml",
    spectra_config_path: Path | str = REPO_ROOT / "config" / "spectra.yaml",
) -> Dict[str, Any]:
    """Merge system settings and spectra configuration."""
    cfg = load_yaml(spectra_config_path)
    settings = load_yaml(settings_path)
    cfg["settings"] = settings
    return cfg


def run(
    config: Optional[Dict[str, Any]] = None,
    candidates_file: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Execute end-to-end spectrum extraction for candidates and demo targets.

    Args:
        config: Spectra configuration parameters dictionary.
        candidates_file: Optional explicit path to candidates.json.

    Returns:
        Summary metrics dictionary.
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
            f"Candidate catalog not found at {cand_path}. Run detection/matching first."
        )

    with open(cand_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    region_dict = catalog.get("region", {})
    region = Region(
        name=region_dict.get("name", "ecliptic_plane_test"),
        ra_center=float(region_dict.get("ra_center", 60.0)),
        dec_center=float(region_dict.get("dec_center", 20.0)),
        radius_deg=float(region_dict.get("radius_deg", 0.2)),
    )
    fov_deg = float(catalog.get("fov_deg", 0.2))

    # Initialize data source adapter
    source = get_source(cfg.get("settings"))

    movers = catalog.get("movers", [])
    logger.info("Extracting spectra for %d movers in %s", len(movers), cand_path)

    extracted_count = 0
    failed_count = 0
    channel_counts: List[int] = []

    for mover in movers:
        obj_id = mover.get("object_id")
        m_ra = float(mover.get("ra", region.ra_center))
        m_dec = float(mover.get("dec", region.dec_center))
        detections = mover.get("detections", [])
        motion = mover.get("motion")

        spectrum = get_spectrum(
            ra=m_ra,
            dec=m_dec,
            source=source,
            region=region,
            fov_deg=fov_deg,
            track=detections,
            motion=motion,
            config=cfg,
        )

        if spectrum is not None:
            mover["spectrum"] = spectrum
            extracted_count += 1
            n_chan = len(spectrum["wavelength_um"])
            channel_counts.append(n_chan)
            logger.info("Extracted %d-channel spectrum for mover %s", n_chan, obj_id)
        else:
            mover["spectrum"] = None
            failed_count += 1
            logger.warning("Spectral extraction returned None for mover %s", obj_id)

    # Validate catalog against JSON schema and domain rules
    validate_dict(catalog)

    with open(cand_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2)
    logger.info("Saved updated candidates catalog with spectra to %s", cand_path)

    validate_file(cand_path)

    # 2. Extract static spectra for NASA Space Apps Challenge Demo Targets
    demo_targets = cfg.get("demo_targets", [])
    spectra_dir = REPO_ROOT / out_cfg.get("spectra_dir", "data/output/spectra")
    spectra_dir.mkdir(parents=True, exist_ok=True)

    demo_results: List[Dict[str, Any]] = []

    for target in demo_targets:
        t_name = target["name"]
        t_ra = float(target.get("ra", 0.0))
        t_dec = float(target.get("dec", 0.0))

        if t_ra == 0.0 and t_dec == 0.0:
            t_ra, t_dec = resolve_target_coordinates(t_name)

        t_region = Region(
            name=f"demo_{slugify(t_name)}",
            ra_center=t_ra,
            dec_center=t_dec,
            radius_deg=0.1,
        )

        t_spectrum = get_spectrum(
            ra=t_ra,
            dec=t_dec,
            source=source,
            region=t_region,
            fov_deg=0.2,
            config=cfg,
        )

        t_file = spectra_dir / f"{slugify(t_name)}.json"
        target_payload = {
            "name": t_name,
            "ra": t_ra,
            "dec": t_dec,
            "notes": target.get("notes", ""),
            "spectrum": t_spectrum,
            "is_synthetic": True,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
        }

        with open(t_file, "w", encoding="utf-8") as f:
            json.dump(target_payload, f, indent=2)

        demo_results.append(
            {
                "name": t_name,
                "ra": t_ra,
                "dec": t_dec,
                "file": str(t_file.name),
                "channels": len(t_spectrum["wavelength_um"]) if t_spectrum else 0,
            }
        )
        logger.info("Wrote static demo spectrum for '%s' to %s", t_name, t_file.name)

    # 3. Save evaluation summary
    eval_file = REPO_ROOT / out_cfg.get("eval_file", "data/output/spectral_eval.json")
    eval_summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_movers": len(movers),
        "spectra_extracted": extracted_count,
        "spectra_none": failed_count,
        "mean_channels_per_spectrum": (
            round(sum(channel_counts) / len(channel_counts), 2) if channel_counts else 0
        ),
        "demo_targets": demo_results,
    }

    eval_file.parent.mkdir(parents=True, exist_ok=True)
    with open(eval_file, "w", encoding="utf-8") as f:
        json.dump(eval_summary, f, indent=2)

    logger.info("==================================================")
    logger.info("MODULE 5 SPECTRA COMPLETE")
    logger.info("  Movers with Spectra: %d / %d", extracted_count, len(movers))
    logger.info("  Movers with None:    %d", failed_count)
    logger.info("  Demo Target Spectra: %d written", len(demo_results))
    logger.info("==================================================")

    return eval_summary
