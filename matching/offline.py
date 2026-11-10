"""SPHEREx Sky Diary — Offline Catalog Generator & Fallback Manager.

Generates and manages offline known Solar System ephemeris catalogs for synthetic
and offline testing environments when live network access is disabled.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from matching.query import KnownObject, PredictedPosition

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]

OFFLINE_NAMES_POOL = [
    "(433) Eros",
    "(1) Ceres",
    "(4) Vesta",
    "(2) Pallas",
    "99942 Apophis (2004 MN4)",
    "(101955) Bennu",
    "(162173) Ryugu",
    "(10) Hygiea",
    "(324) Bamberga",
]


def generate_mock_known_catalog(
    ground_truth_path: Path | str = REPO_ROOT / "data" / "output" / "ground_truth.json",
    output_path: Path | str = REPO_ROOT / "matching" / "cache" / "offline_known.json",
    known_fraction: float = 0.60,
) -> Path:
    """Generate an offline known object catalog derived from ground truth synthetic movers.

    Converts a subset of ground-truth injected movers into 'known' asteroids with realistic
    names, plus adds simulated non-detected known asteroids for validation testing.

    Args:
        ground_truth_path: Path to synthetic ground_truth.json.
        output_path: Output path for offline known objects catalog JSON.
        known_fraction: Fraction of synthetic movers to designate as known catalog asteroids.

    Returns:
        Path to generated offline catalog file.
    """
    gt_file = Path(ground_truth_path)
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    known_objects: List[KnownObject] = []

    if gt_file.exists():
        with open(gt_file, "r", encoding="utf-8") as f:
            gt_data = json.load(f)

        movers = gt_data.get("movers", [])
        num_known = max(1, int(round(len(movers) * known_fraction)))

        for idx, mover in enumerate(movers[:num_known]):
            name = OFFLINE_NAMES_POOL[idx % len(OFFLINE_NAMES_POOL)]
            motion = mover.get("motion", {})
            ra_rate = float(motion.get("ra_rate_arcsec_per_day", 15.0))
            dec_rate = float(motion.get("dec_rate_arcsec_per_day", 5.0))

            positions: List[PredictedPosition] = []
            for pos in mover.get("positions_per_epoch", []):
                # Injected ground truth positions
                positions.append(
                    PredictedPosition(
                        epoch_id=pos["epoch_id"],
                        date=pos["date"],
                        ra=float(pos["ra"]),
                        dec=float(pos["dec"]),
                        ra_rate_arcsec_per_day=ra_rate,
                        dec_rate_arcsec_per_day=dec_rate,
                        v_mag=round(14.5 + idx * 0.8, 2),
                    )
                )

            known_objects.append(
                KnownObject(
                    name=name,
                    designation=name,
                    object_type="asteroid",
                    magnitude=round(14.5 + idx * 0.8, 2),
                    positions=positions,
                    mean_ra_rate=ra_rate,
                    mean_dec_rate=dec_rate,
                    metadata={"source": "ground_truth_synthetic", "mover_id": mover.get("object_id")},
                )
            )

    # Add one non-recovered faint known asteroid in the field (for realistic miss reporting)
    faint_asteroid = KnownObject(
        name="(10) Hygiea",
        designation="(10) Hygiea",
        object_type="asteroid",
        magnitude=19.8,  # Below detection SNR threshold
        positions=[
            PredictedPosition(
                epoch_id="mock_epoch_01",
                date="2026-01-16T00:39:00+00:00",
                ra=60.0150,
                dec=20.0250,
                ra_rate_arcsec_per_day=12.0,
                dec_rate_arcsec_per_day=4.0,
                v_mag=19.8,
            ),
            PredictedPosition(
                epoch_id="mock_epoch_02",
                date="2026-01-22T19:35:00+00:00",
                ra=60.0380,
                dec=20.0320,
                ra_rate_arcsec_per_day=12.0,
                dec_rate_arcsec_per_day=4.0,
                v_mag=19.8,
            ),
            PredictedPosition(
                epoch_id="mock_epoch_03",
                date="2026-01-23T07:42:00+00:00",
                ra=60.0400,
                dec=20.0330,
                ra_rate_arcsec_per_day=12.0,
                dec_rate_arcsec_per_day=4.0,
                v_mag=19.8,
            ),
        ],
        mean_ra_rate=12.0,
        mean_dec_rate=4.0,
        metadata={"source": "synthetic_miss_benchmark"},
    )
    known_objects.append(faint_asteroid)

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump([obj.to_dict() for obj in known_objects], f, indent=2)

    logger.info("Generated offline known catalog with %d objects at %s", len(known_objects), out_file)
    return out_file

