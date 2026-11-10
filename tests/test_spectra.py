"""Tests for Module 5: Spectrum Extraction & Diagnostics.

Uses MockSource and hand-computed test cases without external network calls.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from data.adapter.base import EpochImage, Region
from data.adapter.mock_source import MockSource
from docs.validate import validate_dict
from spectra.api import get_spectrum
from spectra.assemble import build_spectrum
from spectra.crosscheck import compare_to_reference, generate_mock_reference_csv
from spectra.photometry import PhotometryMeasurement, measure_source
from spectra.stacking import compare_snr_gain, stack_epochs_by_band

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def test_region():
    return Region(
        name="test_spectra_patch",
        ra_center=60.0,
        dec_center=20.0,
        radius_deg=0.2,
    )


@pytest.fixture
def mock_source():
    return MockSource(seed=42, n_epochs=5, base_fov_deg=0.2)


def test_injected_source_spectral_shape_recovery(mock_source, test_region):
    """Recover injected source flux within justified aperture photometry tolerance.

    Justification:
    A circular aperture of radius r=3.5 pixels on a 2D Gaussian PSF with sigma=1.5 pixels
    encloses an encircled energy fraction of:
        EE = 1 - exp(- (3.5^2) / (2 * 1.5^2)) = 1 - exp(-2.722) = 93.4%.
    With local background subtraction and photon Poisson noise, uncorrected measured flux
    is expected to agree with the injected flux within 15% (80% to 105%).
    """
    epochs = mock_source.list_epochs(test_region)
    ep_img = mock_source.load_epoch(epochs[0].epoch_id, test_region)

    gt = mock_source.get_ground_truth()
    first_mover = gt["movers"][0]
    m_pos = first_mover["positions_per_epoch"][0]
    injected_flux = first_mover["base_flux"]

    meas, reason = measure_source(
        epoch_image=ep_img,
        ra=m_pos["ra"],
        dec=m_pos["dec"],
        aperture_radius_pix=3.5,
    )

    assert meas is not None, f"Measurement failed: {reason}"
    assert meas.flux > 0.0

    # Verify recovery within 15% tolerance of encircled Gaussian PSF flux
    fraction = meas.flux / injected_flux
    assert 0.80 <= fraction <= 1.05, f"Measured {meas.flux:.1f} vs Injected {injected_flux:.1f} (ratio {fraction:.3f})"


def test_wavelength_assignment_per_epoch(mock_source, test_region):
    """Different observation epochs sample different wavelengths at the same sky coordinate.

    Tests that MockSource position-dependent LVF linear variable filter shifts wavelengths
    across survey passes.
    """
    epochs = mock_source.list_epochs(test_region)
    ep1 = mock_source.load_epoch(epochs[0].epoch_id, test_region)
    ep3 = mock_source.load_epoch(epochs[2].epoch_id, test_region)

    target_ra = test_region.ra_center
    target_dec = test_region.dec_center

    m1, _ = measure_source(ep1, ra=target_ra, dec=target_dec)
    m3, _ = measure_source(ep3, ra=target_ra, dec=target_dec)

    assert m1 is not None and m3 is not None
    assert m1.wavelength_um != m3.wavelength_um
    # In MockSource, epoch_wl_shift = (epoch_idx - 2.5) * 0.18 um -> delta between ep 0 and 2 is ~0.36 um
    delta_wl = abs(m3.wavelength_um - m1.wavelength_um)
    assert 0.25 <= delta_wl <= 0.45


def test_masked_and_edge_apertures_skipped(mock_source, test_region):
    """Apertures touching detector boundaries or heavy masking are skipped with a clear reason."""
    epochs = mock_source.list_epochs(test_region)
    ep_img = mock_source.load_epoch(epochs[0].epoch_id, test_region)

    # 1. Coordinate directly on boundary (pixel x ~ 0.5, y ~ 0.5)
    edge_ra, edge_dec = ep_img.wcs.all_pix2world(1.0, 1.0, 0)
    meas_edge, reason_edge = measure_source(ep_img, ra=float(edge_ra), dec=float(edge_dec), aperture_radius_pix=3.5)
    assert meas_edge is None
    assert "aperture_touches_edge" in reason_edge

    # 2. Heavily masked coordinate (artificially set aperture mask to 1)
    center_ra, center_dec = ep_img.wcs.all_pix2world(128.0, 128.0, 0)
    masked_img = EpochImage(
        pixels=ep_img.pixels.copy(),
        variance=ep_img.variance.copy(),
        mask=np.ones_like(ep_img.mask),  # 100% masked
        wcs=ep_img.wcs,
        wavelength_map=ep_img.wavelength_map,
        epoch_id=ep_img.epoch_id,
        date=ep_img.date,
        metadata=ep_img.metadata,
    )
    meas_mask, reason_mask = measure_source(masked_img, ra=float(center_ra), dec=float(center_dec))
    assert meas_mask is None
    assert "aperture_masked_fraction_too_high" in reason_mask


def test_binning_weighted_mean_and_error_propagation():
    """Verify inverse-variance weighted mean and error propagation against hand-computed values.

    Hand-computed test case:
      Point 1: lambda = 1.00 um, F1 = 100.0, sigma1 = 2.0  => w1 = 1 / 4 = 0.25
      Point 2: lambda = 1.02 um, F2 = 120.0, sigma2 = 4.0  => w2 = 1 / 16 = 0.0625
      Sum(w) = 0.3125
      Weighted Flux  = (0.25 * 100 + 0.0625 * 120) / 0.3125 = 32.5 / 0.3125 = 104.0
      Weighted Error = 1 / sqrt(0.3125) = 1.788854...
      Weighted WL    = (0.25 * 1.00 + 0.0625 * 1.02) / 0.3125 = 1.004 um
    """
    p1 = PhotometryMeasurement(
        epoch_id="ep1",
        date="2026-01-01T00:00:00Z",
        ra=60.0,
        dec=20.0,
        pixel_x=10.0,
        pixel_y=10.0,
        flux=100.0,
        flux_err=2.0,
        wavelength_um=1.00,
        quality_flag=0,
        background=10.0,
        background_rms=1.0,
    )
    p2 = PhotometryMeasurement(
        epoch_id="ep2",
        date="2026-01-05T00:00:00Z",
        ra=60.0,
        dec=20.0,
        pixel_x=12.0,
        pixel_y=12.0,
        flux=120.0,
        flux_err=4.0,
        wavelength_um=1.02,
        quality_flag=0,
        background=10.0,
        background_rms=1.0,
    )

    spectrum = build_spectrum([p1, p2], bin_width_um=0.10)
    assert spectrum is not None
    assert len(spectrum["wavelength_um"]) == 1
    assert math.isclose(spectrum["wavelength_um"][0], 1.004, abs_tol=1e-3)
    assert math.isclose(spectrum["flux"][0], 104.0, abs_tol=1e-2)
    assert math.isclose(spectrum["flux_err"][0], 1.7889, abs_tol=1e-3)


def test_moving_source_aperture_follows_track(mock_source, test_region):
    """Aperture tracking the moving object recovers significantly higher flux than a fixed aperture."""
    gt = mock_source.get_ground_truth()
    first_mover = gt["movers"][0]
    detections = [
        {"epoch_id": pos["epoch_id"], "date": pos["date"], "ra": pos["ra"], "dec": pos["dec"]}
        for pos in first_mover["positions_per_epoch"]
        if pos["in_bounds"]
    ]

    ref_ra = detections[0]["ra"]
    ref_dec = detections[0]["dec"]

    # 1. Extract with motion tracking
    spec_tracked = get_spectrum(
        ra=ref_ra,
        dec=ref_dec,
        source=mock_source,
        region=test_region,
        track=detections,
        motion=first_mover["motion"],
    )

    # 2. Extract with static fixed aperture at initial coordinate
    spec_static = get_spectrum(
        ra=ref_ra,
        dec=ref_dec,
        source=mock_source,
        region=test_region,
        track=None,
        motion=None,
    )

    assert spec_tracked is not None
    mean_tracked_flux = float(np.mean(spec_tracked["flux"]))

    # In static aperture, as the mover drifts away, later epochs measure only background noise (mean ~ 0)
    # Tracked flux must be substantially higher than static un-tracked flux
    if spec_static is not None:
        mean_static_flux = float(np.mean(spec_static["flux"]))
        assert mean_tracked_flux > 1.5 * mean_static_flux
    else:
        assert mean_tracked_flux > 100.0


def test_band_stacking_improves_snr(mock_source, test_region):
    """Band stacking co-adds images to measurably improve S/N (measured empirical gain)."""
    stars = mock_source._synthesize_stars(test_region)
    star = stars[0]

    gain_result = compare_snr_gain(
        source=mock_source,
        region=test_region,
        ra=star["ra"],
        dec=star["dec"],
        fov_deg=0.2,
    )

    assert gain_result["single_snr"] > 0.0
    assert gain_result["stacked_snr"] > gain_result["single_snr"]
    # For 4 stacked images, theoretical sqrt(4) = 2.0; empirically gain should be > 1.3
    assert gain_result["snr_gain"] >= 1.25


def test_too_few_measurements_returns_none():
    """Fewer measurements than min_valid_measurements threshold returns None."""
    p1 = PhotometryMeasurement(
        epoch_id="ep1",
        date="2026-01-01T00:00:00Z",
        ra=60.0,
        dec=20.0,
        pixel_x=10.0,
        pixel_y=10.0,
        flux=100.0,
        flux_err=2.0,
        wavelength_um=1.00,
        quality_flag=0,
        background=10.0,
        background_rms=1.0,
    )
    # Require 2 measurements minimum
    spec = build_spectrum([p1], min_valid_measurements=2)
    assert spec is None


def test_schema_conformance_and_equal_lengths(mock_source, test_region):
    """Spectrum output conforms to Schema 1.0 with equal wavelength, flux, and error array lengths."""
    epochs = mock_source.list_epochs(test_region)
    stars = mock_source._synthesize_stars(test_region)
    star = stars[0]

    spec = get_spectrum(
        ra=star["ra"],
        dec=star["dec"],
        source=mock_source,
        region=test_region,
    )

    assert spec is not None
    wl = spec["wavelength_um"]
    flux = spec["flux"]
    err = spec["flux_err"]

    assert len(wl) == len(flux) == len(err)
    assert len(wl) >= 1

    # Validate against Schema 1.0 contract
    catalog = {
        "schema_version": "1.0",
        "region": {"name": "test", "ra_center": 60.0, "dec_center": 20.0, "radius_deg": 0.2},
        "epochs": [{"epoch_id": ep.epoch_id, "date": ep.date.isoformat(), "band_count": 102} for ep in epochs],
        "movers": [
            {
                "object_id": "mov_spec_test",
                "ra": 60.0,
                "dec": 20.0,
                "type": "known",
                "match_name": "(433) Eros",
                "confidence": 0.95,
                "is_synthetic": True,
                "motion": {"ra_rate_arcsec_per_day": 10.0, "dec_rate_arcsec_per_day": 5.0},
                "detections": [
                    {
                        "epoch_id": epochs[0].epoch_id,
                        "date": epochs[0].date.isoformat(),
                        "ra": 60.0,
                        "dec": 20.0,
                        "flux": 100.0,
                        "cutout_url": "cutouts/test.png",
                    }
                ],
                "spectrum": spec,
            }
        ],
    }

    validate_dict(catalog)


def test_crosscheck_with_reference_csv(tmp_path):
    """Test IRSA spectrophotometry cross-check comparison and diagnostic plot."""
    csv_file = tmp_path / "mock_irsa.csv"
    generate_mock_reference_csv(csv_file)

    our_spectrum = {
        "wavelength_um": [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0],
        "flux": [510.0, 530.0, 560.0, 590.0, 630.0, 680.0, 720.0],
        "flux_err": [10.0, 12.0, 14.0, 15.0, 18.0, 20.0, 22.0],
    }

    plot_file = tmp_path / "crosscheck.png"
    result = compare_to_reference(our_spectrum, csv_file, output_plot_path=plot_file)

    assert 0.85 <= result["median_ratio"] <= 1.25
    assert result["relative_scatter"] < 0.25
    assert plot_file.exists()
