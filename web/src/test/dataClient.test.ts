import { describe, it, expect, vi, beforeEach } from "vitest";
import { loadCandidates, DataClientError } from "@/lib/dataClient";

describe("Typed Data Client & Runtime Schema Validator", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const validCatalog = {
    schema_version: "1.0",
    region: {
      name: "ecliptic_plane_test",
      ra_center: 60.0,
      dec_center: 20.0,
      radius_deg: 0.2,
    },
    epochs: [
      {
        epoch_id: "epoch_01",
        date: "2026-01-10T00:00:00Z",
        band_count: 102,
      },
    ],
    movers: [
      {
        object_id: "mov_001",
        ra: 60.0,
        dec: 20.0,
        type: "known",
        match_name: "(433) Eros",
        confidence: 0.95,
        is_synthetic: true,
        motion: {
          ra_rate_arcsec_per_day: 15.0,
          dec_rate_arcsec_per_day: 5.0,
        },
        detections: [
          {
            epoch_id: "epoch_01",
            date: "2026-01-10T00:00:00Z",
            ra: 60.0,
            dec: 20.0,
            flux: 120.0,
            cutout_url: "cutouts/mov_001_epoch_01.png",
          },
        ],
        spectrum: null,
      },
    ],
  };

  it("successfully loads and validates contract-compliant data", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => validCatalog,
    } as unknown as Response);

    const data = await loadCandidates("/data/candidates.json");
    expect(data.schema_version).toBe("1.0");
    expect(data.movers.length).toBe(1);
    expect(data.movers[0].match_name).toBe("(433) Eros");
  });

  it("throws NOT_FOUND error on 404 response", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      statusText: "Not Found",
    } as unknown as Response);

    await expect(loadCandidates("/missing.json")).rejects.toThrow(
      "Static candidates file not found"
    );
  });

  it("throws PARSE_ERROR on invalid JSON", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => {
        throw new Error("Unexpected token < in JSON");
      },
    } as unknown as Response);

    await expect(loadCandidates("/bad.json")).rejects.toThrow("Failed to parse");
  });

  it("throws VALIDATION_ERROR on schema break (missing required fields)", async () => {
    const invalidData = {
      schema_version: "1.0",
      // Missing required region, epochs, movers
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => invalidData,
    } as unknown as Response);

    await expect(loadCandidates("/invalid.json")).rejects.toThrow(
      "violates SPHEREx Schema 1.0 contract"
    );
  });

  it("handles empty movers list correctly", async () => {
    const emptyMoversCatalog = {
      ...validCatalog,
      movers: [],
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => emptyMoversCatalog,
    } as unknown as Response);

    const data = await loadCandidates("/empty.json");
    expect(data.movers).toEqual([]);
  });
});
