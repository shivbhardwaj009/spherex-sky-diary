"""Unit and integration tests for SPHEREx Image Processing pipeline (Module 2)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from astropy.stats import sigma_clipped_stats
from photutils.aperture import CircularAperture, aperture_photometry
from photutils.centroids import centroid_2dg, centroid_quadratic

from data.adapter.base import EpochImage, Region
from data.adapter.mock_source import MockSource
from detection.processing.align import build_reference_grid, reproject_epoch
from detection.processing.background import estimate_background, subtract_background
from detection.processing.masking import (
    BIT_ADAPTER_BAD,
    BIT_EDGE,
    BIT_OUTLIER,
    apply_mask,
    build_mask,
)
from detection.processing.normalize import normalize_epochs, select_reference_stars
from detection.processing.pipeline import load_processed_stack, run
from detection.processing.wavelength import comparable_mask, wavelength_difference_map

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def default_region() -> Region:
    """Standard test sky region."""
    return Region(
        name="test_region",
        ra_center=60.0,
        dec_center=20.0,
        radius_deg=0.2,
    )


@pytest.fixture
def mock_source(tmp_path: Path) -> MockSource:
    """Deterministic MockSource fixture."""
    return MockSource(seed=42, n_epochs=5, output_dir=tmp_path)


def test_background_subtraction(mock_source: MockSource, default_region: Region):
    """Mean of source-free regions is near 0 after background subtraction; input is unmutated."""
    epoch = mock_source.load_epoch("mock_epoch_01", default_region, fov_deg=0.2)
    initial_mean = float(np.mean(epoch.pixels))
    assert initial_mean > 70.0  # Background baseline ~80 ADU

    sub_epoch = subtract_background(epoch)

    # Input immutability check
    assert float(np.mean(epoch.pixels)) == initial_mean

    # Global background map stored in metadata
    assert "background_map" in sub_epoch.metadata
    assert sub_epoch.metadata["background_map"].shape == epoch.pixels.shape
    assert abs(sub_epoch.metadata["background_global"] - 80.0) < 5.0

    # Source-free background level check using sigma-clipped stats
    mean_res, med_res, std_res = sigma_clipped_stats(
        sub_epoch.pixels,
        mask=epoch.mask > 0,
        sigma=3.0,
        maxiters=5,
    )
    # The source-free background median must be near 0
    assert abs(med_res) < 0.25, f"Residual background median is {med_res}, expected near 0"


def test_masking_outliers_and_growth(mock_source: MockSource, default_region: Region):
    """Injected cosmic rays and bad pixels are flagged; dilation growth works."""
    epoch = mock_source.load_epoch("mock_epoch_01", default_region, fov_deg=0.2)

    # 1. Without growth
    mask_no_grow = build_mask(epoch, config={"masking": {"grow_pixels": 0, "outlier_sigma": 4.5}})
    # Adapter bad pixels flagged with bit 1
    assert np.any((mask_no_grow & BIT_ADAPTER_BAD) > 0)
    # Outliers / cosmic rays flagged with bit 2
    assert np.any((mask_no_grow & BIT_OUTLIER) > 0)

    # 2. With growth
    mask_with_grow = build_mask(epoch, config={"masking": {"grow_pixels": 2, "outlier_sigma": 4.5}})
    # Mask area must expand
    count_no_grow = int(np.sum((mask_no_grow & (BIT_ADAPTER_BAD | BIT_OUTLIER)) > 0))
    count_grow = int(np.sum((mask_with_grow & (BIT_ADAPTER_BAD | BIT_OUTLIER)) > 0))
    assert count_grow > count_no_grow, "Dilation did not expand masked regions"


def test_alignment_star_centroid_agreement(mock_source: MockSource, default_region: Region):
    """Reprojected star centroids agree across epochs within 0.1 px."""
    ep1 = mock_source.load_epoch("mock_epoch_01", default_region, fov_deg=0.2)
    ep2 = mock_source.load_epoch("mock_epoch_02", default_region, fov_deg=0.2)

    ref_wcs, ref_shape = build_reference_grid(default_region, fov_deg=0.2, image_size=256)
    rep1 = reproject_epoch(ep1, ref_wcs, ref_shape)
    rep2 = reproject_epoch(ep2, ref_wcs, ref_shape)

    # Subtract background to isolate star flux
    rep1_sub = subtract_background(rep1)
    rep2_sub = subtract_background(rep2)

    # Find the brightest isolated stars in the synthesized catalog
    stars = sorted(mock_source._synthesize_stars(default_region), key=lambda s: s["base_flux"], reverse=True)
    
    # Pick a bright star situated well within the interior
    bright_star = None
    for s in stars:
        px, py = ref_wcs.all_world2pix(s["ra"], s["dec"], 0)
        if 40 < float(px) < 216 and 40 < float(py) < 216:
            bright_star = s
            break

    assert bright_star is not None, "No suitable bright interior star found for alignment test"

    star_px, star_py = ref_wcs.all_world2pix(bright_star["ra"], bright_star["dec"], 0)
    ix, iy = int(round(float(star_px))), int(round(float(star_py)))

    # Extract 9x9 subpatch
    rad = 4
    patch1 = rep1_sub.pixels[iy - rad : iy + rad + 1, ix - rad : ix + rad + 1]
    patch2 = rep2_sub.pixels[iy - rad : iy + rad + 1, ix - rad : ix + rad + 1]

    # Measure centroid positions with 2D Gaussian fitting
    c1 = centroid_2dg(patch1)
    c2 = centroid_2dg(patch2)

    alignment_error_px = float(np.hypot(c1[0] - c2[0], c1[1] - c2[1]))
    # Alignment error must be strictly within 0.1 pixels
    assert (
        alignment_error_px <= 0.10
    ), f"Alignment error across epochs is {alignment_error_px:.4f} px (expected <= 0.1 px)"


def test_mask_and_wavelength_propagation_shapes(mock_source: MockSource, default_region: Region):
    """Reprojected arrays match pixel shape and edge non-coverage is flagged."""
    ep = mock_source.load_epoch("mock_epoch_01", default_region, fov_deg=0.2)
    ref_wcs, ref_shape = build_reference_grid(default_region, fov_deg=0.2, image_size=256)

    aligned = reproject_epoch(ep, ref_wcs, ref_shape)

    assert aligned.pixels.shape == ref_shape
    assert aligned.variance.shape == ref_shape
    assert aligned.mask.shape == ref_shape
    assert aligned.wavelength_map.shape == ref_shape

    # Reprojection with offset leaves some edge pixels flagged with BIT_EDGE (4)
    assert np.any((aligned.mask & BIT_EDGE) > 0)


def test_normalization_reduces_flux_scatter(mock_source: MockSource, default_region: Region):
    """Relative photometric normalization reduces epoch-to-epoch star flux scatter."""
    ref_wcs, ref_shape = build_reference_grid(default_region, fov_deg=0.2, image_size=256)

    # Load 3 epochs
    ep_ids = ["mock_epoch_01", "mock_epoch_02", "mock_epoch_03"]
    aligned_stack = []

    # Inject known artificial throughput variations (e.g., 0.85, 1.15, 0.95)
    injected_scales = [0.85, 1.15, 0.95]
    for ep_id, scale in zip(ep_ids, injected_scales):
        ep = mock_source.load_epoch(ep_id, default_region, fov_deg=0.2)
        ep_sub = subtract_background(ep)
        ep_align = reproject_epoch(ep_sub, ref_wcs, ref_shape)
        # Apply synthetic throughput error
        scaled_pixels = ep_align.pixels * scale
        scaled_variance = ep_align.variance * (scale**2)
        aligned_stack.append(
            EpochImage(
                pixels=scaled_pixels,
                variance=scaled_variance,
                mask=ep_align.mask,
                wcs=ep_align.wcs,
                wavelength_map=ep_align.wavelength_map,
                epoch_id=ep_id,
                date=ep_align.date,
                metadata=ep_align.metadata,
            )
        )

    # Select reference stars
    stars = select_reference_stars(aligned_stack, config={"normalization": {"min_reference_stars": 4}})
    assert len(stars) >= 4

    # Calculate pre-normalization flux scatter across reference stars
    apertures = CircularAperture([(s["x"], s["y"]) for s in stars], r=3.5)
    pre_fluxes = []
    for ep in aligned_stack:
        phot = aperture_photometry(ep.pixels, apertures)
        pre_fluxes.append(np.array(phot["aperture_sum"]))
    pre_fluxes_arr = np.array(pre_fluxes)  # shape (n_epochs, n_stars)

    pre_scatters = np.std(pre_fluxes_arr, axis=0) / np.mean(pre_fluxes_arr, axis=0)
    mean_pre_scatter = float(np.mean(pre_scatters))

    # Normalize stack
    norm_stack, scale_factors = normalize_epochs(aligned_stack, stars)

    # Calculate post-normalization flux scatter
    post_fluxes = []
    for ep in norm_stack:
        phot = aperture_photometry(ep.pixels, apertures)
        post_fluxes.append(np.array(phot["aperture_sum"]))
    post_fluxes_arr = np.array(post_fluxes)

    post_scatters = np.std(post_fluxes_arr, axis=0) / np.mean(post_fluxes_arr, axis=0)
    mean_post_scatter = float(np.mean(post_scatters))

    # Scatter must drop substantially
    assert mean_post_scatter < mean_pre_scatter
    assert mean_post_scatter < 0.05, f"Post-normalization scatter is {mean_post_scatter:.4f}, expected < 0.05"


def test_too_few_reference_stars_raises_error(mock_source: MockSource, default_region: Region):
    """select_reference_stars raises ValueError when fewer than minimum stars are found."""
    ref_wcs, ref_shape = build_reference_grid(default_region, fov_deg=0.2, image_size=256)
    ep = mock_source.load_epoch("mock_epoch_01", default_region, fov_deg=0.2)
    aligned = reproject_epoch(ep, ref_wcs, ref_shape)

    # Request an impossible number of reference stars
    with pytest.raises(ValueError, match="Too few reference stars found"):
        select_reference_stars([aligned], config={"normalization": {"min_reference_stars": 999}})


def test_comparable_mask(mock_source: MockSource, default_region: Region):
    """comparable_mask returns all True for identical epochs and shrinks when offsets exceed tol."""
    ep1 = mock_source.load_epoch("mock_epoch_01", default_region, fov_deg=0.2)

    # Identical epoch comparison
    mask_ident = comparable_mask(ep1, ep1, tol_um=0.15)
    valid_pixels = ~np.isnan(ep1.wavelength_map)
    assert np.all(mask_ident[valid_pixels] == True)

    # Shifted wavelength epoch
    ep_shifted = EpochImage(
        pixels=ep1.pixels.copy(),
        variance=ep1.variance.copy(),
        mask=ep1.mask.copy(),
        wcs=ep1.wcs,
        wavelength_map=ep1.wavelength_map + 0.50,  # 0.5 um shift exceeds 0.15 um tolerance
        epoch_id="shifted",
        date=ep1.date,
        metadata=ep1.metadata,
    )

    mask_shifted = comparable_mask(ep1, ep_shifted, tol_um=0.15)
    assert not np.any(mask_shifted)

    # Test difference map
    diff_map = wavelength_difference_map(ep_shifted, ep1)
    assert np.allclose(diff_map, 0.50)


def test_pipeline_deterministic_and_manifest(tmp_path: Path):
    """Pipeline execution is reproducible and writes full manifest.json."""
    out_dir1 = tmp_path / "run1"
    out_dir2 = tmp_path / "run2"

    cfg = {
        "data_source": "mock",
        "seed": 42,
        "region": {
            "name": "ecliptic_plane_test",
            "ra_center": 60.0,
            "dec_center": 20.0,
            "radius_deg": 0.2,
        },
        "fov_deg": 0.2,
    }

    run(config=cfg, output_dir=out_dir1)
    run(config=cfg, output_dir=out_dir2)

    # Check manifest exists
    m1_file = out_dir1 / "manifest.json"
    m2_file = out_dir2 / "manifest.json"
    assert m1_file.exists()
    assert m2_file.exists()

    with open(m1_file, "r", encoding="utf-8") as f:
        m1 = json.load(f)
    with open(m2_file, "r", encoding="utf-8") as f:
        m2 = json.load(f)

    assert m1["schema_version"] == "1.0"
    assert m1["is_synthetic"] is True
    assert m1["normalization_factors"] == m2["normalization_factors"]
    assert m1["reference_stars_count"] == m2["reference_stars_count"]

    # Test load_processed_stack helper
    stack, loaded_manifest = load_processed_stack(out_dir1)
    assert len(stack) == len(m1["epochs"])
    for ep in stack:
        assert isinstance(ep, EpochImage)
        assert ep.pixels.shape == tuple(m1["grid_shape"])
        assert "normalization_factor" in ep.metadata
