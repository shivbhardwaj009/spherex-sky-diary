"""Tests for Module 4: Catalog Matching & Validation.

All tests mock external network interfaces (astroquery) to ensure hermetic,
offline test execution.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest
from astropy.table import Table

from docs.validate import validate_dict
from matching.match import match_candidates
from matching.predict import predict_positions
from matching.query import KnownObject, PredictedPosition, query_known_objects
from matching.validate_matches import evaluate_catalog_matching

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def sample_epochs():
    return [
        {"epoch_id": "epoch_01", "date": "2026-01-10T00:00:00+00:00"},
        {"epoch_id": "epoch_02", "date": "2026-01-15T00:00:00+00:00"},
        {"epoch_id": "epoch_03", "date": "2026-01-20T00:00:00+00:00"},
    ]


@pytest.fixture
def mock_known_eros():
    """Known asteroid (433) Eros moving at (15 arcsec/day, 5 arcsec/day)."""
    # Over 5 days:
    # d_ra = 15 * 5 / 3600 = 0.020833 deg / cos(20) ~ 0.022170 deg
    # d_dec = 5 * 5 / 3600 = 0.006944 deg
    return KnownObject(
        name="(433) Eros",
        designation="(433) Eros",
        object_type="asteroid",
        magnitude=14.2,
        positions=[
            PredictedPosition(
                epoch_id="epoch_01",
                date="2026-01-10T00:00:00+00:00",
                ra=60.0000,
                dec=20.0000,
                ra_rate_arcsec_per_day=15.0,
                dec_rate_arcsec_per_day=5.0,
                v_mag=14.2,
            ),
            PredictedPosition(
                epoch_id="epoch_02",
                date="2026-01-15T00:00:00+00:00",
                ra=60.0222,
                dec=20.0069,
                ra_rate_arcsec_per_day=15.0,
                dec_rate_arcsec_per_day=5.0,
                v_mag=14.2,
            ),
            PredictedPosition(
                epoch_id="epoch_03",
                date="2026-01-20T00:00:00+00:00",
                ra=60.0443,
                dec=20.0139,
                ra_rate_arcsec_per_day=15.0,
                dec_rate_arcsec_per_day=5.0,
                v_mag=14.2,
            ),
        ],
        mean_ra_rate=15.0,
        mean_dec_rate=5.0,
    )


def test_perfect_match_becomes_known(mock_known_eros, sample_epochs):
    """Candidate on exact predicted trajectory becomes 'known' with correct name."""
    candidate = {
        "object_id": "mov_001",
        "ra": 60.0000,
        "dec": 20.0000,
        "type": "unknown",
        "match_name": None,
        "confidence": 0.82,
        "is_synthetic": True,
        "motion": {
            "ra_rate_arcsec_per_day": 15.0,
            "dec_rate_arcsec_per_day": 5.0,
        },
        "detections": [
            {
                "epoch_id": "epoch_01",
                "date": "2026-01-10T00:00:00+00:00",
                "ra": 60.0000,
                "dec": 20.0000,
                "flux": 120.0,
                "cutout_url": "cutouts/mov_001_epoch_01.png",
            },
            {
                "epoch_id": "epoch_02",
                "date": "2026-01-15T00:00:00+00:00",
                "ra": 60.0222,
                "dec": 20.0069,
                "flux": 122.0,
                "cutout_url": "cutouts/mov_001_epoch_02.png",
            },
            {
                "epoch_id": "epoch_03",
                "date": "2026-01-20T00:00:00+00:00",
                "ra": 60.0443,
                "dec": 20.0139,
                "flux": 118.0,
                "cutout_url": "cutouts/mov_001_epoch_03.png",
            },
        ],
        "spectrum": None,
    }

    matched = match_candidates([candidate], [mock_known_eros])
    res = matched[0]

    assert res["type"] == "known"
    assert res["match_name"] == "(433) Eros"
    assert res["match_distance_arcsec"] < 1.0
    assert res["matched_epoch_count"] == 3
    assert res["confidence"] >= 0.90


def test_position_offset_beyond_tolerance_stays_unknown(mock_known_eros):
    """Candidate with position offset beyond tolerance remains 'unknown'."""
    # Offset by 30 arcseconds (0.0083 deg)
    candidate = {
        "object_id": "mov_002",
        "ra": 60.0083,
        "dec": 20.0083,
        "type": "unknown",
        "match_name": None,
        "confidence": 0.75,
        "is_synthetic": True,
        "motion": {"ra_rate_arcsec_per_day": 15.0, "dec_rate_arcsec_per_day": 5.0},
        "detections": [
            {
                "epoch_id": "epoch_01",
                "date": "2026-01-10T00:00:00+00:00",
                "ra": 60.0083,
                "dec": 20.0083,
                "flux": 80.0,
                "cutout_url": "cutouts/mov_002_epoch_01.png",
            },
            {
                "epoch_id": "epoch_02",
                "date": "2026-01-15T00:00:00+00:00",
                "ra": 60.0305,
                "dec": 20.0152,
                "flux": 85.0,
                "cutout_url": "cutouts/mov_002_epoch_02.png",
            },
        ],
        "spectrum": None,
    }

    matched = match_candidates([candidate], [mock_known_eros])
    assert matched[0]["type"] == "unknown"
    assert matched[0]["match_name"] is None


def test_right_position_wrong_motion_stays_unknown(mock_known_eros):
    """Candidate overlapping at epoch 1 but moving in opposite direction stays unknown."""
    candidate = {
        "object_id": "mov_003",
        "ra": 60.0000,
        "dec": 20.0000,
        "type": "unknown",
        "match_name": None,
        "confidence": 0.70,
        "is_synthetic": True,
        "motion": {"ra_rate_arcsec_per_day": -15.0, "dec_rate_arcsec_per_day": -5.0},
        "detections": [
            {
                "epoch_id": "epoch_01",
                "date": "2026-01-10T00:00:00+00:00",
                "ra": 60.0000,
                "dec": 20.0000,
                "flux": 70.0,
                "cutout_url": "cutouts/mov_003_epoch_01.png",
            },
            {
                "epoch_id": "epoch_02",
                "date": "2026-01-15T00:00:00+00:00",
                "ra": 59.9778,
                "dec": 19.9931,
                "flux": 72.0,
                "cutout_url": "cutouts/mov_003_epoch_02.png",
            },
        ],
        "spectrum": None,
    }

    matched = match_candidates([candidate], [mock_known_eros])
    assert matched[0]["type"] == "unknown"
    assert matched[0]["match_name"] is None


def test_ambiguity_picks_closest_and_records_runner_up():
    """When two known objects are close, candidate matches the closest and records runner-up."""
    obj_close = KnownObject(
        name="(1) Ceres",
        designation="(1) Ceres",
        object_type="asteroid",
        magnitude=9.0,
        positions=[
            PredictedPosition(
                epoch_id="epoch_01",
                date="2026-01-10T00:00:00+00:00",
                ra=60.0002,  # ~0.7 arcsec offset
                dec=20.0000,
                ra_rate_arcsec_per_day=10.0,
                dec_rate_arcsec_per_day=0.0,
            ),
            PredictedPosition(
                epoch_id="epoch_02",
                date="2026-01-15T00:00:00+00:00",
                ra=60.0150,
                dec=20.0000,
                ra_rate_arcsec_per_day=10.0,
                dec_rate_arcsec_per_day=0.0,
            ),
        ],
        mean_ra_rate=10.0,
        mean_dec_rate=0.0,
    )

    obj_further = KnownObject(
        name="(4) Vesta",
        designation="(4) Vesta",
        object_type="asteroid",
        magnitude=8.5,
        positions=[
            PredictedPosition(
                epoch_id="epoch_01",
                date="2026-01-10T00:00:00+00:00",
                ra=60.0010,  # ~3.4 arcsec offset
                dec=20.0000,
                ra_rate_arcsec_per_day=10.0,
                dec_rate_arcsec_per_day=0.0,
            ),
            PredictedPosition(
                epoch_id="epoch_02",
                date="2026-01-15T00:00:00+00:00",
                ra=60.0158,
                dec=20.0000,
                ra_rate_arcsec_per_day=10.0,
                dec_rate_arcsec_per_day=0.0,
            ),
        ],
        mean_ra_rate=10.0,
        mean_dec_rate=0.0,
    )

    candidate = {
        "object_id": "mov_ambig",
        "ra": 60.0000,
        "dec": 20.0000,
        "type": "unknown",
        "match_name": None,
        "confidence": 0.85,
        "is_synthetic": True,
        "motion": {"ra_rate_arcsec_per_day": 10.0, "dec_rate_arcsec_per_day": 0.0},
        "detections": [
            {
                "epoch_id": "epoch_01",
                "date": "2026-01-10T00:00:00+00:00",
                "ra": 60.0000,
                "dec": 20.0000,
                "flux": 150.0,
                "cutout_url": "cutouts/mov_ambig_epoch_01.png",
            },
            {
                "epoch_id": "epoch_02",
                "date": "2026-01-15T00:00:00+00:00",
                "ra": 60.0148,
                "dec": 20.0000,
                "flux": 150.0,
                "cutout_url": "cutouts/mov_ambig_epoch_02.png",
            },
        ],
        "spectrum": None,
    }

    matched = match_candidates([candidate], [obj_further, obj_close])
    res = matched[0]
    assert res["type"] == "known"
    assert res["match_name"] == "(1) Ceres"
    assert res["runner_up_match"] == "(4) Vesta"


def test_ra_wraparound_near_zero_boundary():
    """Correctly matches tracks traversing RA wraparound across 360/0 degrees."""
    obj_wrap = KnownObject(
        name="2024 BX1",
        designation="2024 BX1",
        object_type="asteroid",
        magnitude=16.0,
        positions=[
            PredictedPosition(
                epoch_id="epoch_01",
                date="2026-01-10T00:00:00+00:00",
                ra=359.9950,
                dec=5.0000,
                ra_rate_arcsec_per_day=30.0,
                dec_rate_arcsec_per_day=0.0,
            ),
            PredictedPosition(
                epoch_id="epoch_02",
                date="2026-01-12T00:00:00+00:00",
                ra=0.0117,
                dec=5.0000,
                ra_rate_arcsec_per_day=30.0,
                dec_rate_arcsec_per_day=0.0,
            ),
        ],
        mean_ra_rate=30.0,
        mean_dec_rate=0.0,
    )

    candidate = {
        "object_id": "mov_wrap",
        "ra": 359.9950,
        "dec": 5.0000,
        "type": "unknown",
        "match_name": None,
        "confidence": 0.88,
        "is_synthetic": True,
        "motion": {"ra_rate_arcsec_per_day": 30.0, "dec_rate_arcsec_per_day": 0.0},
        "detections": [
            {
                "epoch_id": "epoch_01",
                "date": "2026-01-10T00:00:00+00:00",
                "ra": 359.9950,
                "dec": 5.0000,
                "flux": 95.0,
                "cutout_url": "cutouts/mov_wrap_epoch_01.png",
            },
            {
                "epoch_id": "epoch_02",
                "date": "2026-01-12T00:00:00+00:00",
                "ra": 0.0117,
                "dec": 5.0000,
                "flux": 95.0,
                "cutout_url": "cutouts/mov_wrap_epoch_02.png",
            },
        ],
        "spectrum": None,
    }

    matched = match_candidates([candidate], [obj_wrap])
    assert matched[0]["type"] == "known"
    assert matched[0]["match_name"] == "2024 BX1"
    assert matched[0]["match_distance_arcsec"] < 1.0


def test_query_caching(monkeypatch, tmp_path, sample_epochs):
    """Subsequent identical queries hit the disk cache without querying SkyBoT."""
    mock_table = Table(
        {
            "Name": ["Eros"],
            "Number": [433],
            "Type": ["Asteroid"],
            "RA": [60.0],
            "DEC": [20.0],
            "RA_rate": [0.5],
            "DEC_rate": [0.2],
            "V": [14.0],
        }
    )

    query_count = 0

    def mock_cone_search(*args, **kwargs):
        nonlocal query_count
        query_count += 1
        return mock_table

    monkeypatch.setattr("astroquery.imcce.Skybot.cone_search", mock_cone_search)

    cfg = {
        "cache": {"cache_dir": str(tmp_path)},
        "service": {"timeout_sec": 5, "max_retries": 1},
        "matching": {"max_search_rate_arcsec_per_day": 50.0},
    }

    # First query -> executes mocked network call
    objs_1, src_1 = query_known_objects(
        ra=60.0, dec=20.0, radius_deg=0.2, epochs=sample_epochs, offline=False, config=cfg
    )
    assert src_1 == "skybot"
    assert query_count == len(sample_epochs)

    # Second identical query -> loads from disk cache, zero additional network calls
    objs_2, src_2 = query_known_objects(
        ra=60.0, dec=20.0, radius_deg=0.2, epochs=sample_epochs, offline=False, config=cfg
    )
    assert src_2 == "cache"
    assert query_count == len(sample_epochs)
    assert len(objs_2) == len(objs_1)


def test_network_failure_triggers_offline_fallback(monkeypatch, tmp_path, sample_epochs):
    """Network connection failure seamlessly falls back to offline catalog."""
    def failing_cone_search(*args, **kwargs):
        raise ConnectionError("Simulated network outage")

    monkeypatch.setattr("astroquery.imcce.Skybot.cone_search", failing_cone_search)

    # Create dummy offline catalog
    offline_file = tmp_path / "offline_fallback.json"
    dummy_offline = [
        KnownObject(
            name="(101955) Bennu",
            designation="(101955) Bennu",
            object_type="asteroid",
            magnitude=20.0,
            positions=[],
        ).to_dict()
    ]
    with open(offline_file, "w", encoding="utf-8") as f:
        json.dump(dummy_offline, f)

    cfg = {
        "cache": {
            "cache_dir": str(tmp_path / "cache"),
            "offline_catalog_path": str(offline_file),
        },
        "service": {"timeout_sec": 1, "max_retries": 1, "backoff_factor": 0.01},
    }

    objs, src = query_known_objects(
        ra=70.0, dec=25.0, radius_deg=0.2, epochs=sample_epochs, offline=False, config=cfg
    )

    assert src == "offline_catalog"
    assert len(objs) == 1
    assert objs[0].name == "(101955) Bennu"


def test_validation_report_metrics(mock_known_eros):
    """Validation report computes recovered vs missed numbers accurately."""
    catalog = {
        "schema_version": "1.0",
        "region": {"name": "test_patch", "ra_center": 60.0, "dec_center": 20.0, "radius_deg": 0.2},
        "epochs": [{"epoch_id": "ep1", "date": "2026-01-10T00:00:00Z", "band_count": 102}],
        "movers": [
            {
                "object_id": "mov_rec",
                "ra": 60.0,
                "dec": 20.0,
                "type": "known",
                "match_name": "(433) Eros",
                "match_distance_arcsec": 0.45,
                "confidence": 0.95,
                "is_synthetic": True,
                "motion": {"ra_rate_arcsec_per_day": 15.0, "dec_rate_arcsec_per_day": 5.0},
                "detections": [{"epoch_id": "ep1", "date": "2026-01-10T00:00:00Z", "ra": 60.0, "dec": 20.0, "flux": 100.0, "cutout_url": "cutouts/test.png"}],
                "spectrum": None,
            },
            {
                "object_id": "mov_unk",
                "ra": 60.1,
                "dec": 20.1,
                "type": "unknown",
                "match_name": None,
                "confidence": 0.72,
                "is_synthetic": True,
                "motion": {"ra_rate_arcsec_per_day": -5.0, "dec_rate_arcsec_per_day": 8.0},
                "detections": [{"epoch_id": "ep1", "date": "2026-01-10T00:00:00Z", "ra": 60.1, "dec": 20.1, "flux": 50.0, "cutout_url": "cutouts/test2.png"}],
                "spectrum": None,
            },
        ],
    }

    # 2 known objects: Eros (recovered) and Ceres (missed)
    ceres = KnownObject(
        name="(1) Ceres",
        designation="(1) Ceres",
        object_type="asteroid",
        magnitude=19.5,
        positions=[],
        mean_ra_rate=20.0,
        mean_dec_rate=10.0,
    )

    report = evaluate_catalog_matching(catalog, [mock_known_eros, ceres])
    summary = report["summary"]

    assert summary["total_candidates"] == 2
    assert summary["labeled_known_count"] == 1
    assert summary["labeled_unknown_count"] == 1
    assert summary["total_known_in_field"] == 2
    assert summary["recovered_known_count"] == 1
    assert summary["missed_known_count"] == 1
    assert summary["known_recovery_recall"] == 0.50
    assert summary["mean_match_distance_arcsec"] == 0.45
    assert report["missed_objects"][0]["probable_cause"] == "faint_magnitude_below_snr_threshold"


def test_schema_conformance_with_matching_fields(mock_known_eros):
    """Matched candidate catalog with optional fields conforms to schema 1.0."""
    catalog = {
        "schema_version": "1.0",
        "data_version": "v1.0-matched",
        "generated_at": "2026-01-15T12:00:00Z",
        "fov_deg": 0.2,
        "metadata": {
            "matching_source": "offline_catalog",
            "matched_at": "2026-01-15T12:05:00Z",
        },
        "region": {
            "name": "ecliptic_plane_test",
            "ra_center": 60.0,
            "dec_center": 20.0,
            "radius_deg": 0.2,
        },
        "epochs": [
            {"epoch_id": "epoch_01", "date": "2026-01-10T00:00:00Z", "band_count": 102},
            {"epoch_id": "epoch_02", "date": "2026-01-15T00:00:00Z", "band_count": 102},
        ],
        "movers": [
            {
                "object_id": "mov_001",
                "ra": 60.0,
                "dec": 20.0,
                "type": "known",
                "match_name": "(433) Eros",
                "match_distance_arcsec": 0.42,
                "matched_epoch_count": 2,
                "runner_up_match": "(4) Vesta",
                "confidence": 0.96,
                "is_synthetic": True,
                "motion": {"ra_rate_arcsec_per_day": 15.0, "dec_rate_arcsec_per_day": 5.0},
                "detections": [
                    {
                        "epoch_id": "epoch_01",
                        "date": "2026-01-10T00:00:00Z",
                        "ra": 60.0,
                        "dec": 20.0,
                        "flux": 120.0,
                        "cutout_url": "cutouts/mov_001_epoch_01.png",
                    },
                    {
                        "epoch_id": "epoch_02",
                        "date": "2026-01-15T00:00:00Z",
                        "ra": 60.0222,
                        "dec": 20.0069,
                        "flux": 122.0,
                        "cutout_url": "cutouts/mov_001_epoch_02.png",
                    },
                ],
                "spectrum": None,
            }
        ],
    }

    # Should validate without any exceptions
    validate_dict(catalog)

