"""Validation helper for SPHEREx Sky Diary JSON contract (schema v1.0).

Validates candidate files against docs/schema.json and applies supplementary
domain rules (array length invariants, chronological sorting, relational
integrity of epoch IDs, and classification consistency).
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import jsonschema
from jsonschema import Draft202012Validator, FormatChecker

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.json"


class ContractValidationError(Exception):
    """Raised when JSON contract or domain validation invariants fail."""

    def __init__(self, errors: List[str]):
        self.errors = errors
        message = f"Found {len(errors)} contract validation error(s):\n" + "\n".join(
            f"  - {err}" for err in errors
        )
        super().__init__(message)


def load_schema(schema_path: Path | str = SCHEMA_PATH) -> Dict[str, Any]:
    """Load JSON schema definition."""
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _parse_iso_date(date_str: str) -> datetime:
    """Parse ISO 8601 timestamp string into datetime."""
    # Replace trailing 'Z' with +00:00 for standard datetime parser
    normalized = date_str.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def validate_dict(data: Dict[str, Any], schema: Dict[str, Any] | None = None) -> None:
    """Validate a python dictionary against the contract schema and invariants.

    Raises:
        ContractValidationError: If any schema or domain rule is violated.
    """
    if schema is None:
        schema = load_schema()

    errors: List[str] = []

    # 1. Structural validation via JSON Schema (Draft 2020-12)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for validation_err in validator.iter_errors(data):
        field_path = ".".join(str(p) for p in validation_err.absolute_path) or "root"
        errors.append(f"Schema violation at '{field_path}': {validation_err.message}")

    # If top-level structure is already fundamentally broken, raise immediately
    if not isinstance(data, dict):
        raise ContractValidationError(errors)

    # 2. Extract epochs index for referential integrity checks
    declared_epoch_ids = set()
    epochs = data.get("epochs")
    if isinstance(epochs, list):
        for idx, ep in enumerate(epochs):
            if isinstance(ep, dict) and "epoch_id" in ep:
                declared_epoch_ids.add(ep["epoch_id"])

    # 3. Domain invariant checks across movers
    movers = data.get("movers")
    if isinstance(movers, list):
        for m_idx, mover in enumerate(movers):
            if not isinstance(mover, dict):
                continue
            mover_id = mover.get("object_id", f"mover[{m_idx}]")

            # Check match_name vs type consistency
            mover_type = mover.get("type")
            match_name = mover.get("match_name")
            if mover_type == "known" and (match_name is None or not str(match_name).strip()):
                errors.append(
                    f"Mover '{mover_id}': type is 'known' but match_name is null or empty."
                )
            elif mover_type == "unknown" and match_name is not None:
                errors.append(
                    f"Mover '{mover_id}': type is 'unknown' but match_name is '{match_name}' (must be null)."
                )

            # Check spectrum array lengths
            spectrum = mover.get("spectrum")
            if isinstance(spectrum, dict):
                wl = spectrum.get("wavelength_um", [])
                flux = spectrum.get("flux", [])
                flux_err = spectrum.get("flux_err", [])
                if not (len(wl) == len(flux) == len(flux_err)):
                    errors.append(
                        f"Mover '{mover_id}': spectrum array lengths mismatch: "
                        f"wavelength_um={len(wl)}, flux={len(flux)}, flux_err={len(flux_err)}"
                    )

            # Check detections
            detections = mover.get("detections")
            if isinstance(detections, list) and detections:
                prev_date: datetime | None = None
                for d_idx, det in enumerate(detections):
                    if not isinstance(det, dict):
                        continue
                    
                    # Referential integrity: epoch_id must exist in epochs
                    ep_id = det.get("epoch_id")
                    if ep_id not in declared_epoch_ids:
                        errors.append(
                            f"Mover '{mover_id}', detection[{d_idx}]: references unknown "
                            f"epoch_id '{ep_id}'."
                        )

                    # Chronological ordering check
                    date_val = det.get("date")
                    if isinstance(date_val, str):
                        try:
                            curr_date = _parse_iso_date(date_val)
                            if prev_date is not None and curr_date < prev_date:
                                errors.append(
                                    f"Mover '{mover_id}': detections are not sorted chronologically: "
                                    f"detection[{d_idx}] date '{date_val}' is earlier than previous detection."
                                )
                            prev_date = curr_date
                        except Exception as e:
                            errors.append(
                                f"Mover '{mover_id}', detection[{d_idx}]: invalid date '{date_val}': {e}"
                            )

    if errors:
        raise ContractValidationError(errors)


def validate_file(file_path: Path | str) -> Dict[str, Any]:
    """Load JSON from file and validate against contract schema and rules.

    Returns:
        Loaded and validated dictionary.
    Raises:
        ContractValidationError: If invalid.
        FileNotFoundError: If file not found.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as exc:
            raise ContractValidationError([f"JSON parse error in {path}: {exc}"]) from exc

    validate_dict(data)
    return data


def main() -> None:
    """CLI entrypoint for validate.py."""
    target = sys.argv[1] if len(sys.argv) > 1 else "data/output/candidates.json"
    path = Path(target)
    print(f"[Contract Validator] Checking: {path}")
    try:
        data = validate_file(path)
        movers_count = len(data.get("movers", []))
        epochs_count = len(data.get("epochs", []))
        print(f"[OK] Validation passed: {path}")
        print(f"     - Schema version: {data.get('schema_version')}")
        print(f"     - Region: {data.get('region', {}).get('name')}")
        print(f"     - Epochs: {epochs_count}")
        print(f"     - Movers: {movers_count}")
    except ContractValidationError as err:
        print(f"[ERROR] Contract validation failed for {path}:", file=sys.stderr)
        print(str(err), file=sys.stderr)
        sys.exit(1)
    except Exception as err:
        print(f"[FATAL] Error validating {path}: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
