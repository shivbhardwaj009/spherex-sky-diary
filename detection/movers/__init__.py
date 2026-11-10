"""SPHEREx Sky Diary — Mover Detection Package (Module 3)."""

from detection.movers.difference import difference_epoch, pairwise_difference
from detection.movers.extract import extract_sources
from detection.movers.filters import (
    flag_filter_response,
    reject_bad_fit,
    reject_single_epoch,
    reject_stationary,
)
from detection.movers.linking import Tracklet, link_detections
from detection.movers.pipeline import run
from detection.movers.score import compute_confidence
from detection.movers.static_model import build_static_model

__all__ = [
    "build_static_model",
    "difference_epoch",
    "pairwise_difference",
    "extract_sources",
    "link_detections",
    "Tracklet",
    "reject_single_epoch",
    "reject_stationary",
    "flag_filter_response",
    "reject_bad_fit",
    "compute_confidence",
    "run",
]
