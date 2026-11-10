# SPHEREx Sky Diary — Catalog Matching Validation Report

> [!IMPORTANT]
> **SYNTHETIC TEST BENCHMARK:** Evaluated on synthetic mock data with known injected movers.
> All metrics reflect algorithmic performance on synthetic test sets.


**Timestamp:** `2026-11-10T15:40:24.515548+00:00`  
**Target Region:** `ecliptic_plane_test`  

## 1. Executive Summary

| Metric | Value | Description |
| :--- | :--- | :--- |
| **Total Candidates** | `3` | Mover tracklets from detection pipeline |
| **Labeled Known** | `1` | Successfully matched to catalog ephemeris |
| **Labeled Unknown** | `2` | Unmatched (new mover / candidate) |
| **Known Bodies in Field** | `4` | Catalog bodies with ephemerides in cone |
| **Known Recovery Recall** | **`25.0%`** | Recovered / Total predicted in field |
| **Mean Separation Residual** | `0.88"` | Mean astrometric offset from ephemeris |
| **Median Separation Residual**| `0.88"` | Robust median astrometric offset |
| **Marginal Matches** | `0` | Detections approaching tolerance limit |

## 2. Recovered Known Asteroids

| Name | Type | V Mag | Speed (arcsec/day) | Candidate ID | Residual | Matched Epochs |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **(433) Eros** | asteroid | 14.5 | 20.36 | `mov_001` | 0.88" | 3 |

## 3. Missed Known Asteroids

| Name | Type | V Mag | Speed (arcsec/day) | Diagnostic Cause |
| :--- | :--- | :---: | :---: | :--- |
| **(1) Ceres** | asteroid | 15.3 | 33.14 | `unrecovered_tracklet` |
| **(4) Vesta** | asteroid | 16.1 | 12.36 | `unrecovered_tracklet` |
| **(10) Hygiea** | asteroid | 19.8 | 12.65 | `faint_magnitude_below_snr_threshold` |
