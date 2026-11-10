"""SPHEREx Sky Diary — Metadata Catalog Generator and Reader (Module 1).

Builds and reads a tabular observation index (CSV) mapping observation epochs,
spatial bounds, file references, and synthetic flags.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Optional, Union

import pandas as pd

from data.adapter.base import EpochSource, Region

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG_PATH = REPO_ROOT / "data" / "output" / "metadata_catalog.csv"

CATALOG_COLUMNS = [
    "epoch_id",
    "date",
    "band_or_channel",
    "ra_min",
    "ra_max",
    "dec_min",
    "dec_max",
    "file_path",
    "is_synthetic",
]


def build_catalog(
    source: EpochSource,
    region: Region,
    output_path: Optional[Union[Path, str]] = None,
) -> Path:
    """Generate a CSV metadata catalog from an EpochSource.

    Args:
        source: EpochSource instance to enumerate.
        region: Sky region targeting.
        output_path: Destination path for the CSV catalog (default: data/output/metadata_catalog.csv).

    Returns:
        Path to the written CSV file.
    """
    dest = Path(output_path) if output_path is not None else DEFAULT_CATALOG_PATH
    dest.parent.mkdir(parents=True, exist_ok=True)

    epochs = source.list_epochs(region)

    # Compute bounding celestial coordinates for region
    cos_dec = max(0.001, math.cos(math.radians(region.dec_center)))
    delta_ra = region.radius_deg / cos_dec
    ra_min = max(0.0, round(region.ra_center - delta_ra, 6))
    ra_max = min(360.0, round(region.ra_center + delta_ra, 6))
    dec_min = max(-90.0, round(region.dec_center - region.radius_deg, 6))
    dec_max = min(90.0, round(region.dec_center + region.radius_deg, 6))

    rows = []
    for ep in epochs:
        file_ref = str(ep.files[0]) if ep.files else ""
        is_syn = bool(ep.metadata.get("is_synthetic", False))
        rows.append(
            {
                "epoch_id": ep.epoch_id,
                "date": ep.date.isoformat(),
                "band_or_channel": f"bands_1-{ep.band_count}",
                "ra_min": ra_min,
                "ra_max": ra_max,
                "dec_min": dec_min,
                "dec_max": dec_max,
                "file_path": file_ref,
                "is_synthetic": is_syn,
            }
        )

    df = pd.DataFrame(rows, columns=CATALOG_COLUMNS)
    df.to_csv(dest, index=False)
    return dest


def read_catalog(path: Optional[Union[Path, str]] = None) -> pd.DataFrame:
    """Load metadata catalog CSV into a pandas DataFrame.

    Args:
        path: Path to CSV catalog (default: data/output/metadata_catalog.csv).

    Returns:
        Loaded DataFrame.

    Raises:
        FileNotFoundError: If the catalog file does not exist.
        ValueError: If required columns are missing.
    """
    target = Path(path) if path is not None else DEFAULT_CATALOG_PATH
    if not target.exists():
        raise FileNotFoundError(f"Metadata catalog not found: {target}")

    df = pd.read_csv(target)
    missing = [c for c in CATALOG_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Metadata catalog missing required columns: {missing}")

    return df

