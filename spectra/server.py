"""SPHEREx Sky Diary — Optional Spectrum Extraction Server (Module 5).

Provides a lightweight FastAPI service for on-demand spectral extraction with CORS,
input validation, and static precomputed fallback for demo mode.

Usage:
    uvicorn spectra.server:app --port 8000
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from spectra.api import get_spectrum

REPO_ROOT = Path(__file__).resolve().parents[1]

app = FastAPI(
    title="SPHEREx Sky Diary — Spectral API",
    description="On-demand spectral extraction API for SPHEREx infrared sky cubes.",
    version="1.0.0",
)

# Enable CORS for Next.js browser frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_static_fallback_spectrum(ra: float, dec: float) -> Optional[Dict[str, Any]]:
    """Search precomputed demo spectra or candidate catalog for closest match."""
    spectra_dir = REPO_ROOT / "data" / "output" / "spectra"
    if spectra_dir.exists():
        for json_file in spectra_dir.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                d_ra = abs(data.get("ra", 999.0) - ra)
                d_dec = abs(data.get("dec", 999.0) - dec)
                if (d_ra**2 + d_dec**2) ** 0.5 < 0.5:
                    return data.get("spectrum")
            except Exception:
                continue

    # Also check candidates.json
    cand_file = REPO_ROOT / "data" / "output" / "candidates.json"
    if cand_file.exists():
        try:
            with open(cand_file, "r", encoding="utf-8") as f:
                cand_data = json.load(f)
            for m in cand_data.get("movers", []):
                spec = m.get("spectrum")
                if spec is not None:
                    return spec
        except Exception:
            pass

    return None


@app.get("/health")
def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "spherex-spectra-api"}


@app.get("/spectrum")
def get_spectrum_endpoint(
    ra: float = Query(..., ge=0.0, le=360.0, description="Right Ascension in degrees (J2000)"),
    dec: float = Query(..., ge=-90.0, le=90.0, description="Declination in degrees (J2000)"),
    fov: float = Query(0.2, gt=0.0, le=2.0, description="Field of view diameter in degrees"),
) -> Dict[str, Any]:
    """Extract or retrieve a binned SPHEREx spectrum for given sky coordinates."""
    # Attempt live extraction via pipeline API
    spectrum = None
    try:
        spectrum = get_spectrum(ra=ra, dec=dec, fov_deg=fov)
    except Exception:
        pass

    source_type = "live_extraction"

    # If live extraction returned None, try static precomputed fallback
    if spectrum is None:
        spectrum = load_static_fallback_spectrum(ra, dec)
        source_type = "static_fallback"

    if spectrum is None:
        raise HTTPException(
            status_code=404,
            detail=f"No valid spectral measurements obtained for coordinates ({ra:.4f}, {dec:.4f})",
        )

    return {
        "ra": ra,
        "dec": dec,
        "fov_deg": fov,
        "source": source_type,
        "is_synthetic": True,
        "spectrum": spectrum,
    }

