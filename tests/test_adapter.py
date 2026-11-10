"""Unit and integration tests for SPHEREx Data Adapter layer (Module 1)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from data.adapter.base import EpochImage, EpochInfo, EpochSource, Region
from data.adapter.factory import get_source
from data.adapter.irsa_source import IrsaFitsSource
from data.adapter.metadata_catalog import CATALOG_COLUMNS, build_catalog, read_catalog
from data.adapter.mock_source import MockSource

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
    """MockSource instance pointing to temporary output directory."""
    return MockSource(seed=42, n_epochs=5, output_dir=tmp_path)


def test_mock_source_deterministic(default_region: Region, tmp_path: Path):
    """Same seed produces strictly identical array outputs; different seed differs."""
    source_a = MockSource(seed=123, n_epochs=3, output_dir=tmp_path / "a")
    source_b = MockSource(seed=123, n_epochs=3, output_dir=tmp_path / "b")
    source_c = MockSource(seed=999, n_epochs=3, output_dir=tmp_path / "c")

    img_a = source_a.load_epoch("mock_epoch_01", default_region, fov_deg=0.2)
    img_b = source_b.load_epoch("mock_epoch_01", default_region, fov_deg=0.2)
    img_c = source_c.load_epoch("mock_epoch_01", default_region, fov_deg=0.2)

    # Identical seed -> identical pixels, variance, mask, wavelength
    np.testing.assert_array_equal(img_a.pixels, img_b.pixels)
    np.testing.assert_array_equal(img_a.variance, img_b.variance)
    np.testing.assert_array_equal(img_a.mask, img_b.mask)
    np.testing.assert_array_equal(img_a.wavelength_map, img_b.wavelength_map)

    # Different seed -> distinct pixel noise realization
    assert not np.array_equal(img_a.pixels, img_c.pixels)


def test_list_epochs_sorted_and_count(mock_source: MockSource, default_region: Region):
    """list_epochs returns requested count and sorted ascending dates."""
    epochs = mock_source.list_epochs(default_region)
    assert len(epochs) == 5

    # Check date sorting
    for i in range(len(epochs) - 1):
        assert epochs[i].date <= epochs[i + 1].date

    # Check synthetic metadata flag
    for ep in epochs:
        assert ep.metadata.get("is_synthetic") is True
        assert ep.band_count == 102


def test_wavelength_map_properties(mock_source: MockSource, default_region: Region):
    """wavelength_map shape matches pixels and stays strictly within 0.75 - 5.0 um."""
    img_ep1 = mock_source.load_epoch("mock_epoch_01", default_region, fov_deg=0.2)
    img_ep2 = mock_source.load_epoch("mock_epoch_02", default_region, fov_deg=0.2)

    assert img_ep1.wavelength_map.shape == img_ep1.pixels.shape
    assert np.all(img_ep1.wavelength_map >= 0.75)
    assert np.all(img_ep1.wavelength_map <= 5.0)

    # Temporal / per-epoch offset ensures multi-epoch diversity
    assert not np.allclose(img_ep1.wavelength_map, img_ep2.wavelength_map)


def test_wcs_round_trip_and_peak(mock_source: MockSource, default_region: Region):
    """WCS converts ground truth RA/Dec to pixel position where source peaks (within 0.5 px)."""
    img = mock_source.load_epoch("mock_epoch_01", default_region, fov_deg=0.2)
    gt = mock_source.get_ground_truth()
    assert gt is not None

    # Pick the first injected mover
    mover = gt["movers"][0]
    pos = next(p for p in mover["positions_per_epoch"] if p["epoch_id"] == "mock_epoch_01")
    ra, dec = pos["ra"], pos["dec"]
    expected_px, expected_py = pos["pixel_x"], pos["pixel_y"]

    # 1. World to pixel conversion
    calc_px_arr, calc_py_arr = img.wcs.all_world2pix(ra, dec, 0)
    calc_px = float(calc_px_arr)
    calc_py = float(calc_py_arr)
    assert abs(calc_px - expected_px) < 1e-3
    assert abs(calc_py - expected_py) < 1e-3

    # 2. Pixel to world round-trip
    calc_ra_arr, calc_dec_arr = img.wcs.all_pix2world(calc_px, calc_py, 0)
    calc_ra = float(calc_ra_arr)
    calc_dec = float(calc_dec_arr)
    assert abs(calc_ra - ra) < 1e-6
    assert abs(calc_dec - dec) < 1e-6

    # 3. Peak check in synthesized image
    # Compute the centroid (flux-weighted center of light) and discrete peak
    int_x = int(round(calc_px))
    int_y = int(round(calc_py))

    patch_rad = 3
    y_min, y_max = int_y - patch_rad, int_y + patch_rad + 1
    x_min, x_max = int_x - patch_rad, int_x + patch_rad + 1
    patch = np.maximum(0.0, img.pixels[y_min:y_max, x_min:x_max] - mock_source.bg_mean)

    # Flux-weighted subpixel centroid
    y_grid, x_grid = np.mgrid[y_min:y_max, x_min:x_max]
    total_flux = np.sum(patch)
    assert total_flux > 0
    centroid_x = float(np.sum(x_grid * patch) / total_flux)
    centroid_y = float(np.sum(y_grid * patch) / total_flux)
    dist_to_centroid = np.hypot(centroid_x - calc_px, centroid_y - calc_py)
    assert dist_to_centroid <= 0.5, (
        f"Centroid at ({centroid_x:.3f}, {centroid_y:.3f}) is {dist_to_centroid:.3f} px from ({calc_px:.3f}, {calc_py:.3f})"
    )

    # Find the maximum flux pixel inside the neighborhood
    rel_max_y, rel_max_x = np.unravel_index(np.argmax(patch), patch.shape)
    peak_y = y_min + rel_max_y
    peak_x = x_min + rel_max_x
    dist_to_peak = np.hypot(peak_x - calc_px, peak_y - calc_py)
    assert dist_to_peak <= 0.5, (
        f"Peak at ({peak_x}, {peak_y}) is {dist_to_peak:.3f} px from ({calc_px:.3f}, {calc_py:.3f})"
    )


def test_ground_truth_file_and_valid_json(mock_source: MockSource, default_region: Region):
    """Ground truth file is generated, valid JSON, and correctly structured."""
    mock_source.load_epoch("mock_epoch_01", default_region, fov_deg=0.2)
    gt_file = mock_source.output_dir / "ground_truth.json"
    assert gt_file.exists()

    with open(gt_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["is_synthetic"] is True
    assert data["seed"] == mock_source.seed
    assert len(data["movers"]) == mock_source.n_movers
    assert "stars_summary" in data

    # Verify mover format
    m0 = data["movers"][0]
    assert "object_id" in m0
    assert "motion" in m0
    assert len(m0["positions_per_epoch"]) == mock_source.n_epochs


def test_factory_sources(tmp_path: Path):
    """Factory returns MockSource for 'mock', IrsaFitsSource for 'irsa', raises for others."""
    # Mock source
    src_mock = get_source({"data_source": "mock", "seed": 99, "output_dir": str(tmp_path)})
    assert isinstance(src_mock, MockSource)
    assert src_mock.seed == 99

    # IRSA source
    src_irsa = get_source({"data_source": "irsa", "irsa_data_dir": str(tmp_path)})
    assert isinstance(src_irsa, IrsaFitsSource)

    # Invalid source
    with pytest.raises(ValueError, match="Invalid data_source: 'unknown_source'"):
        get_source({"data_source": "unknown_source"})


def test_irsa_raises_not_implemented(default_region: Region):
    """IrsaFitsSource methods raise NotImplementedError with TODO(VERIFY) explanations."""
    irsa = IrsaFitsSource()

    with pytest.raises(NotImplementedError, match="TODO\\(VERIFY\\)"):
        irsa.list_epochs(default_region)

    with pytest.raises(NotImplementedError, match="TODO\\(VERIFY\\)"):
        irsa.load_epoch("any_epoch", default_region)

    # get_ground_truth returns None for flight data
    assert irsa.get_ground_truth() is None


def test_fov_deg_scales_image_size(mock_source: MockSource, default_region: Region):
    """Changing fov_deg changes image size accordingly."""
    img_default = mock_source.load_epoch("mock_epoch_01", default_region, fov_deg=0.2)
    assert img_default.pixels.shape == (256, 256)

    img_half = mock_source.load_epoch("mock_epoch_01", default_region, fov_deg=0.1)
    assert img_half.pixels.shape == (128, 128)

    img_double = mock_source.load_epoch("mock_epoch_01", default_region, fov_deg=0.4)
    assert img_double.pixels.shape == (512, 512)


def test_metadata_catalog(mock_source: MockSource, default_region: Region, tmp_path: Path):
    """build_catalog creates valid CSV and read_catalog parses it into a DataFrame."""
    csv_path = tmp_path / "metadata_catalog.csv"
    returned_path = build_catalog(mock_source, default_region, output_path=csv_path)
    assert returned_path.exists()

    df = read_catalog(returned_path)
    assert len(df) == mock_source.n_epochs
    for col in CATALOG_COLUMNS:
        assert col in df.columns

    assert df["is_synthetic"].all()
    assert (df["ra_max"] >= df["ra_min"]).all()
    assert (df["dec_max"] >= df["dec_min"]).all()
