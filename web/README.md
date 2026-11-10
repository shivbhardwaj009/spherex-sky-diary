# SPHEREx Sky Diary — Web Application (Module 6)

Interactive web frontend for the **NASA Space Apps Challenge 2026** (Challenge: Planet X and SPHEREx).

Built with **Next.js 14 (App Router)**, **TypeScript (Strict Mode)**, **Tailwind CSS**, and **Vitest**.

---

## 1. Quick Start

```bash
# 1. Install dependencies
npm install

# 2. Sync static scientific pipeline artifacts (candidates.json, cutouts, spectra)
npm run sync-data

# 3. Start development server
npm run dev

# 4. Open in browser
# App Shell:   http://localhost:3000
# Design Sheet: http://localhost:3000/design
```

---

## 2. Available Scripts

| Script | Command | Purpose |
| :--- | :--- | :--- |
| `dev` | `next dev` | Start local Next.js development server |
| `build` | `next build` | Compile production static build |
| `test` | `vitest run` | Run component, accessibility, and client unit tests |
| `typecheck` | `tsc --noEmit` | Strict TypeScript type validation |
| `lint` | `next lint` | Run ESLint static analysis |
| `sync-data` | `node scripts/sync-data.mjs` | Copies `/data/output/` artifacts to `/web/public/data/` |
| `gen:types` | `node scripts/gen-types.mjs` | Generates TypeScript interfaces from `docs/schema.json` |

---

## 3. Design System & Tokens

All tokens are centralized in [`web/src/design/tokens.ts`](src/design/tokens.ts):
- **Theme:** Deep space navy (`#050B1A` to `#0B1630`) with translucent glass surfaces (`backdrop-blur-md`).
- **Object Status Accents:**
  - **Cyan (`#22D3EE`):** Catalog-matched Known Asteroids / Comets.
  - **Amber (`#FBBF24`):** Unmatched Unknown mover candidates.
  - **Rose (`#F43F5E`):** Synthetic Test Data warning banner (mandated on synthetic runs).
  - **Slate (`#94A3B8`):** Offline ephemeris catalog fallback.
- **Contrast Compliance:** Every text/background combination satisfies **WCAG AA** standards ($\ge 4.5:1$ body, $\ge 3.0:1$ UI accents).
- **Accessibility:**
  - Minimum touch target: `44px x 44px` on all buttons and inputs.
  - Visible keyboard focus ring: 2px cyan/sky outline with 2px offset.
  - `prefers-reduced-motion` honored across all animations.
- **Component Review Sheet:** Visit `/design` to inspect all UI components in every state.

---

## 4. Architectural Boundaries & Static Client

- The web app **only READS static files** (`/public/data/candidates.json`, `/public/data/cutouts/`, `/public/data/spectra/`).
- No heavy scientific computation is executed in the browser.
- Data fetching is validated at runtime with `Ajv` against [`docs/schema.json`](../../docs/schema.json).
- Modules 7 & 8 placeholders are labeled in [`AppShell.tsx`](src/components/layout/AppShell.tsx):
  - `#sky-viewer-slot`: Aladin Lite interactive sky map (Module 7).
  - `#time-controls-slot`: Epoch playback & blink time-lapse controls (Module 7).
  - `#movers-list-slot`: Candidate mover filtering and tracklet cards (Module 8).
  - `#spectra-detail-slot`: 102-channel reflectance spectra and diagnostic indices (Module 8).
