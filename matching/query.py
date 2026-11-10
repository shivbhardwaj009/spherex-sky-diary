"""SPHEREx Sky Diary — Known Solar System Object Query.

Queries known Solar System bodies (asteroids, comets, planets) via IMCCE SkyBoT
and JPL Horizons with disk caching, rate limiting, and offline fallback.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy.time import Time

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class PredictedPosition:
    """Predicted position and motion vector of a known body at an observation epoch."""

    epoch_id: str
    date: str  # ISO 8601 UTC
    ra: float  # deg
    dec: float  # deg
    ra_rate_arcsec_per_day: float = 0.0
    dec_rate_arcsec_per_day: float = 0.0
    v_mag: Optional[float] = None


@dataclass
class KnownObject:
    """A known Solar System body with predicted ephemerides across epochs."""

    name: str
    designation: str
    object_type: str  # 'asteroid', 'comet', 'planet', 'other'
    magnitude: Optional[float]
    positions: List[PredictedPosition] = field(default_factory=list)
    mean_ra_rate: float = 0.0
    mean_dec_rate: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "designation": self.designation,
            "object_type": self.object_type,
            "magnitude": self.magnitude,
            "positions": [asdict(p) for p in self.positions],
            "mean_ra_rate": self.mean_ra_rate,
            "mean_dec_rate": self.mean_dec_rate,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> KnownObject:
        """Deserialize from dictionary."""
        positions = [PredictedPosition(**p) for p in data.get("positions", [])]
        return cls(
            name=data["name"],
            designation=data.get("designation", data["name"]),
            object_type=data.get("object_type", "asteroid"),
            magnitude=data.get("magnitude"),
            positions=positions,
            mean_ra_rate=float(data.get("mean_ra_rate", 0.0)),
            mean_dec_rate=float(data.get("mean_dec_rate", 0.0)),
            metadata=data.get("metadata", {}),
        )


def compute_query_hash(
    ra: float,
    dec: float,
    radius_deg: float,
    dates: List[str],
) -> str:
    """Compute deterministic SHA-256 hash for query parameters."""
    normalized_dates = sorted(dates)
    query_str = (
        f"ra={ra:.4f},dec={dec:.4f},rad={radius_deg:.4f},dates={','.join(normalized_dates)}"
    )
    return hashlib.sha256(query_str.encode("utf-8")).hexdigest()


class RateLimiter:
    """Enforces minimum interval between consecutive network queries."""

    def __init__(self, min_interval_sec: float = 0.5):
        self.min_interval = min_interval_sec
        self.last_call = 0.0

    def wait(self) -> None:
        elapsed = time.time() - self.last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_call = time.time()


# Global module rate limiter
_RATE_LIMITER = RateLimiter(min_interval_sec=0.5)


def _normalize_iso_date(date_val: str | datetime) -> str:
    if isinstance(date_val, datetime):
        return date_val.isoformat()
    return str(date_val)


def _load_cache(cache_path: Path) -> Optional[List[KnownObject]]:
    if not cache_path.exists():
        return None
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [KnownObject.from_dict(item) for item in data]
    except Exception as exc:
        logger.warning("Failed to read cache file %s: %s", cache_path, exc)
        return None


def _json_default(obj: Any) -> Any:
    if hasattr(obj, "item"):
        return obj.item()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _save_cache(cache_path: Path, objects: List[KnownObject]) -> None:
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump([obj.to_dict() for obj in objects], f, indent=2, default=_json_default)
    except Exception as exc:
        logger.warning("Failed to write query cache to %s: %s", cache_path, exc)


def _query_skybot_single_epoch(
    ra: float,
    dec: float,
    radius_deg: float,
    epoch_date: str,
    timeout_sec: float = 15.0,
    max_retries: int = 3,
    backoff_factor: float = 1.5,
) -> Any:
    """Execute one cone search against IMCCE SkyBoT via astroquery.

    TODO(VERIFY): SkyBoT default location='500' assumes geocentric coordinates.
    SPHEREx satellite topocentric position may induce up to ~1-3 arcsec parallax
    for fast inner solar system / near-Earth asteroids.
    """
    from astroquery.imcce import Skybot

    # Parse coordinate and time
    coord = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame="icrs")
    norm_epoch = epoch_date.replace("Z", "+00:00")
    dt = datetime.fromisoformat(norm_epoch)
    t = Time(dt)

    # SkyBoT maximum search radius is 10.0 degrees
    search_rad = min(radius_deg, 10.0) * u.deg

    last_exc = None
    for attempt in range(max_retries):
        _RATE_LIMITER.wait()
        try:
            # Query SkyBoT service
            table = Skybot.cone_search(
                coord,
                search_rad,
                t,
                location="500",  # Geocentric
                find_asteroids=True,
                find_comets=True,
                find_planets=True,
            )
            return table
        except Exception as exc:
            last_exc = exc
            delay = backoff_factor * (2**attempt)
            logger.warning(
                "SkyBoT query attempt %d failed: %s. Retrying in %.2fs...",
                attempt + 1,
                exc,
                delay,
            )
            time.sleep(delay)

    raise ConnectionError(f"Failed to query SkyBoT after {max_retries} attempts: {last_exc}")


def query_known_objects(
    ra: float,
    dec: float,
    radius_deg: float,
    epochs: List[Dict[str, Any]],
    offline: bool = False,
    config: Optional[Dict[str, Any]] = None,
) -> Tuple[List[KnownObject], str]:
    """Query known Solar System objects predicted inside the region across observation epochs.

    Args:
        ra: Center RA in degrees (J2000).
        dec: Center Dec in degrees (J2000).
        radius_deg: Field radius in degrees.
        epochs: List of epoch dicts containing 'epoch_id' and 'date'.
        offline: If True, do not contact external network; use disk cache or offline catalog.
        config: Matching service configuration dictionary.

    Returns:
        Tuple of (list_of_known_objects, source_description)
    """
    cfg = config or {}
    cache_cfg = cfg.get("cache", {})
    service_cfg = cfg.get("service", {})
    matching_cfg = cfg.get("matching", {})

    cache_dir_raw = Path(cache_cfg.get("cache_dir", "matching/cache"))
    cache_dir = cache_dir_raw if cache_dir_raw.is_absolute() else REPO_ROOT / cache_dir_raw

    offline_raw = Path(cache_cfg.get("offline_catalog_path", "matching/cache/offline_known.json"))
    offline_catalog_path = offline_raw if offline_raw.is_absolute() else REPO_ROOT / offline_raw

    dates = [_normalize_iso_date(ep["date"]) for ep in epochs]
    query_hash = compute_query_hash(ra, dec, radius_deg, dates)
    cache_file = cache_dir / f"skybot_{query_hash}.json"

    # 1. Check disk cache first
    cached_objects = _load_cache(cache_file)
    if cached_objects is not None:
        logger.info("Loaded %d known objects from query cache: %s", len(cached_objects), cache_file.name)
        return cached_objects, "cache"

    # 2. If offline requested, fall back immediately to offline catalog
    if offline:
        logger.info("Offline mode requested. Loading fallback catalog from %s", offline_catalog_path)
        offline_objects = _load_cache(offline_catalog_path)
        if offline_objects is not None:
            return offline_objects, "offline_catalog"
        logger.warning("Offline catalog %s not found. Returning empty list.", offline_catalog_path)
        return [], "offline_catalog"

    # 3. Calculate search radius with maximum expected motion padding
    # Objects moving across epochs might enter/leave the cone
    max_rate_arcsec_day = float(matching_cfg.get("max_search_rate_arcsec_per_day", 50.0))
    if len(dates) >= 2:
        try:
            d_times = [datetime.fromisoformat(d.replace("Z", "+00:00")) for d in dates]
            span_days = max(1.0, (max(d_times) - min(d_times)).total_seconds() / 86400.0)
        except Exception:
            span_days = 30.0
    else:
        span_days = 1.0

    motion_padding_deg = (max_rate_arcsec_day * span_days) / 3600.0
    effective_radius_deg = min(radius_deg + motion_padding_deg, 9.9)

    # 4. Attempt live network query across epochs
    known_by_name: Dict[str, KnownObject] = {}
    timeout = float(service_cfg.get("timeout_sec", 15.0))
    max_retries = int(service_cfg.get("max_retries", 3))
    backoff = float(service_cfg.get("backoff_factor", 1.5))

    try:
        for ep in epochs:
            ep_id = ep["epoch_id"]
            ep_date = _normalize_iso_date(ep["date"])

            table = _query_skybot_single_epoch(
                ra=ra,
                dec=dec,
                radius_deg=effective_radius_deg,
                epoch_date=ep_date,
                timeout_sec=timeout,
                max_retries=max_retries,
                backoff_factor=backoff,
            )

            if table is None or len(table) == 0:
                continue

            # Process table rows
            for row in table:
                name = str(row["Name"]).strip()
                raw_number = row.get("Number", -1)
                try:
                    number = int(raw_number) if raw_number != -1 and str(raw_number) != "-1" else -1
                except Exception:
                    number = -1
                desig = f"({number}) {name}" if number != -1 else name
                obj_type = str(row.get("Type", "asteroid")).lower()

                # Coordinates (deg)
                obj_ra = float(row["RA"])
                obj_dec = float(row["DEC"])

                # SkyBoT rates are reported in arcsec/hr
                # TODO(VERIFY): Confirm whether SkyBoT RA_rate includes cos(dec)
                ra_rate_day = float(row.get("RA_rate", 0.0)) * 24.0
                dec_rate_day = float(row.get("DEC_rate", 0.0)) * 24.0

                v_mag = float(row["V"]) if "V" in row and not math.isnan(row["V"]) else None

                pos = PredictedPosition(
                    epoch_id=ep_id,
                    date=ep_date,
                    ra=obj_ra,
                    dec=obj_dec,
                    ra_rate_arcsec_per_day=ra_rate_day,
                    dec_rate_arcsec_per_day=dec_rate_day,
                    v_mag=v_mag,
                )

                if name not in known_by_name:
                    known_by_name[name] = KnownObject(
                        name=desig,
                        designation=desig,
                        object_type=obj_type,
                        magnitude=v_mag,
                        positions=[pos],
                        mean_ra_rate=ra_rate_day,
                        mean_dec_rate=dec_rate_day,
                        metadata={"skybot_name": name, "number": number},
                    )
                else:
                    known_by_name[name].positions.append(pos)

        # Compute average rates for each object
        result_objects = list(known_by_name.values())
        for obj in result_objects:
            if obj.positions:
                obj.mean_ra_rate = float(
                    sum(p.ra_rate_arcsec_per_day for p in obj.positions) / len(obj.positions)
                )
                obj.mean_dec_rate = float(
                    sum(p.dec_rate_arcsec_per_day for p in obj.positions) / len(obj.positions)
                )

        # Save to disk cache
        _save_cache(cache_file, result_objects)
        return result_objects, "skybot"

    except Exception as exc:
        logger.warning(
            "Live SkyBoT query failed (%s). Falling back to offline catalog: %s",
            exc,
            offline_catalog_path,
        )
        offline_objects = _load_cache(offline_catalog_path)
        if offline_objects is not None:
            return offline_objects, "offline_catalog"
        return [], "offline_catalog"
