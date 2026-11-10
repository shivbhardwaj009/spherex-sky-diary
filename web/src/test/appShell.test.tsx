import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { AppShell } from "@/components/layout/AppShell";
import { DataProvider } from "@/lib/DataProvider";
import { BeginnerModeProvider } from "@/lib/BeginnerModeContext";
import { SPHERExSkyDiaryCandidatesContract } from "@/types/candidates";

const mockSyntheticCatalog: SPHERExSkyDiaryCandidatesContract = {
  schema_version: "1.0",
  region: {
    name: "ecliptic_plane_test",
    ra_center: 60.0,
    dec_center: 20.0,
    radius_deg: 0.2,
  },
  epochs: [
    { epoch_id: "mock_epoch_01", date: "2026-01-15T00:00:00Z", band_count: 102 },
  ],
  movers: [
    {
      object_id: "mov_001",
      ra: 60.034,
      dec: 19.979,
      type: "known",
      match_name: "(433) Eros",
      confidence: 0.96,
      is_synthetic: true, // Mandates TEST DATA badge
      motion: { ra_rate_arcsec_per_day: 19.5, dec_rate_arcsec_per_day: 5.5 },
      detections: [
        {
          epoch_id: "mock_epoch_01",
          date: "2026-01-15T00:00:00Z",
          ra: 60.034,
          dec: 19.979,
          flux: 120.0,
          cutout_url: "cutouts/mov_001.png",
        },
      ],
      spectrum: null,
    },
    {
      object_id: "mov_002",
      ra: 59.932,
      dec: 20.074,
      type: "unknown",
      match_name: null,
      confidence: 0.82,
      is_synthetic: true,
      motion: { ra_rate_arcsec_per_day: 31.6, dec_rate_arcsec_per_day: 9.8 },
      detections: [
        {
          epoch_id: "mock_epoch_01",
          date: "2026-01-15T00:00:00Z",
          ra: 59.932,
          dec: 20.074,
          flux: 65.0,
          cutout_url: "cutouts/mov_002.png",
        },
      ],
      spectrum: null,
    },
  ],
};

describe("App Shell & Synthetic Test Data Banner", () => {
  it("shows persistent, visible TEST DATA badge in top bar when is_synthetic is true", () => {
    render(
      <DataProvider initialData={mockSyntheticCatalog}>
        <BeginnerModeProvider>
          <AppShell />
        </BeginnerModeProvider>
      </DataProvider>
    );

    // TEST DATA badge must be visible
    const testDataBadges = screen.getAllByText("TEST DATA");
    expect(testDataBadges.length).toBeGreaterThanOrEqual(1);

    // Focus shows tooltip explanation
    const trigger = testDataBadges[0].closest("[tabindex='0']");
    if (trigger) {
      fireEvent.focus(trigger);
      expect(
        screen.getByText("Synthetic data for testing. Not a real SPHEREx detection.")
      ).toBeInTheDocument();
    }
  });

  it("renders labeled placeholder slots for Modules 7 and 8", () => {
    render(
      <DataProvider initialData={mockSyntheticCatalog}>
        <BeginnerModeProvider>
          <AppShell />
        </BeginnerModeProvider>
      </DataProvider>
    );

    expect(screen.getByText(/Aladin Lite Sky Viewer/i)).toBeInTheDocument();
    expect(screen.getByText(/Time-lapse Blink & Epoch Slider/i)).toBeInTheDocument();
    expect(screen.getByText(/Candidate Movers List/i)).toBeInTheDocument();
    expect(screen.getByText(/102-Channel Spectra Viewer/i)).toBeInTheDocument();
  });

  it("opens About modal with SPHEREx mission & IRSA attribution placeholder", () => {
    render(
      <DataProvider initialData={mockSyntheticCatalog}>
        <BeginnerModeProvider>
          <AppShell />
        </BeginnerModeProvider>
      </DataProvider>
    );

    const aboutBtn = screen.getByRole("button", {
      name: /open about and data attribution modal/i,
    });
    fireEvent.click(aboutBtn);

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText(/About SPHEREx Sky Diary/i)).toBeInTheDocument();
    expect(screen.getByText(/NASA\/IPAC Infrared Science Archive/i)).toBeInTheDocument();
  });
});
