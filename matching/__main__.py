"""CLI entry point for SPHEREx Sky Diary matching module.

Usage:
    python -m matching [--config config/settings.yaml] [--matching-config config/matching.yaml] [--offline]
"""

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from matching.pipeline import build_pipeline_config, run


def main() -> None:
    parser = argparse.ArgumentParser(description="SPHEREx Solar System catalog matching pipeline.")
    parser.add_argument(
        "--config",
        type=str,
        default="config/settings.yaml",
        help="Path to main settings YAML file.",
    )
    parser.add_argument(
        "--matching-config",
        type=str,
        default="config/matching.yaml",
        help="Path to matching configuration YAML file.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Force offline mode using local cached ephemerides without external network access.",
    )
    parser.add_argument(
        "--candidates",
        type=str,
        default=None,
        help="Optional path to candidate JSON file to match in-place.",
    )

    args = parser.parse_args()
    config = build_pipeline_config(
        settings_path=args.config,
        matching_config_path=args.matching_config,
    )

    run(config=config, offline=args.offline, candidates_file=args.candidates)


if __name__ == "__main__":
    main()

