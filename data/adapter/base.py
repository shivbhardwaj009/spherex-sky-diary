"""SPHEREx Sky Diary — Data Adapter Base Interface and Data Classes (Module 1).

Defines the core domain types and abstract EpochSource contract for accessing
both synthetic (mock) and real (IRSA FITS) observation data.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np
from astropy.wcs import WCS


@dataclass
class Region:
    """Target sky region specification."""

    name: str
    ra_center: float
    dec_center: float
    radius_deg: float


@dataclass
class EpochInfo:
    """Summary metadata for an observation epoch."""

    epoch_id: str
    date: datetime
    files: List[Union[str, Path]] = field(default_factory=list)
    band_count: int = 102
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EpochImage:
    """Calibrated image data plane for a single observation epoch."""

    pixels: np.ndarray  # 2D float array
    variance: np.ndarray  # 2D float array (per-pixel variance)
    mask: np.ndarray  # 2D bool or int bitmask (True/non-zero = masked/bad pixel)
    wcs: WCS  # Astropy WCS
    wavelength_map: np.ndarray  # 2D float array in microns (same shape as pixels)
    epoch_id: str
    date: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate array dimensions and consistency."""
        if self.pixels.ndim != 2:
            raise ValueError(f"pixels array must be 2D, got shape {self.pixels.shape}")
        if self.variance.shape != self.pixels.shape:
            raise ValueError(
                f"variance shape {self.variance.shape} must match pixels {self.pixels.shape}"
            )
        if self.mask.shape != self.pixels.shape:
            raise ValueError(
                f"mask shape {self.mask.shape} must match pixels {self.pixels.shape}"
            )
        if self.wavelength_map.shape != self.pixels.shape:
            raise ValueError(
                f"wavelength_map shape {self.wavelength_map.shape} must match pixels {self.pixels.shape}"
            )


class EpochSource(ABC):
    """Abstract interface for querying and loading observation epochs."""

    @abstractmethod
    def list_epochs(self, region: Region) -> List[EpochInfo]:
        """List available observation epochs for region, sorted ascending by date."""
        pass

    @abstractmethod
    def load_epoch(
        self,
        epoch_id: str,
        region: Region,
        fov_deg: float = 0.2,
    ) -> EpochImage:
        """Load calibrated epoch image plane for a given epoch, region, and FOV.

        Args:
            epoch_id: Identifier of the epoch to load.
            region: Target celestial region.
            fov_deg: Angular field of view size in degrees (default: 0.2).
        """
        pass

    @abstractmethod
    def get_ground_truth(self) -> Optional[Dict[str, Any]]:
        """Retrieve synthetic ground truth metadata if available (None for real data)."""
        pass

