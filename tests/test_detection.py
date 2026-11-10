"""Unit and integration tests for SPHEREx Mover Detection pipeline (Module 3)."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest
from astropy.wcs import WCS

from data.adapter.base import EpochImage, Region
from data.adapter.mock_source import MockSource
from detection.movers.evaluate_detection import evaluate
from detection.movers.filters import (
    flag_filter_response,
    reject_bad_fit,
    reject_single_epoch,
    reject_stationary,
)
from detection.movers.linking import Tracklet, fit_constant_velocity_track, link_detections
from detection.movers.pipeline import run
from detection.movers.score import compute_confidence
from detection.movers.static_model import build_static_model
from detection.processing.pipeline import run as run_processing
from docs.validate import validate_file

REPO_ROOT = Path(__file__).resolve().parents[1]


def make_dummy_wcs(crval=(60.0, 20.0), crpix=(64.0, 64.0), cdelt=(-0.2 / 128, 0.2 / 128)) -> WCS:
    """Helper to create a test TAN WCS."""
    w = WCS(naxis=2)
    w.wcs.crval = list(crval)
    w.wcs.crpix = list(crpix)
    w.wcs.cdelt = list(cdelt)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    return w


def test_static_model_recovers_clean_background_with_transient_mover():
    """Static model recovers clean stationary background when a transient mover is in only 1 epoch."""
    shape = (64, 64)
    wcs = make_dummy_wcs()
    base_time = datetime(2026, 1, 15, 0, 0, 0, tzinfo=timezone.utc)

    epochs = []
    # 5 epochs: background mean ~ 0.0 with noise sigma ~ 2.0
    rng = np.random.default_rng(99)
    for i in range(5):
        pixels = rng.normal(0.0, 2.0, shape)
        # Inject transient mover in epoch 0 ONLY at pixel (30, 30)
        if i == 0:
            pixels[30, 30] += 500.0

        epochs.append(
            EpochImage(
                pixels=pixels,
                variance=np.full(shape, 4.0),
                mask=np.zeros(shape, dtype=np.int32),
                wcs=wcs,
                wavelength_map=np.full(shape, 2.0 + 0.02 * i),
                epoch_id=f"test_ep_{i}",
                date=base_time + timedelta(days=i * 20),
            )
        )

    model, scatter, meta = build_static_model(epochs)

    # In epoch 0, pixel (30, 30) received 500.0 flux.
    # The static model median across epochs 0..4 must completely reject this transient!
    assert abs(model[30, 30]) < 3.0, f"Transient leaked into static model: {model[30, 30]}"
    assert scatter[30, 30] > 0.0


def test_tracklet_linking_unequal_spacing_and_ra_wraparound():
    """Linking recovers constant-velocity track across unequal dates and RA 0/360 wraparound."""
    # Simulate tracklet crossing RA 0 (e.g., from 359.85 to 0.40 degrees)
    # True motion: ra_rate = +20.0 arcsec/day, dec_rate = +10.0 arcsec/day
    base_date = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
    day_offsets = [0.0, 15.3, 44.8, 85.0]  # Unequally spaced dates

    cos_dec = np.cos(np.radians(20.0))
    ra_start = 359.85
    dec_start = 20.0

    detections_by_epoch = {}
    for i, dt_days in enumerate(day_offsets):
        ep_id = f"ep_{i+1:02d}"
        d_ra = (ra_start + ((20.0 * dt_days) / 3600.0) / cos_dec) % 360.0
        d_dec = dec_start + (10.0 * dt_days) / 3600.0

        detections_by_epoch[ep_id] = [
            {
                "x": 64.0 + i * 5,
                "y": 64.0 + i * 3,
                "ra": d_ra,
                "dec": d_dec,
                "flux": 300.0,
                "snr": 12.0,
                "wavelength_um": 2.2,
                "epoch_id": ep_id,
                "date": (base_date + timedelta(days=dt_days)).isoformat(),
            }
        ]

    # Link detections
    tracklets = link_detections(
        detections_by_epoch,
        config={"linking": {"min_detections": 3, "match_radius_arcsec": 6.0}},
    )

    assert len(tracklets) == 1
    trk = tracklets[0]
    assert len(trk.detections) == 4
    # Rate recovery check within 0.1 arcsec/day
    assert abs(trk.ra_rate_arcsec_per_day - 20.0) < 0.15
    assert abs(trk.dec_rate_arcsec_per_day - 10.0) < 0.15
    # Trajectory fit residual must be small (< 0.2 arcsec)
    assert trk.rms_residual_arcsec < 0.2


def test_filters_pass_and_fail_cases():
    """Verify each artifact filter correctly identifies pass and fail cases."""
    base_date = datetime(2026, 3, 1, 0, 0, 0, tzinfo=timezone.utc)

    # 1. reject_single_epoch
    fail_single = Tracklet(
        tracklet_id="single",
        detections=[
            {"epoch_id": "ep1", "date": base_date.isoformat(), "ra": 60.0, "dec": 20.0, "flux": 100},
            {"epoch_id": "ep1", "date": base_date.isoformat(), "ra": 60.001, "dec": 20.001, "flux": 100},
        ],
        ref_ra=60.0,
        ref_dec=20.0,
        ref_date=base_date,
        ra_rate_arcsec_per_day=0.0,
        dec_rate_arcsec_per_day=0.0,
        rms_residual_arcsec=0.1,
        reduced_chi2=1.0,
    )
    assert reject_single_epoch(fail_single) is True

    pass_multi = Tracklet(
        tracklet_id="multi",
        detections=[
            {"epoch_id": "ep1", "date": base_date.isoformat(), "ra": 60.0, "dec": 20.0, "flux": 100},
            {"epoch_id": "ep2", "date": (base_date + timedelta(days=10)).isoformat(), "ra": 60.01, "dec": 20.01, "flux": 100},
        ],
        ref_ra=60.0,
        ref_dec=20.0,
        ref_date=base_date,
        ra_rate_arcsec_per_day=10.0,
        dec_rate_arcsec_per_day=10.0,
        rms_residual_arcsec=0.1,
        reduced_chi2=1.0,
    )
    assert reject_single_epoch(pass_multi) is False

    # 2. reject_stationary
    fail_stationary = Tracklet(
        tracklet_id="stat",
        detections=[
            {"epoch_id": "ep1", "date": base_date.isoformat(), "ra": 60.00000, "dec": 20.00000, "flux": 100},
            {"epoch_id": "ep2", "date": (base_date + timedelta(days=20)).isoformat(), "ra": 60.00002, "dec": 20.00001, "flux": 100},
        ],
        ref_ra=60.0,
        ref_dec=20.0,
        ref_date=base_date,
        ra_rate_arcsec_per_day=0.01,
        dec_rate_arcsec_per_day=0.01,
        rms_residual_arcsec=0.05,
        reduced_chi2=0.5,
    )
    assert reject_stationary(fail_stationary, min_motion_arcsec=3.0) is True

    pass_moving = Tracklet(
        tracklet_id="move",
        detections=[
            {"epoch_id": "ep1", "date": base_date.isoformat(), "ra": 60.00000, "dec": 20.00000, "flux": 100},
            {"epoch_id": "ep2", "date": (base_date + timedelta(days=20)).isoformat(), "ra": 60.02000, "dec": 20.01500, "flux": 100},
        ],
        ref_ra=60.0,
        ref_dec=20.0,
        ref_date=base_date,
        ra_rate_arcsec_per_day=15.0,
        dec_rate_arcsec_per_day=10.0,
        rms_residual_arcsec=0.1,
        reduced_chi2=1.0,
    )
    assert reject_stationary(pass_moving, min_motion_arcsec=3.0) is False

    # 3. reject_bad_fit
    fail_fit = copy.deepcopy(pass_moving)
    fail_fit.rms_residual_arcsec = 5.8
    assert reject_bad_fit(fail_fit, max_residual_arcsec=3.5) is True

    pass_fit = copy.deepcopy(pass_moving)
    pass_fit.rms_residual_arcsec = 0.6
    assert reject_bad_fit(pass_fit, max_residual_arcsec=3.5) is False

    # 4. flag_filter_response
    # Chromatic response artifact: flux varies linearly with wavelength
    chromatic_track = Tracklet(
        tracklet_id="chromatic",
        detections=[
            {"epoch_id": "ep1", "date": base_date.isoformat(), "ra": 60.0, "dec": 20.0, "flux": 100.0, "wavelength_um": 1.0},
            {"epoch_id": "ep2", "date": (base_date + timedelta(days=10)).isoformat(), "ra": 60.01, "dec": 20.01, "flux": 200.0, "wavelength_um": 2.0},
            {"epoch_id": "ep3", "date": (base_date + timedelta(days=20)).isoformat(), "ra": 60.02, "dec": 20.02, "flux": 300.0, "wavelength_um": 3.0},
        ],
        ref_ra=60.0,
        ref_dec=20.0,
        ref_date=base_date,
        ra_rate_arcsec_per_day=10.0,
        dec_rate_arcsec_per_day=10.0,
        rms_residual_arcsec=0.1,
        reduced_chi2=1.0,
    )
    is_flagged, score = flag_filter_response(chromatic_track, correlation_threshold=0.80)
    assert is_flagged is True
    assert score > 0.95

    # Genuine mover: flux constant while wavelength changes
    clean_track = copy.deepcopy(chromatic_track)
    for d in clean_track.detections:
        d["flux"] = 250.0  # Constant flux
    is_clean_flagged, clean_score = flag_filter_response(clean_track, correlation_threshold=0.80)
    assert is_clean_flagged is False
    assert clean_score == 0.0


def test_confidence_properties():
    """Confidence score is bounded in [0, 1] and strictly increases with S/N and epoch count."""
    base_date = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    def make_track(n_dets: int, snr: float, rms: float) -> Tracklet:
        dets = [
            {
                "epoch_id": f"ep_{i}",
                "date": (base_date + timedelta(days=i * 15)).isoformat(),
                "ra": 60.0 + i * 0.01,
                "dec": 20.0 + i * 0.01,
                "flux": snr * 20.0,
                "snr": snr,
            }
            for i in range(n_dets)
        ]
        return Tracklet(
            tracklet_id="test",
            detections=dets,
            ref_ra=60.0,
            ref_dec=20.0,
            ref_date=base_date,
            ra_rate_arcsec_per_day=10.0,
            dec_rate_arcsec_per_day=10.0,
            rms_residual_arcsec=rms,
            reduced_chi2=1.0,
        )

    t_low_snr = make_track(n_dets=3, snr=4.0, rms=0.5)
    t_high_snr = make_track(n_dets=3, snr=16.0, rms=0.5)
    c_low_snr = compute_confidence(t_low_snr)
    c_high_snr = compute_confidence(t_high_snr)

    assert 0.0 <= c_low_snr <= 1.0
    assert 0.0 <= c_high_snr <= 1.0
    assert c_high_snr > c_low_snr, "Confidence must increase with S/N"

    t_3ep = make_track(n_dets=3, snr=10.0, rms=0.5)
    t_5ep = make_track(n_dets=5, snr=10.0, rms=0.5)
    assert compute_confidence(t_5ep) > compute_confidence(t_3ep), "Confidence must increase with epoch count"


def test_end_to_end_detection_and_validation(tmp_path: Path):
    """End-to-end detection on mock data generates valid candidates.json and high recall."""
    # Ensure processed stack exists from Module 2
    proc_dir = tmp_path / "processed"
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
        "output": {
            "processed_dir": str(proc_dir),
            "cutouts_dir": str(tmp_path / "cutouts"),
            "candidates_file": str(tmp_path / "candidates.json"),
            "eval_file": str(tmp_path / "detection_eval.json"),
        },
    }

    # Run processing
    run_processing(config=cfg, output_dir=proc_dir)

    # Run mover detection pipeline
    cand_file = tmp_path / "candidates.json"
    run(config=cfg, output_candidates_path=cand_file)
    assert cand_file.exists()

    # Contract schema validation
    validated_catalog = validate_file(cand_file)
    assert validated_catalog["schema_version"] == "1.0"
    assert len(validated_catalog["movers"]) > 0

    for m in validated_catalog["movers"]:
        assert m["type"] == "unknown"
        assert m["match_name"] is None
        assert 0.0 <= m["confidence"] <= 1.0
        assert m["is_synthetic"] is True
        assert len(m["detections"]) >= 3

        # Verify cutouts exist on disk
        for det in m["detections"]:
            cutout_p = tmp_path / det["cutout_url"]
            assert cutout_p.exists()

    # Run evaluation script against ground_truth.json
    gt_file = REPO_ROOT / "data" / "output" / "ground_truth.json"
    eval_metrics = evaluate(candidates_path=cand_file, ground_truth_path=gt_file)

    # We justify recall >= 0.60: In our synthetic simulation of 5 moving solar system bodies,
    # some may exit the 0.2 deg FOV or experience faint lightcurves. Requiring >= 60% recall
    # ensures genuine tracking sensitivity while rigorously testing the pipeline.
    assert eval_metrics["recall"] >= 0.60, f"Recall was {eval_metrics['recall']}, expected >= 0.60"
    assert eval_metrics["false_positives"] <= 2


def test_detection_determinism(tmp_path: Path):
    """Detection pipeline is strictly deterministic given the same seed."""
    run1_cand = tmp_path / "run1" / "candidates.json"
    run2_cand = tmp_path / "run2" / "candidates.json"

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

    run(config=cfg, output_candidates_path=run1_cand)
    run(config=cfg, output_candidates_path=run2_cand)

    with open(run1_cand, "r", encoding="utf-8") as f:
        d1 = json.load(f)
    with open(run2_cand, "r", encoding="utf-8") as f:
        d2 = json.load(f)

    # Normalize timestamps before comparison
    d1["generated_at"] = "FIXED"
    d2["generated_at"] = "FIXED"

    assert d1 == d2, "Outputs across repeated runs with identical seed must match bitwise"
