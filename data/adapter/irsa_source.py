"""SPHEREx Sky Diary — IRSA FITS Data Adapter Stub (Module 1).

Implements the EpochSource interface for real SPHEREx data delivered via NASA/IPAC
Infrared Science Archive (IRSA). All methods raise NotImplementedError pending
official mission data verification.

CRITICAL RULES:
- Never invent FITS extension names or assume internal data layouts.
- Isolate all file handling here and mark every unverified assumption with TODO(VERIFY).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from data.adapter.base import EpochImage, EpochInfo, EpochSource, Region


class IrsaFitsSource(EpochSource):
    """Data source adapter for real SPHEREx FITS products served by IRSA.

    All methods raise NotImplementedError until the data release specification
    is verified by the team.
    """

    def __init__(
        self,
        data_dir: Optional[Path | str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        self.data_dir = Path(data_dir) if data_dir is not None else Path("data/raw/irsa")
        self.api_key = api_key

    def list_epochs(self, region: Region) -> List[EpochInfo]:
        """Query or scan IRSA archive files for observation epochs covering region.

        Raises:
            NotImplementedError: Real SPHEREx file hierarchy and epoch grouping
            are not yet verified.
        """
        # TODO(VERIFY): file extensions and how many FITS extensions exist
        # Example questions: Are files single-band exposures (.fits), multi-band
        # spectral cubes (.fits.gz), or MEF (Multi-Extension FITS) containers?
        #
        # TODO(VERIFY): how to group files into epochs by date and band
        # Example questions: Does an "epoch" correspond to a single survey visit,
        # an orbit, or a coadd within a time window (e.g., 6-month full sky pass)?
        # Which FITS header keywords specify the start/end observation timestamps
        # (e.g., DATE-OBS, MJD-OBS, TIME-OBS)?
        raise NotImplementedError(
            "IrsaFitsSource.list_epochs() is not implemented. "
            "Real SPHEREx FITS organization, file extensions, and epoch time keywords "
            "are pending verification from IRSA release documentation. TODO(VERIFY)."
        )

    def load_epoch(
        self,
        epoch_id: str,
        region: Region,
        fov_deg: float = 0.2,
    ) -> EpochImage:
        """Load and extract calibrated image planes for a single epoch.

        Raises:
            NotImplementedError: Extension mapping and WCS conventions are not verified.
        """
        # TODO(VERIFY): how WCS is stored and whether it is per-extension
        # Example questions: Does the primary HDU contain the celestial WCS
        # (CRVAL, CRPIX, CD matrix / CDELT, CTYPE=RA---TAN/DEC--TAN), or does each
        # spectral band extension define its own pointing solution / distortion (SIP)?
        #
        # TODO(VERIFY): where the per-pixel wavelength information lives
        # Example questions: Does each extension correspond to a fixed wavelength band,
        # is wavelength parameterized as a header polynomial (LVF dispersion coefficients),
        # or is there an explicit WAVELENGTH HDU/table?
        #
        # TODO(VERIFY): mask / flag extension and bit meanings
        # Example questions: Name of the data quality extension (e.g., 'MASK', 'DQ',
        # 'FLAGS') and the bitmask definitions (which bit corresponds to bad pixel,
        # cosmic ray, saturation, edge, or stray light?).
        #
        # TODO(VERIFY): variance or uncertainty extension
        # Example questions: Name and units of uncertainty HDU (e.g., 'UNCERT', 'VAR',
        # 'ERR', 'SIGMA'). Is it 1-sigma standard deviation or variance (sigma^2)?
        #
        # TODO(VERIFY): PSF extension and the known PSF header caveat
        # Example questions: Is an effective PSF provided per band/detector?
        # Note the known SPHEREx PSF caveat: verify pixel grid centering (0.5 pixel
        # offset convention between FITS Fortran 1-based and C/Python 0-based indexing).
        raise NotImplementedError(
            "IrsaFitsSource.load_epoch() is not implemented. "
            "FITS extensions for WCS, wavelength mapping, DQ mask, variance, and PSF "
            "must be verified against the official SPHEREx IRSA data delivery. TODO(VERIFY)."
        )

    def get_ground_truth(self) -> Optional[Dict[str, Any]]:
        """Real flight data does not provide synthetic ground truth. Always returns None."""
        return None


def query_irsa_cutout_example(
    ra: float,
    dec: float,
    size_deg: float = 0.2,
) -> Optional[Any]:
    """Demonstration helper showing how an IRSA cutout request could be issued.

    NOTE: This is a reference stub. It is guarded against execution and must NOT
    be called by test suites or run during pipeline imports.
    """
    try:
        import pyvo as vo
        from astroquery.ipac.irsa import Irsa
    except ImportError:
        # astroquery or pyvo not installed / optional
        return None

    # TODO(VERIFY): Confirm the exact IVOA SIA (Simple Image Access) or TAP service
    # endpoint URL registered for SPHEREx at IRSA.
    sia_service_url = "https://irsa.ipac.caltech.edu/SIA?COLLECTION=spherex"
    try:
        service = vo.dal.SIAService(sia_service_url)
        results = service.search(pos=(ra, dec), size=size_deg)
        return results
    except Exception as exc:
        # Network/auth access intentionally not executed during unit tests
        return None
