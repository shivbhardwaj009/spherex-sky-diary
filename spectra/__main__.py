"""CLI entry point for SPHEREx Sky Diary spectra module.

Usage:
    python -m spectra [--config config/settings.yaml] [--spectra-config config/spectra.yaml]
"""

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectra.pipeline import build_pipeline_config, run


def main() -> None:
    parser = argparse.ArgumentParser(description="SPHEREx multi-epoch spectral extraction pipeline.")
    parser.add_argument(
        "--config",
        type=str,
        default="config/settings.yaml",
        help="Path to main settings YAML file.",
    )
    parser.add_argument(
        "--spectra-config",
        type=str,
        default="config/spectra.yaml",
        help="Path to spectra configuration YAML file.",
    )
    parser.add_argument(
        "--candidates",
        type=str,
        default=None,
        help="Optional path to candidates.json to update in-place.",
    )

    args = parser.parse_args()
    config = build_pipeline_config(
        settings_path=args.config,
        spectra_config_path=args.spectra_config,
    )

    run(config=config, candidates_file=args.candidates)


if __name__ == "__main__":
    main()
