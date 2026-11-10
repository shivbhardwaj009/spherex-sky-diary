"""SPHEREx Sky Diary — Detector Band Stacking (Module 5).

Co-adds or averages epoch images falling within the same SPHEREx detector spectral band
(Bands 1 through 6) to boost signal-to-noise ratio prior to aperture extraction.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from data.adapter.base import EpochImage, EpochSource, Region
from spectra.photometry import measure_source

logger = logging.getLogger(__name__)

# SPHEREx 6 physical focal plane detector arrays / wavelength bands in microns
# TODO(VERIFY): Official SPHEREx flight focal plane bandpass cutoffs
SPHEREX_BANDS: Dict[str, Tuple[float, float]] = {
    "band_1": (0.75, 1.11),
    "band_2": (1.11, 1.64),
    "band_3": (1.64, 2.42),
    "band_4": (2.42, 3.82),
    "band_5": (3.82, 4.42),
    "band_6": (4.42, 5.00),
}


def identify_band_for_image(
    epoch_image: EpochImage,
    bands: Optional[Dict[str, Tuple[float, float]]] = None,
) -> str:
    """Identify which SPHEREx detector array / band an EpochImage belongs to.

    TODO(VERIFY): In real SPHEREx FITS headers, read the detector array identifier
    from FITS header key (e.g., 'DETECTOR' or 'BANDID').
    """
    # 1. Check metadata if explicitly tagged
    if "band" in epoch_image.metadata:
        return str(epoch_image.metadata["band"])

    # 2. Derive from median focal-plane wavelength
    med_wl = float(np.nanmedian(epoch_image.wavelength_map))
    band_defs = bands or SPHEREX_BANDS

    for b_name, (w_min, w_max) in band_defs.items():
        if w_min <= med_wl <= w_max:
            return b_name

    return "band_unassigned"


def stack_epochs_by_band(
    epochs: List[EpochImage],
    bands: Optional[Dict[str, Tuple[float, float]]] = None,
) -> List[EpochImage]:
    """Co-add/average aligned images falling within the same spectral band.

    Propagates pixel flux (mean), variance (sum / M^2), combined mask,
    and average wavelength map.

    Args:
        epochs: List of aligned EpochImage objects.
        bands: Optional dictionary mapping band name to (w_min, w_max).

    Returns:
        List of stacked EpochImage objects (one per populated band).
    """
    if not epochs:
        return []

    band_defs = bands or SPHEREX_BANDS
    grouped: Dict[str, List[EpochImage]] = {}

    for ep in epochs:
        b_name = identify_band_for_image(ep, band_defs)
        if b_name not in grouped:
            grouped[b_name] = []
        grouped[b_name].append(ep)

    stacked_results: List[EpochImage] = []

    for b_name, ep_list in grouped.items():
        if len(ep_list) == 1:
            # Single image in this band, no co-addition needed
            single_ep = ep_list[0]
            single_ep.metadata["band"] = b_name
            single_ep.metadata["stacked_count"] = 1
            stacked_results.append(single_ep)
            continue

        # Multiple images: compute weighted or uniform average
        m_count = len(ep_list)
        ref = ep_list[0]

        # Stack pixels and variance
        stacked_pix = np.zeros_like(ref.pixels)
        stacked_var = np.zeros_like(ref.variance)
        stacked_mask = np.zeros_like(ref.mask)
        stacked_wl = np.zeros_like(ref.wavelength_map)

        for ep in ep_list:
            stacked_pix += ep.pixels
            stacked_var += ep.variance
            stacked_mask |= ep.mask
            stacked_wl += ep.wavelength_map

        # Mean pixel values and scaled variance: Var(mean) = sum(Var_i) / M^2
        stacked_pix /= float(m_count)
        stacked_var /= float(m_count**2)
        stacked_wl /= float(m_count)

        stacked_ep = EpochImage(
            pixels=stacked_pix,
            variance=stacked_var,
            mask=stacked_mask,
            wcs=ref.wcs,
            wavelength_map=stacked_wl,
            epoch_id=f"stacked_{b_name}",
            date=ref.date,
            metadata={
                "is_synthetic": ref.metadata.get("is_synthetic", True),
                "band": b_name,
                "stacked_count": m_count,
                "member_epochs": [ep.epoch_id for ep in ep_list],
            },
        )
        stacked_results.append(stacked_ep)
        logger.info("Stacked %d images for detector %s", m_count, b_name)

    return stacked_results


def compare_snr_gain(
    source: EpochSource,
    region: Region,
    ra: float,
    dec: float,
    fov_deg: float = 0.2,
    aperture_radius_pix: float = 3.5,
) -> Dict[str, float]:
    """Empirically measure S/N improvement from band stacking on synthetic data.

    Returns:
        Dictionary containing single_snr, stacked_snr, and snr_gain.
    """
    epoch_infos = source.list_epochs(region)
    if not epoch_infos:
        return {"single_snr": 0.0, "stacked_snr": 0.0, "snr_gain": 1.0}

    # Load first 2 epochs
    epochs_to_load = epoch_infos[:min(4, len(epoch_infos))]
    images = [source.load_epoch(ep.epoch_id, region, fov_deg=fov_deg) for ep in epochs_to_load]

    # Force all to same band for empirical stacking test
    for ep in images:
        ep.metadata["band"] = "band_test"

    # 1. Single epoch measurement
    m_single, _ = measure_source(images[0], ra=ra, dec=dec, aperture_radius_pix=aperture_radius_pix)
    single_snr = (m_single.flux / m_single.flux_err) if m_single and m_single.flux_err > 0 else 0.0

    # 2. Stacked measurement
    stacked = stack_epochs_by_band(images)
    m_stacked, _ = measure_source(stacked[0], ra=ra, dec=dec, aperture_radius_pix=aperture_radius_pix)
    stacked_snr = (m_stacked.flux / m_stacked.flux_err) if m_stacked and m_stacked.flux_err > 0 else 0.0

    gain = stacked_snr / single_snr if single_snr > 0 else 1.0

    return {
        "images_stacked": len(images),
        "single_flux": m_single.flux if m_single else 0.0,
        "single_err": m_single.flux_err if m_single else 0.0,
        "single_snr": round(float(single_snr), 3),
        "stacked_flux": m_stacked.flux if m_stacked else 0.0,
        "stacked_err": m_stacked.flux_err if m_stacked else 0.0,
        "stacked_snr": round(float(stacked_snr), 3),
        "snr_gain": round(float(gain), 3),
    }

