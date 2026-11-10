"""SPHEREx Sky Diary — Mock Data Adapter Source (Module 1).

Synthesizes multi-epoch 2D image planes with WCS, star fields, realistic noise,
variance maps, bad pixel masks, position-dependent variable wavelength maps,
and injected moving solar system objects with exact ground truth tracking.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from astropy.wcs import WCS

from data.adapter.base import EpochImage, EpochInfo, EpochSource, Region

REPO_ROOT = Path(__file__).resolve().parents[2]


class MockSource(EpochSource):
    """Synthetic multi-epoch observation source."""

    def __init__(
        self,
        seed: int = 42,
        n_epochs: int = 5,
        base_image_size: int = 256,
        base_fov_deg: float = 0.2,
        n_stars: int = 60,
        n_movers: int = 5,
        psf_sigma: float = 1.5,
        bg_mean: float = 80.0,
        bg_sigma: float = 3.0,
        base_wavelength_um: float = 2.2,
        gradient_um_per_deg: float = 2.5,
        output_dir: Optional[Path | str] = None,
    ) -> None:
        self.seed = seed
        self.n_epochs = n_epochs
        self.base_image_size = base_image_size
        self.base_fov_deg = base_fov_deg
        self.n_stars = n_stars
        self.n_movers = n_movers
        self.psf_sigma = psf_sigma
        self.bg_mean = bg_mean
        self.bg_sigma = bg_sigma
        self.base_wavelength_um = base_wavelength_um
        self.gradient_um_per_deg = gradient_um_per_deg
        self.output_dir = (
            Path(output_dir) if output_dir is not None else REPO_ROOT / "data" / "output"
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Precompute static simulation properties from seed
        self._epochs_cache: Optional[List[EpochInfo]] = None
        self._ground_truth_cache: Optional[Dict[str, Any]] = None

    def _get_seeded_rng(self, sub_seed: int = 0) -> np.random.Generator:
        """Create an isolated deterministic generator."""
        return np.random.default_rng(self.seed + sub_seed)

    def list_epochs(self, region: Region) -> List[EpochInfo]:
        """List simulated observation epochs sorted ascending by date."""
        if self._epochs_cache is not None:
            return self._epochs_cache

        rng = self._get_seeded_rng(sub_seed=100)
        base_time = datetime(2026, 1, 15, 2, 30, 0, tzinfo=timezone.utc)
        
        # Unevenly spaced observation epochs across ~6 months (180 days)
        day_spacing = np.sort(rng.choice(np.arange(5, 175), size=self.n_epochs - 1, replace=False))
        epoch_days = [0] + list(day_spacing)

        epochs: List[EpochInfo] = []
        for idx, days in enumerate(epoch_days):
            ep_id = f"mock_epoch_{idx + 1:02d}"
            ep_date = base_time + timedelta(
                days=int(days),
                hours=int(rng.integers(0, 23)),
                minutes=int(rng.integers(0, 59)),
            )
            epochs.append(
                EpochInfo(
                    epoch_id=ep_id,
                    date=ep_date,
                    files=[f"synthetic://{region.name}/{ep_id}.fits"],
                    band_count=102,
                    metadata={
                        "is_synthetic": True,
                        "epoch_index": idx,
                        "pointing_jitter_arcsec": float(rng.uniform(0.2, 2.5)),
                    },
                )
            )

        # Ensure sorted by date
        epochs.sort(key=lambda ep: ep.date)
        self._epochs_cache = epochs
        return epochs

    def _compute_image_size(self, fov_deg: float) -> int:
        """Scale pixel dimensions dynamically with field of view."""
        scale_ratio = fov_deg / self.base_fov_deg
        calculated_size = int(round(self.base_image_size * scale_ratio))
        # Ensure minimum reasonable dimension
        return max(32, calculated_size)

    def _build_wcs(
        self,
        region: Region,
        image_size: int,
        fov_deg: float,
        epoch_idx: int,
    ) -> WCS:
        """Construct Astropy TAN WCS with small per-epoch pointing jitter."""
        rng = self._get_seeded_rng(sub_seed=200 + epoch_idx)
        # Pointing jitter: fraction of a pixel to a couple pixels (-2.5 to +2.5 px)
        dx_pix = float(rng.uniform(-2.5, 2.5))
        dy_pix = float(rng.uniform(-2.5, 2.5))

        pixel_scale_deg = fov_deg / float(image_size)

        w = WCS(naxis=2)
        # FITS CRPIX is 1-based; in 0-based python indexing, center is (image_size / 2.0)
        w.wcs.crpix = [
            (image_size / 2.0) + 1.0 + dx_pix,
            (image_size / 2.0) + 1.0 + dy_pix,
        ]
        # Standard astronomical convention: RA increases east (left, negative CDELT1)
        w.wcs.cdelt = [-pixel_scale_deg, pixel_scale_deg]
        w.wcs.crval = [region.ra_center, region.dec_center]
        w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
        return w

    def _synthesize_stars(
        self,
        region: Region,
    ) -> List[Dict[str, float]]:
        """Generate static stellar catalog within the region."""
        rng = self._get_seeded_rng(sub_seed=300)
        stars: List[Dict[str, float]] = []

        cos_dec = math.cos(math.radians(region.dec_center))
        # Distribute stars comfortably inside the observable field of view
        spread = (self.base_fov_deg / 2.0) * 0.82

        for s_idx in range(self.n_stars):
            dra = float(rng.uniform(-spread, spread) / cos_dec)
            ddec = float(rng.uniform(-spread, spread))
            # Power-law / Pareto luminosity function (many moderate, several bright)
            flux = float(rng.pareto(a=1.5) * 200.0 + 350.0)

            stars.append(
                {
                    "star_id": f"star_{s_idx:03d}",
                    "ra": region.ra_center + dra,
                    "dec": region.dec_center + ddec,
                    "base_flux": flux,
                    "variability_amp": float(rng.uniform(0.01, 0.05)),
                }
            )
        return stars

    def _synthesize_movers(
        self,
        region: Region,
        epochs: List[EpochInfo],
    ) -> List[Dict[str, Any]]:
        """Generate constant-velocity moving solar system objects."""
        rng = self._get_seeded_rng(sub_seed=400)
        movers: List[Dict[str, Any]] = []

        cos_dec = math.cos(math.radians(region.dec_center))
        ref_date = epochs[0].date

        for m_idx in range(self.n_movers):
            obj_id = f"mock_mover_{m_idx + 1:02d}"
            # Realistic main-belt apparent rates: few to tens of arcsec/day
            ra_rate = float(rng.uniform(8.0, 35.0) * rng.choice([-1.0, 1.0]))
            dec_rate = float(rng.uniform(4.0, 20.0) * rng.choice([-1.0, 1.0]))
            base_flux = float(rng.uniform(500.0, 1200.0))

            # Initial position close to center so trajectory stays in FOV
            init_offset = region.radius_deg * 0.4
            init_ra = region.ra_center + float(rng.uniform(-init_offset, init_offset) / cos_dec)
            init_dec = region.dec_center + float(rng.uniform(-init_offset, init_offset))

            mover_data: Dict[str, Any] = {
                "object_id": obj_id,
                "base_flux": base_flux,
                "motion": {
                    "ra_rate_arcsec_per_day": round(ra_rate, 3),
                    "dec_rate_arcsec_per_day": round(dec_rate, 3),
                },
                "reference_position": {"ra": init_ra, "dec": init_dec},
                "epochs": {},
            }

            for ep in epochs:
                delta_days = (ep.date - ref_date).total_seconds() / 86400.0
                curr_ra = init_ra + ((ra_rate * delta_days) / 3600.0) / cos_dec
                curr_dec = init_dec + ((dec_rate * delta_days) / 3600.0)
                mover_data["epochs"][ep.epoch_id] = {
                    "date": ep.date.isoformat(),
                    "ra": curr_ra,
                    "dec": curr_dec,
                    "flux": base_flux,
                }

            movers.append(mover_data)
        return movers

    def _inject_psf(
        self,
        image: np.ndarray,
        px: float,
        py: float,
        flux: float,
        sigma: float,
    ) -> None:
        """Inject 2D Gaussian point source at subpixel position (px, py)."""
        height, width = image.shape
        # Bounding box around source (5-sigma radius)
        rad = int(math.ceil(sigma * 5.0))
        x_min = max(0, int(math.floor(px - rad)))
        x_max = min(width, int(math.ceil(px + rad + 1)))
        y_min = max(0, int(math.floor(py - rad)))
        y_max = min(height, int(math.ceil(py + rad + 1)))

        if x_min >= x_max or y_min >= y_max:
            return

        y_grid, x_grid = np.mgrid[y_min:y_max, x_min:x_max]
        norm = 2.0 * math.pi * (sigma**2)
        psf = (flux / norm) * np.exp(-((x_grid - px) ** 2 + (y_grid - py) ** 2) / (2.0 * sigma**2))
        image[y_min:y_max, x_min:x_max] += psf

    def load_epoch(
        self,
        epoch_id: str,
        region: Region,
        fov_deg: float = 0.2,
    ) -> EpochImage:
        """Synthesize and return complete EpochImage."""
        epochs = self.list_epochs(region)
        matching_epochs = [ep for ep in epochs if ep.epoch_id == epoch_id]
        if not matching_epochs:
            raise KeyError(f"Unknown epoch_id '{epoch_id}' for region {region.name}")

        epoch_info = matching_epochs[0]
        epoch_idx = next(i for i, ep in enumerate(epochs) if ep.epoch_id == epoch_id)

        image_size = self._compute_image_size(fov_deg)
        wcs = self._build_wcs(region, image_size, fov_deg, epoch_idx)

        # 1. Background noise and baseline
        rng = self._get_seeded_rng(sub_seed=1000 + epoch_idx)
        pixels = rng.normal(loc=self.bg_mean, scale=self.bg_sigma, size=(image_size, image_size)).astype(
            np.float64
        )

        # 2. Inject Star Field
        stars = self._synthesize_stars(region)
        for star in stars:
            # Celestial to pixel conversion (0-based)
            px, py = wcs.all_world2pix(star["ra"], star["dec"], 0)
            # Slight per-epoch flux fluctuation
            var_flux = star["base_flux"] * (1.0 + rng.normal(0.0, star["variability_amp"]))
            self._inject_psf(pixels, px, py, var_flux, self.psf_sigma)

        # 3. Inject Movers
        movers = self._synthesize_movers(region, epochs)
        for mover in movers:
            m_pos = mover["epochs"][epoch_id]
            px, py = wcs.all_world2pix(m_pos["ra"], m_pos["dec"], 0)
            self._inject_psf(pixels, px, py, m_pos["flux"], self.psf_sigma)

        # 4. Variance map (background noise variance + Poisson photon noise)
        gain = 1.5  # e-/ADU
        poisson_var = np.maximum(0.0, pixels - self.bg_mean) / gain
        variance = np.full_like(pixels, self.bg_sigma**2) + poisson_var

        # 5. Mask plane (bitmask: 1 = bad/dead pixel, 2 = cosmic ray hit)
        mask = np.zeros((image_size, image_size), dtype=np.int32)
        # Hot / dead pixels (static)
        bad_rng = self._get_seeded_rng(sub_seed=5000)
        n_bad = int(rng.integers(6, 15))
        for _ in range(n_bad):
            bx = int(bad_rng.integers(0, image_size))
            by = int(bad_rng.integers(0, image_size))
            mask[by, bx] |= 1
            pixels[by, bx] = 0.0  # dead pixel

        # Cosmic ray hits (epoch-specific streaks / spots)
        n_cr = int(rng.integers(3, 8))
        for _ in range(n_cr):
            cx = int(rng.integers(5, image_size - 5))
            cy = int(rng.integers(5, image_size - 5))
            mask[cy, cx] |= 2
            pixels[cy, cx] += float(rng.uniform(800.0, 2500.0))

        # 6. Wavelength map (LVF linear variable filter gradient across image + epoch offset)
        # Position-dependent gradient across FOV
        y_coords, x_coords = np.mgrid[0:image_size, 0:image_size]
        center = image_size / 2.0
        deg_per_pix = fov_deg / float(image_size)

        # Gradient along X and Y axes
        delta_deg_x = (x_coords - center) * deg_per_pix
        delta_deg_y = (y_coords - center) * deg_per_pix

        # Per-epoch offset simulates temporal wavelength coverage change across survey passes
        epoch_wl_shift = (epoch_idx - (self.n_epochs / 2.0)) * 0.18

        wl_gradient = (delta_deg_x + 0.5 * delta_deg_y) * self.gradient_um_per_deg
        wavelength_map = self.base_wavelength_um + epoch_wl_shift + wl_gradient
        # SPHEREx physical detector range is strictly 0.75 - 5.0 um
        wavelength_map = np.clip(wavelength_map, 0.75, 5.0)

        # 7. Generate or refresh ground truth file
        self._ensure_ground_truth(region, epochs, fov_deg)

        return EpochImage(
            pixels=pixels,
            variance=variance,
            mask=mask,
            wcs=wcs,
            wavelength_map=wavelength_map,
            epoch_id=epoch_id,
            date=epoch_info.date,
            metadata={
                "is_synthetic": True,
                "fov_deg": fov_deg,
                "image_size": image_size,
                "seed": self.seed,
            },
        )

    def _ensure_ground_truth(
        self,
        region: Region,
        epochs: List[EpochInfo],
        fov_deg: float,
    ) -> Dict[str, Any]:
        """Save synthetic ground truth JSON if not already generated."""
        if self._ground_truth_cache is not None:
            return self._ground_truth_cache

        gt_file = self.output_dir / "ground_truth.json"
        stars = self._synthesize_stars(region)
        movers = self._synthesize_movers(region, epochs)
        image_size = self._compute_image_size(fov_deg)

        ground_truth: Dict[str, Any] = {
            "is_synthetic": True,
            "seed": self.seed,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "region": {
                "name": region.name,
                "ra_center": region.ra_center,
                "dec_center": region.dec_center,
                "radius_deg": region.radius_deg,
            },
            "fov_deg": fov_deg,
            "image_size": image_size,
            "movers": [],
            "stars_summary": {
                "star_count": len(stars),
                "mean_flux": round(float(np.mean([s["base_flux"] for s in stars])), 2),
                "variability_scatter_mean": round(
                    float(np.mean([s["variability_amp"] for s in stars])), 4
                ),
            },
        }

        for mover in movers:
            mover_record: Dict[str, Any] = {
                "object_id": mover["object_id"],
                "base_flux": mover["base_flux"],
                "motion": mover["motion"],
                "positions_per_epoch": [],
            }
            for ep_idx, ep in enumerate(epochs):
                m_pos = mover["epochs"][ep.epoch_id]
                ep_wcs = self._build_wcs(region, image_size, fov_deg, ep_idx)
                px, py = ep_wcs.all_world2pix(m_pos["ra"], m_pos["dec"], 0)
                in_bounds = bool(0 <= px < image_size and 0 <= py < image_size)
                mover_record["positions_per_epoch"].append(
                    {
                        "epoch_id": ep.epoch_id,
                        "date": ep.date.isoformat(),
                        "ra": round(m_pos["ra"], 6),
                        "dec": round(m_pos["dec"], 6),
                        "pixel_x": round(float(px), 3),
                        "pixel_y": round(float(py), 3),
                        "in_bounds": in_bounds,
                    }
                )
            ground_truth["movers"].append(mover_record)

        with open(gt_file, "w", encoding="utf-8") as f:
            json.dump(ground_truth, f, indent=2)

        self._ground_truth_cache = ground_truth
        return ground_truth

    def get_ground_truth(self) -> Optional[Dict[str, Any]]:
        """Return the simulation ground truth dictionary."""
        gt_file = self.output_dir / "ground_truth.json"
        if gt_file.exists():
            with open(gt_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return self._ground_truth_cache
