/* tslint:disable */
/**
 * Auto-generated from docs/schema.json via `npm run gen:types`.
 * DO NOT EDIT DIRECTLY.
 */

/**
 * Unified JSON contract for moving object detections, tracks, and spectra in SPHEREx sky patches.
 */
export interface SPHERExSkyDiaryCandidatesContract {
  /**
   * Semantic schema contract version. Must be 1.0.
   */
  schema_version: "1.0";
  /**
   * Version identifier for the data release or pipeline run.
   */
  data_version?: string;
  /**
   * ISO 8601 timestamp of when this candidate catalog was produced.
   */
  generated_at?: string;
  /**
   * Field of view diameter/width in degrees for the patch.
   */
  fov_deg?: number;
  /**
   * Optional pipeline and execution metadata (e.g., matching_source: 'skybot' | 'offline_catalog').
   */
  metadata?: {
    [k: string]: unknown;
  };
  region: {
    /**
     * Human-readable label or target identifier for the sky patch.
     */
    name: string;
    /**
     * Right Ascension center coordinate (J2000) in degrees.
     */
    ra_center: number;
    /**
     * Declination center coordinate (J2000) in degrees.
     */
    dec_center: number;
    /**
     * Angular radius of the region in degrees.
     */
    radius_deg: number;
  };
  /**
   * List of SPHEREx observation epochs covered in this sky patch.
   *
   * @minItems 1
   */
  epochs: [
    {
      /**
       * Unique identifier for the observation epoch.
       */
      epoch_id: string;
      /**
       * Observation date and time in ISO 8601 format.
       */
      date: string;
      /**
       * Number of spectral channels / bands observed in this epoch.
       */
      band_count: number;
    },
    ...{
      /**
       * Unique identifier for the observation epoch.
       */
      epoch_id: string;
      /**
       * Observation date and time in ISO 8601 format.
       */
      date: string;
      /**
       * Number of spectral channels / bands observed in this epoch.
       */
      band_count: number;
    }[]
  ];
  /**
   * Detected moving objects within the region across observation epochs.
   */
  movers: {
    /**
     * Unique identifier for the moving object candidate.
     */
    object_id: string;
    /**
     * Current or reference Right Ascension in degrees.
     */
    ra: number;
    /**
     * Current or reference Declination in degrees.
     */
    dec: number;
    /**
     * Mover classification: known solar system body or newly discovered unknown mover.
     */
    type: "known" | "unknown";
    /**
     * Catalog or MPC designation if known, or null if unknown.
     */
    match_name: string | null;
    /**
     * Mean positional separation in arcseconds between detections and predicted ephemeris.
     */
    match_distance_arcsec?: number;
    /**
     * Number of observation epochs where the candidate matched the ephemeris within tolerance.
     */
    matched_epoch_count?: number;
    /**
     * Second-closest matching known body designation in case of ambiguity, or null.
     */
    runner_up_match?: string | null;
    /**
     * Classification or detection confidence score between 0.0 and 1.0.
     */
    confidence: number;
    /**
     * True if synthetic/mock data. Mandates 'TEST DATA' badge in the UI.
     */
    is_synthetic: boolean;
    motion: {
      /**
       * Apparent motion rate in RA in arcseconds per day (dRA/dt * cos(dec)).
       */
      ra_rate_arcsec_per_day: number;
      /**
       * Apparent motion rate in Dec in arcseconds per day (dDec/dt).
       */
      dec_rate_arcsec_per_day: number;
    };
    /**
     * Individual epoch detections constituting the mover's trajectory.
     *
     * @minItems 1
     */
    detections: [
      {
        /**
         * ID of the epoch corresponding to this detection.
         */
        epoch_id: string;
        /**
         * Detection timestamp in ISO 8601 format.
         */
        date: string;
        /**
         * Measured RA in degrees at this epoch.
         */
        ra: number;
        /**
         * Measured Dec in degrees at this epoch.
         */
        dec: number;
        /**
         * Integrated or peak measured flux (in arbitrary or physical units, e.g. uJy).
         */
        flux: number;
        /**
         * Relative URL or path to the postage-stamp cutout image.
         */
        cutout_url: string;
      },
      ...{
        /**
         * ID of the epoch corresponding to this detection.
         */
        epoch_id: string;
        /**
         * Detection timestamp in ISO 8601 format.
         */
        date: string;
        /**
         * Measured RA in degrees at this epoch.
         */
        ra: number;
        /**
         * Measured Dec in degrees at this epoch.
         */
        dec: number;
        /**
         * Integrated or peak measured flux (in arbitrary or physical units, e.g. uJy).
         */
        flux: number;
        /**
         * Relative URL or path to the postage-stamp cutout image.
         */
        cutout_url: string;
      }[]
    ];
    /**
     * Extracted SPHEREx spectrum for this mover, or null if unextracted.
     */
    spectrum: null | {
      /**
       * Array of wavelengths in micrometers (0.75 - 5.0 um).
       */
      wavelength_um: number[];
      /**
       * Calibrated spectral flux array.
       */
      flux: number[];
      /**
       * 1-sigma uncertainty per spectral channel.
       */
      flux_err: number[];
    };
  }[];
}
