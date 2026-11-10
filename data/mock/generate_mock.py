"""SPHEREx Sky Diary — Mock Data Generator (Module 0).

Generates synthetic SPHEREx moving object catalog conforming to contract v1.0.
All records are marked with is_synthetic: true.
Produces candidates.json and cutout PNGs in data/output/.
"""

from __future__ import annotations

import json
import math
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import yaml
from PIL import Image

# Ensure docs/ is importable for validation
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from docs.validate import validate_dict

# Plausible solar system object designations for known movers
KNOWN_OBJECT_POOL = [
    "99942 Apophis (2004 MN4)",
    "(433) Eros",
    "(101955) Bennu",
    "(162173) Ryugu",
    "(4) Vesta",
    "(1) Ceres",
    "(2) Pallas",
    "(10) Hygiea",
    "(324) Bamberga",
    "2024 BX1",
    "2023 DW",
    "(1566) Icarus",
    "(65803) Didymos",
    "(25143) Itokawa",
    "C/2023 A3 (Tsuchinshan-ATLAS)",
    "(243) Ida",
    "(951) Gaspra",
    "(2060) Chiron",
    "(5145) Pholus",
    "(588) Achilles",
]


def load_config(config_path: Path | str) -> Dict[str, Any]:
    """Load settings from YAML configuration file."""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def generate_cutout_image(
    save_path: Path,
    size: int = 48,
    blob_sigma: float = 3.0,
    peak_snr: float = 18.0,
    rng: np.random.Generator | None = None,
) -> None:
    """Generate a realistic noisy postage-stamp cutout with a Gaussian point source."""
    if rng is None:
        rng = np.random.default_rng()

    # Sky background noise
    bg_mean = 50.0
    bg_sigma = 8.0
    image_data = rng.normal(loc=bg_mean, scale=bg_sigma, size=(size, size))

    # Center coordinates with slight subpixel jitter
    cx = size / 2.0 + rng.uniform(-0.8, 0.8)
    cy = size / 2.0 + rng.uniform(-0.8, 0.8)

    # 2D Gaussian point spread function (PSF)
    y, x = np.mgrid[0:size, 0:size]
    gaussian_psf = np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2.0 * blob_sigma**2))
    peak_flux = peak_snr * bg_sigma
    image_data += peak_flux * gaussian_psf

    # Clip to valid 8-bit image range
    clipped = np.clip(image_data, 0, 255).astype(np.uint8)
    img = Image.fromarray(clipped, mode="L")
    save_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(save_path, format="PNG")


def generate_solar_reflectance_spectrum(
    wavelength_um: np.ndarray,
    mover_type: str,
    rng: np.random.Generator,
) -> Dict[str, List[float]]:
    """Synthesize a 102-point SPHEREx spectrum (0.75 - 5.0 um).

    Simulates reflected solar continuum with characteristic asteroid spectral slopes:
    - S-type (silicate absorption near 1.0 um and 2.0 um)
    - C-type (neutral/flat or slight blue-UV drop, hydrated feature near 2.7-3.0 um)
    - D/T-type (steep red slope across near-IR)
    Plus thermal emission rise longward of 3.8 um.
    """
    n_points = len(wavelength_um)

    # Solar continuum approximation across near-IR
    # Peak near 0.5 um, falling off as blackbody ~ 5778 K
    solar_flux = (1.0 / (wavelength_um**4)) / (np.exp(2.48 / wavelength_um) - 1.0)
    solar_flux = solar_flux / np.max(solar_flux)

    # Spectral reflectance curves
    if mover_type == "known":
        # Mixed S-type and C-type features
        slope = rng.uniform(0.05, 0.25)
        reflectance = 1.0 + slope * (wavelength_um - 1.0)

        # 1.0 um silicate band absorption
        band1 = 0.15 * np.exp(-((wavelength_um - 1.05) ** 2) / (2 * 0.18**2))
        # 2.0 um band absorption
        band2 = 0.08 * np.exp(-((wavelength_um - 1.95) ** 2) / (2 * 0.25**2))
        # 2.9 um hydrated water/OH feature
        band3 = 0.06 * np.exp(-((wavelength_um - 2.85) ** 2) / (2 * 0.15**2))
        reflectance = reflectance - band1 - band2 - band3
    else:
        # Unknown mover / primitive outer asteroid / comet
        slope = rng.uniform(0.15, 0.35)
        reflectance = 1.0 + slope * (wavelength_um - 1.0)
        # Deep 3.0 um volatile / ice absorption feature
        ice_band = 0.14 * np.exp(-((wavelength_um - 3.05) ** 2) / (2 * 0.20**2))
        reflectance = reflectance - ice_band

    # Thermal emission tail at long wavelengths (> 3.5 um)
    thermal_onset = np.clip((wavelength_um - 3.5) / 1.5, 0.0, 1.0)
    thermal_flux = 0.4 * (thermal_onset**2)

    total_flux = (reflectance * solar_flux * 150.0) + thermal_flux * 40.0

    # 1-sigma uncertainty (roughly 2-4% + low-flux noise floor)
    flux_err = np.maximum(0.8, total_flux * rng.uniform(0.02, 0.04, size=n_points))
    noisy_flux = total_flux + rng.normal(0.0, flux_err)

    return {
        "wavelength_um": [round(float(w), 4) for w in wavelength_um],
        "flux": [round(float(f), 3) for f in noisy_flux],
        "flux_err": [round(float(e), 3) for e in flux_err],
    }


