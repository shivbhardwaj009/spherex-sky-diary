"""SPHEREx Sky Diary — Data Adapter Factory (Module 1).

Reads settings configuration and instantiates the appropriate EpochSource
implementation ("mock" or "irsa").
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml

from data.adapter.base import EpochSource
from data.adapter.irsa_source import IrsaFitsSource
from data.adapter.mock_source import MockSource

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "settings.yaml"


def load_config(config_input: Optional[Union[Dict[str, Any], Path, str]] = None) -> Dict[str, Any]:
    """Resolve configuration from dict, path, or default file."""
    if isinstance(config_input, dict):
        return config_input

    path = Path(config_input) if config_input is not None else DEFAULT_CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        loaded = yaml.safe_load(f)
        return loaded if isinstance(loaded, dict) else {}


def get_source(
    config: Optional[Union[Dict[str, Any], Path, str]] = None,
    **kwargs: Any,
) -> EpochSource:
    """Instantiate and return the configured EpochSource.

    Args:
        config: Configuration dict or path to settings.yaml (defaults to config/settings.yaml).
        **kwargs: Optional overrides passed to the source constructor.

    Returns:
        Instance of MockSource or IrsaFitsSource.

    Raises:
        ValueError: If data_source is missing or not recognized ('mock' | 'irsa').
    """
    cfg = load_config(config)
    data_source = cfg.get("data_source")

    if data_source == "mock":
        seed = kwargs.pop("seed", cfg.get("seed", 42))
        output_dir = kwargs.pop("output_dir", cfg.get("output_dir", "data/output"))
        base_fov_deg = kwargs.pop("fov_deg", cfg.get("fov_deg", 0.2))
        return MockSource(
            seed=seed,
            output_dir=output_dir,
            base_fov_deg=base_fov_deg,
            **kwargs,
        )

    elif data_source == "irsa":
        data_dir = kwargs.pop("data_dir", cfg.get("irsa_data_dir", "data/raw/irsa"))
        return IrsaFitsSource(data_dir=data_dir, **kwargs)

    else:
        raise ValueError(
            f"Invalid data_source: '{data_source}'. Supported data sources are 'mock' and 'irsa'."
        )

