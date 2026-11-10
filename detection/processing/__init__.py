"""SPHEREx Sky Diary — Image Processing Package (Module 2)."""

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

__all__ = [
    "estimate_background",
    "subtract_background",
    "build_mask",
    "apply_mask",
    "BIT_ADAPTER_BAD",
    "BIT_OUTLIER",
    "BIT_EDGE",
    "build_reference_grid",
    "reproject_epoch",
    "select_reference_stars",
    "normalize_epochs",
    "comparable_mask",
    "wavelength_difference_map",
    "run",
    "load_processed_stack",
]