def generate_mock_catalog(
    config_path: Path | str = REPO_ROOT / "config" / "settings.yaml",
    output_file: Optional[Path | str] = None,
) -> Path:
    """Generate mock dataset conforming to schema 1.0."""
    cfg = load_config(config_path)

    seed = cfg.get("seed", 42)
    # Seed both numpy and python random for total reproducibility
    rng = np.random.default_rng(seed)
    random.seed(seed)
    np.random.seed(seed)

    region_cfg = cfg.get("region", {})
    ra_center = float(region_cfg.get("ra_center", 60.0))
    dec_center = float(region_cfg.get("dec_center", 20.0))
    radius_deg = float(region_cfg.get("radius_deg", 0.2))
    region_name = str(region_cfg.get("name", "ecliptic_plane_test"))
    fov_deg = float(cfg.get("fov_deg", 0.2))

    output_dir = REPO_ROOT / cfg.get("output_dir", "data/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    cutouts_dir = output_dir / "cutouts"
    cutouts_dir.mkdir(parents=True, exist_ok=True)

    # 1. Define 6 observation epochs across ~6 months (180 days)
    base_time = datetime(2026, 1, 10, 0, 0, 0, tzinfo=timezone.utc)
    epoch_day_offsets = [0, 22, 58, 95, 137, 180]
    epochs: List[Dict[str, Any]] = []
    epoch_datetimes: List[datetime] = []

    for idx, day_offset in enumerate(epoch_day_offsets):
        ep_id = f"epoch_{idx + 1:02d}"
        ep_time = base_time + timedelta(
            days=day_offset,
            hours=int(rng.integers(2, 22)),
            minutes=int(rng.integers(0, 59)),
        )
        epoch_datetimes.append(ep_time)
        epochs.append(
            {
                "epoch_id": ep_id,
                "date": ep_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "band_count": 102,
            }
        )

    # 2. Synthesize exactly 25 movers (15 known ~ 60%, 10 unknown ~ 40%)
    total_movers = 25
    known_count = 15
    unknown_count = total_movers - known_count

    types = ["known"] * known_count + ["unknown"] * unknown_count
    # Shuffle predictably with seeded RNG
    shuffled_indices = rng.permutation(total_movers)

    # Standard SPHEREx 102 channels from 0.75 um to 5.0 um
    wavelength_grid = np.linspace(0.75, 5.0, 102)

    movers: List[Dict[str, Any]] = []
    known_pool_copy = list(KNOWN_OBJECT_POOL)

    for i in range(total_movers):
        m_idx = shuffled_indices[i]
        m_type = types[m_idx]
        obj_id = f"mov_{i + 1:03d}"

        if m_type == "known":
            match_name = known_pool_copy[i % len(known_pool_copy)]
            confidence = round(float(rng.uniform(0.90, 0.99)), 3)
        else:
            match_name = None
            confidence = round(float(rng.uniform(0.70, 0.89)), 3)

        # Plausible main-belt motion: few to tens of arcsec/day
        # Main belt asteroid typical apparent motion ~ 10-35 arcsec/day
        ra_rate = float(rng.uniform(6.0, 32.0) * rng.choice([-1.0, 1.0]))
        dec_rate = float(rng.uniform(3.0, 18.0) * rng.choice([-1.0, 1.0]))

        # Reference position inside region (J2000)
        # Offset slightly from center so track fits within FOV
        r_offset = float(rng.uniform(0.05, radius_deg * 0.65))
        theta = float(rng.uniform(0, 2 * math.pi))
        base_ra = ra_center + (r_offset * math.cos(theta)) / math.cos(math.radians(dec_center))
        base_dec = dec_center + (r_offset * math.sin(theta))

        # Each mover observed in 3 to 6 epochs
        k_epochs = int(rng.integers(3, 7))  # 3, 4, 5, or 6
        chosen_epoch_indices = sorted(rng.choice(len(epochs), size=k_epochs, replace=False))

        cos_dec = math.cos(math.radians(base_dec))
        detections: List[Dict[str, Any]] = []

        ref_epoch_dt = epoch_datetimes[chosen_epoch_indices[0]]

        for ep_idx in chosen_epoch_indices:
            ep = epochs[ep_idx]
            ep_dt = epoch_datetimes[ep_idx]
            delta_days = (ep_dt - ref_epoch_dt).total_seconds() / 86400.0

            # Constant velocity motion + small astrometric noise (sigma ~ 0.06 arcsec)
            noise_ra_arcsec = float(rng.normal(0.0, 0.06))
            noise_dec_arcsec = float(rng.normal(0.0, 0.06))

            det_ra = base_ra + ((ra_rate * delta_days + noise_ra_arcsec) / 3600.0) / cos_dec
            det_dec = base_dec + ((dec_rate * delta_days + noise_dec_arcsec) / 3600.0)

            # Plausible flux with epoch-to-epoch lightcurve variation
            base_flux = 120.0 if m_type == "known" else 55.0
            flux_val = round(float(base_flux * rng.uniform(0.92, 1.08)), 2)

            # Generate cutout image file
            cutout_filename = f"{obj_id}_{ep['epoch_id']}.png"
            cutout_filepath = cutouts_dir / cutout_filename
            generate_cutout_image(
                cutout_filepath,
                size=48,
                peak_snr=15.0 if m_type == "known" else 9.0,
                rng=rng,
            )

            detections.append(
                {
                    "epoch_id": ep["epoch_id"],
                    "date": ep["date"],
                    "ra": round(det_ra, 6),
                    "dec": round(det_dec, 6),
                    "flux": flux_val,
                    "cutout_url": f"cutouts/{cutout_filename}",
                }
            )

        # 102-point spectrum with realistic shape
        spectrum_data = generate_solar_reflectance_spectrum(
            wavelength_grid,
            mover_type=m_type,
            rng=rng,
        )

        movers.append(
            {
                "object_id": obj_id,
                "ra": round(detections[0]["ra"], 6),
                "dec": round(detections[0]["dec"], 6),
                "type": m_type,
                "match_name": match_name,
                "confidence": confidence,
                "is_synthetic": True,
                "motion": {
                    "ra_rate_arcsec_per_day": round(ra_rate, 2),
                    "dec_rate_arcsec_per_day": round(dec_rate, 2),
                },
                "detections": detections,
                "spectrum": spectrum_data,
            }
        )

    catalog_data: Dict[str, Any] = {
        "schema_version": "1.0",
        "data_version": "v1.0-mock",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fov_deg": fov_deg,
        "region": {
            "name": region_name,
            "ra_center": ra_center,
            "dec_center": dec_center,
            "radius_deg": radius_deg,
        },
        "epochs": epochs,
        "movers": movers,
    }

    # Validate against contract schema before writing
    validate_dict(catalog_data)

    out_file = Path(output_file) if output_file is not None else (output_dir / "candidates.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(catalog_data, f, indent=2)

    return out_file


def main() -> None:
    """CLI script runner."""
    print("[SPHEREx Mock Generator] Generating mock dataset...")
    out_file = generate_mock_catalog()
    print(f"[SPHEREx Mock Generator] Successfully wrote candidates to: {out_file}")


if __name__ == "__main__":
    main()

