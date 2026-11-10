"""Unit and contract validation tests for SPHEREx Sky Diary (Module 0)."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data.mock.generate_mock import generate_mock_catalog
from docs.validate import (
    ContractValidationError,
    load_schema,
    validate_dict,
    validate_file,
)


@pytest.fixture(scope="session")
def candidates_path():
    """Ensure mock candidates catalog is generated."""
    path = REPO_ROOT / "data" / "output" / "candidates.json"
    if not path.exists():
        generate_mock_catalog()
    return path


@pytest.fixture
def valid_candidate_data(candidates_path):
    """Load valid candidates data dict for mutation testing."""
    with open(candidates_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_mock_output_validates(candidates_path):
    """Ensure candidate.json passes all contract schema and domain invariant checks."""
    data = validate_file(candidates_path)
    assert data["schema_version"] == "1.0"
    assert len(data["movers"]) == 25
    assert len(data["epochs"]) >= 3

    # Check known vs unknown ratio
    known_count = sum(1 for m in data["movers"] if m["type"] == "known")
    unknown_count = sum(1 for m in data["movers"] if m["type"] == "unknown")
    assert known_count == 15
    assert unknown_count == 10

    # Verify detection counts and cutout existence
    for mover in data["movers"]:
        assert 3 <= len(mover["detections"]) <= 6
        for det in mover["detections"]:
            cutout_rel = det["cutout_url"]
            cutout_full = REPO_ROOT / "data" / "output" / cutout_rel
            assert cutout_full.exists(), f"Cutout file missing: {cutout_full}"


def test_all_mock_movers_have_is_synthetic_true(valid_candidate_data):
    """All synthetic records must have is_synthetic: true (Rule #2)."""
    assert len(valid_candidate_data["movers"]) > 0
    for mover in valid_candidate_data["movers"]:
        assert mover.get("is_synthetic") is True, f"Mover {mover['object_id']} missing is_synthetic: true"


def test_reject_missing_required_field(valid_candidate_data):
    """Removing top-level or mover-level required fields must fail validation."""
    # Missing top-level schema_version
    data_missing_version = copy.deepcopy(valid_candidate_data)
    del data_missing_version["schema_version"]
    with pytest.raises(ContractValidationError):
        validate_dict(data_missing_version)

    # Missing mover field 'motion'
    data_missing_motion = copy.deepcopy(valid_candidate_data)
    del data_missing_motion["movers"][0]["motion"]
    with pytest.raises(ContractValidationError):
        validate_dict(data_missing_motion)


def test_reject_confidence_out_of_bounds(valid_candidate_data):
    """Confidence score must be strictly in [0.0, 1.0]."""
    # > 1.0
    bad_data = copy.deepcopy(valid_candidate_data)
    bad_data["movers"][0]["confidence"] = 1.5
    with pytest.raises(ContractValidationError):
        validate_dict(bad_data)

    # < 0.0
    bad_data_neg = copy.deepcopy(valid_candidate_data)
    bad_data_neg["movers"][0]["confidence"] = -0.2
    with pytest.raises(ContractValidationError):
        validate_dict(bad_data_neg)


def test_reject_invalid_type(valid_candidate_data):
    """Type must be enum ['known', 'unknown']. 'maybe' must be rejected."""
    bad_data = copy.deepcopy(valid_candidate_data)
    bad_data["movers"][0]["type"] = "maybe"
    with pytest.raises(ContractValidationError):
        validate_dict(bad_data)


def test_reject_ra_out_of_bounds(valid_candidate_data):
    """RA must be within 0.0 to 360.0."""
    # Top mover RA = 400
    bad_data = copy.deepcopy(valid_candidate_data)
    bad_data["movers"][0]["ra"] = 400.0
    with pytest.raises(ContractValidationError):
        validate_dict(bad_data)

    # Detection RA = -5.0
    bad_data_det = copy.deepcopy(valid_candidate_data)
    bad_data_det["movers"][0]["detections"][0]["ra"] = -5.0
    with pytest.raises(ContractValidationError):
        validate_dict(bad_data_det)


def test_reject_dec_out_of_bounds(valid_candidate_data):
    """Dec must be within -90.0 to 90.0."""
    bad_data = copy.deepcopy(valid_candidate_data)
    bad_data["movers"][0]["dec"] = 95.0
    with pytest.raises(ContractValidationError):
        validate_dict(bad_data)


def test_reject_mismatched_spectrum_lengths(valid_candidate_data):
    """Spectrum arrays (wavelength_um, flux, flux_err) must have identical length."""
    bad_data = copy.deepcopy(valid_candidate_data)
    # Truncate flux array by 1 element
    bad_data["movers"][0]["spectrum"]["flux"].pop()
    with pytest.raises(ContractValidationError, match="spectrum array lengths mismatch"):
        validate_dict(bad_data)


def test_reject_unknown_epoch_id(valid_candidate_data):
    """Detection referencing an undeclared epoch_id must be rejected."""
    bad_data = copy.deepcopy(valid_candidate_data)
    bad_data["movers"][0]["detections"][0]["epoch_id"] = "epoch_unregistered_999"
    with pytest.raises(ContractValidationError, match="unknown epoch_id"):
        validate_dict(bad_data)


def test_reject_unsorted_detections(valid_candidate_data):
    """Detections not in chronological order must be rejected."""
    bad_data = copy.deepcopy(valid_candidate_data)
    dets = bad_data["movers"][0]["detections"]
    if len(dets) >= 2:
        # Swap first two detections
        dets[0], dets[1] = dets[1], dets[0]
        with pytest.raises(ContractValidationError, match="not sorted chronologically"):
            validate_dict(bad_data)


def test_reject_inconsistent_match_name(valid_candidate_data):
    """Known movers require non-empty match_name; unknown movers require null."""
    # Known mover with null match_name
    bad_known = copy.deepcopy(valid_candidate_data)
    for m in bad_known["movers"]:
        if m["type"] == "known":
            m["match_name"] = None
            break
    with pytest.raises(ContractValidationError, match="type is 'known' but match_name is null"):
        validate_dict(bad_known)

    # Unknown mover with a match_name
    bad_unknown = copy.deepcopy(valid_candidate_data)
    for m in bad_unknown["movers"]:
        if m["type"] == "unknown":
            m["match_name"] = "Asteroid Surprise"
            break
    with pytest.raises(ContractValidationError, match="type is 'unknown' but match_name is"):
        validate_dict(bad_unknown)


def test_reproducibility_same_seed(tmp_path):
    """Generating mock catalog with identical seed yields identical JSON output."""
    cfg_file = REPO_ROOT / "config" / "settings.yaml"

    # Generate twice
    out1 = generate_mock_catalog(cfg_file)
    with open(out1, "r", encoding="utf-8") as f:
        data1 = json.load(f)

    out2 = generate_mock_catalog(cfg_file)
    with open(out2, "r", encoding="utf-8") as f:
        data2 = json.load(f)

    # Ignore generated_at timestamp differences if any (though same seed / same run)
    data1["generated_at"] = "FIXED_TIMESTAMP"
    data2["generated_at"] = "FIXED_TIMESTAMP"

    assert data1 == data2, "Outputs with same seed must be identical"


def test_cli_validator(candidates_path):
    """Test CLI invocation of validate.py."""
    res = subprocess.run(
        [sys.executable, str(REPO_ROOT / "docs" / "validate.py"), str(candidates_path)],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "[OK] Validation passed" in res.stdout

