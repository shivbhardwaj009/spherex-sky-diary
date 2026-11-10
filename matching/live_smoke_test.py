"""SPHEREx Sky Diary — Live SkyBoT Network Smoke Test.

Performs a live query against IMCCE SkyBoT for a known location to verify
network connectivity and response parsing.

NOTE: This script makes LIVE external network calls and is intended ONLY
for manual verification. It is NEVER executed during automated tests.

Usage:
    python matching/live_smoke_test.py
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy.time import Time
from astroquery.imcce import Skybot


def run_live_test() -> None:
    print("=" * 60)
    print("SPHEREx Sky Diary: Live SkyBoT Smoke Test")
    print("=" * 60)

    # Test coordinate: Ecliptic plane region near Ceres / Main Belt
    ra_deg = 60.0
    dec_deg = 20.0
    radius_deg = 0.5
    epoch_str = "2026-01-15 00:00:00"

    coord = SkyCoord(ra=ra_deg * u.deg, dec=dec_deg * u.deg, frame="icrs")
    epoch_time = Time(epoch_str)
    search_radius = radius_deg * u.deg

    print(f"Querying IMCCE SkyBoT for cone center: ({ra_deg:.2f}°, {dec_deg:.2f}°)")
    print(f"Radius: {radius_deg}° | Epoch: {epoch_str} (UT)")
    print("Contacting service...")

    try:
        table = Skybot.cone_search(
            coord,
            search_radius,
            epoch_time,
            location="500",  # Geocentric
            find_asteroids=True,
            find_comets=True,
            find_planets=True,
        )

        if table is None or len(table) == 0:
            print("Query succeeded: 0 bodies found in search cone.")
            return

        print(f"SUCCESS: Received table with {len(table)} Solar System object(s).\n")
        print("Sample returned columns:")
        for col in table.colnames[:8]:
            print(f"  - {col}")

        print("\nFirst 5 detected objects:")
        print("-" * 60)
        for i, row in enumerate(table[:5]):
            name = row["Name"]
            number = row.get("Number", "N/A")
            v_mag = row.get("V", "N/A")
            ra_r = row.get("RA_rate", "N/A")
            dec_r = row.get("DEC_rate", "N/A")
            print(f"[{i + 1}] ({number}) {name:<16} | V: {v_mag} | Rates: ({ra_r}, {dec_r}) \"/hr")

        print("-" * 60)
        print("Live smoke test completed successfully.")

    except Exception as exc:
        print(f"ERROR: Live SkyBoT query failed: {exc}")
        print("Check internet connection or firewall status.")


if __name__ == "__main__":
    run_live_test()
