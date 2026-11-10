"use client";

import React from "react";
import { Modal } from "@/components/ui/Modal";
import { ExternalLink, Info } from "lucide-react";

export interface AboutModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AboutModal: React.FC<AboutModalProps> = ({ isOpen, onClose }) => {
  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="About SPHEREx Sky Diary"
      description="NASA Space Apps Challenge 2026 — Planet X and SPHEREx"
    >
      <div className="flex flex-col gap-4 text-sm text-apptext-secondary leading-relaxed">
        <p>
          <strong className="text-apptext-primary font-semibold">SPHEREx Sky Diary</strong> is an interactive
          astronomical discovery platform built for the NASA Space Apps Challenge 2026. It enables citizen scientists
          and astronomers to inspect time-resolved infrared sky maps from NASA&apos;s SPHEREx mission, detect moving
          Solar System objects, and view extracted 102-channel reflectance spectra (0.75 – 5.0 µm).
        </p>

        <div className="rounded-xl bg-space-surface border border-white/10 p-3.5 flex flex-col gap-2">
          <h4 className="text-xs uppercase font-semibold text-cyan-300 flex items-center gap-1.5">
            <Info className="w-3.5 h-3.5" aria-hidden="true" />
            <span>Mission & Data Acknowledgements</span>
          </h4>
          <p className="text-xs text-apptext-muted">
            {/* TODO(VERIFY): Use the exact acknowledgement wording requested by IRSA / IPAC for flight publications. */}
            This project uses data products from the NASA Spectro-Photometer for the History of the Universe, Epoch of
            Reionization and Ices Explorer (SPHEREx) mission, accessed via the NASA/IPAC Infrared Science Archive (IRSA),
            which is funded by the National Aeronautics and Space Administration.
          </p>
        </div>

        <div className="text-xs text-apptext-muted space-y-1.5 pt-1">
          <p>
            <strong className="text-apptext-secondary">Ephemeris Services:</strong> Cross-matching provided by IMCCE
            SkyBoT cone search service and NASA/JPL Horizons System.
          </p>
          <p>
            <strong className="text-apptext-secondary">Challenge:</strong> Planet X and SPHEREx — Exploring the Outer Solar System.
          </p>
        </div>

        <div className="pt-2 flex justify-end">
          <a
            href="https://spherex.caltech.edu"
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-cyan-400 hover:text-cyan-300 inline-flex items-center gap-1 font-medium focus:outline-none focus-visible:underline"
          >
            <span>Learn about SPHEREx Mission</span>
            <ExternalLink className="w-3.5 h-3.5" aria-hidden="true" />
          </a>
        </div>
      </div>
    </Modal>
  );
};
