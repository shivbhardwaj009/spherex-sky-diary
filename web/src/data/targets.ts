/**
 * SPHEREx Sky Diary — Quick Target Presets (Module 6 & 7)
 *
 * Curated list of high-priority demonstration targets for quick-pick selection
 * in the sky viewer interface.
 */

export interface QuickTarget {
  id: string;
  name: string;
  ra: number;
  dec: number;
  fovDeg: number;
  type: "brown_dwarf" | "red_dwarf" | "yso" | "variable_star" | "test_field";
  description: string;
}

export const QUICK_TARGETS: QuickTarget[] = [
  {
    id: "wise_0855",
    name: "WISE 0855",
    ra: 133.79513, // Verified: RA 08h55m10.831s
    dec: -7.24515,  // Verified: Dec -07d14m42.53s
    fovDeg: 0.2,
    type: "brown_dwarf",
    description: "Coldest known sub-stellar brown dwarf (Y-dwarf, T ~ 250 K).",
  },
  {
    id: "barnards_star",
    name: "Barnard's Star",
    ra: 269.45208, // TODO(VERIFY): Propagate proper motion from Gaia DR3 to SPHEREx survey epoch
    dec: 4.69339,
    fovDeg: 0.2,
    type: "red_dwarf",
    description: "Nearby high-proper-motion M-dwarf star (~10.4 arcsec/yr).",
  },
  {
    id: "epsilon_indi_b",
    name: "Epsilon Indi B",
    ra: 330.84042, // TODO(VERIFY): Binary brown dwarf system J2000 vs current epoch
    dec: -56.78611,
    fovDeg: 0.2,
    type: "brown_dwarf",
    description: "Nearby binary brown dwarf system (T1 + T6).",
  },
  {
    id: "rw_aurigae",
    name: "RW Aurigae",
    ra: 77.10625, // TODO(VERIFY): Young stellar object coordinates
    dec: 30.40139,
    fovDeg: 0.2,
    type: "yso",
    description: "Young stellar object undergoing episodic accretion dimming.",
  },
  {
    id: "r_draconis",
    name: "R Draconis",
    ra: 248.33792, // TODO(VERIFY): Long-period pulsating variable coordinates
    dec: 66.86861,
    fovDeg: 0.2,
    type: "variable_star",
    description: "Mira-type long-period variable star with circumstellar dust envelope.",
  },
  {
    id: "ecliptic_demo",
    name: "Ecliptic Test Patch",
    ra: 60.0,
    dec: 20.0,
    fovDeg: 0.2,
    type: "test_field",
    description: "Baseline SPHEREx mock survey patch with injected moving asteroids.",
  },
];
