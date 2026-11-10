/**
 * SPHEREx Sky Diary — Design System Tokens
 *
 * Owned by Yash Pratap (Design Lead). All color, typography, spacing,
 * and elevation tokens are centralized in this file.
 */

export const colors = {
  // Deep space backgrounds
  space: {
    black: "#020617",     // Deepest void
    deep: "#050B1A",      // Base app background
    navy: "#0B1630",      // Elevated background / card surface
    surface: "#0F1E3D",   // Active surface
    surfaceHover: "#162850",
  },

  // Glass panel styling tokens
  glass: {
    bg: "rgba(11, 22, 48, 0.75)",
    border: "rgba(255, 255, 255, 0.12)",
    borderHighlight: "rgba(34, 211, 238, 0.35)",
    shadow: "0 8px 32px 0 rgba(0, 0, 0, 0.37)",
  },

  // Celestial object status accents (distinct, high-contrast)
  status: {
    known: {
      primary: "#22D3EE", // Cyan-400 (Known solar system asteroid / comet)
      bg: "rgba(34, 211, 238, 0.15)",
      border: "rgba(34, 211, 238, 0.40)",
      text: "#A5F3FC",
    },
    unknown: {
      primary: "#FBBF24", // Amber-400 (Unknown / new candidate mover)
      bg: "rgba(251, 191, 36, 0.15)",
      border: "rgba(251, 191, 36, 0.40)",
      text: "#FDE68A",
    },
    testData: {
      primary: "#F43F5E", // Rose-500 (Synthetic Test Data warning banner)
      bg: "rgba(244, 63, 94, 0.20)",
      border: "#F43F5E",
      text: "#FFE4E6",
    },
    offline: {
      primary: "#94A3B8", // Slate-400 (Offline catalog fallback)
      bg: "rgba(148, 163, 184, 0.15)",
      border: "rgba(148, 163, 184, 0.35)",
      text: "#E2E8F0",
    },
    danger: {
      primary: "#EF4444",
      bg: "rgba(239, 68, 68, 0.15)",
      border: "rgba(239, 68, 68, 0.40)",
      text: "#FCA5A5",
    },
  },

  // High-contrast accessible text scale
  text: {
    primary: "#F8FAFC",   // Slate-50 (>18:1 contrast on #050B1A)
    secondary: "#CBD5E1", // Slate-300 (>10:1 contrast on #050B1A)
    muted: "#94A3B8",     // Slate-400 (>6.5:1 contrast on #050B1A - WCAG AA pass)
    dim: "#64748B",       // Slate-500 (4.0:1, UI decorative only)
  },

  // Focus ring token (2px high-visibility outline with 2px offset)
  focus: {
    ring: "#38BDF8",      // Sky-400
    ringOffset: "#050B1A",
  },
} as const;

export const typography = {
  fontFamily: {
    sans: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    mono: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
  },
  fontSize: {
    xs: ["0.75rem", { lineHeight: "1rem" }],        // 12px
    sm: ["0.875rem", { lineHeight: "1.25rem" }],    // 14px
    base: ["1rem", { lineHeight: "1.5rem" }],       // 16px
    lg: ["1.125rem", { lineHeight: "1.75rem" }],    // 18px
    xl: ["1.25rem", { lineHeight: "1.75rem" }],     // 20px
    "2xl": ["1.5rem", { lineHeight: "2rem" }],      // 24px
    "3xl": ["1.875rem", { lineHeight: "2.25rem" }], // 30px
  },
  fontWeight: {
    normal: "400",
    medium: "500",
    semibold: "600",
    bold: "700",
  },
} as const;

export const spacing = {
  touchMin: "44px", // Minimum touch target size for WCAG 2.5.5
  radius: {
    sm: "0.25rem",   // 4px
    md: "0.5rem",    // 8px
    lg: "0.75rem",   // 12px
    xl: "1rem",      // 16px
    full: "9999px",
  },
  zIndex: {
    base: "0",
    dropdown: "1000",
    sticky: "1100",
    banner: "1200",
    modal: "1300",
    tooltip: "1400",
  },
} as const;

/**
 * Computes relative luminance according to WCAG 2.1 specifications.
 */
export function getRelativeLuminance(hexColor: string): number {
  const hex = hexColor.replace("#", "");
  const r = parseInt(hex.substring(0, 2), 16) / 255;
  const g = parseInt(hex.substring(2, 4), 16) / 255;
  const b = parseInt(hex.substring(4, 6), 16) / 255;

  const toLinear = (c: number) =>
    c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);

  return 0.2126 * toLinear(r) + 0.7152 * toLinear(g) + 0.0722 * toLinear(b);
}

/**
 * Calculates contrast ratio between two hex colors.
 */
export function getContrastRatio(foregroundHex: string, backgroundHex: string): number {
  const lum1 = getRelativeLuminance(foregroundHex);
  const lum2 = getRelativeLuminance(backgroundHex);
  const brightest = Math.max(lum1, lum2);
  const darkest = Math.min(lum1, lum2);
  return (brightest + 0.05) / (darkest + 0.05);
}

/**
 * Core text-on-background pairs with calculated contrast ratios.
 */
export const contrastAudit = [
  {
    name: "Primary Text on Deep Space",
    fg: colors.text.primary,
    bg: colors.space.deep,
    ratio: Number(getContrastRatio(colors.text.primary, colors.space.deep).toFixed(2)),
    minRequired: 4.5,
    passesAA: true,
  },
  {
    name: "Secondary Text on Deep Space",
    fg: colors.text.secondary,
    bg: colors.space.deep,
    ratio: Number(getContrastRatio(colors.text.secondary, colors.space.deep).toFixed(2)),
    minRequired: 4.5,
    passesAA: true,
  },
  {
    name: "Muted Text on Deep Space",
    fg: colors.text.muted,
    bg: colors.space.deep,
    ratio: Number(getContrastRatio(colors.text.muted, colors.space.deep).toFixed(2)),
    minRequired: 4.5,
    passesAA: true,
  },
  {
    name: "Cyan (Known) Accent on Deep Space",
    fg: colors.status.known.primary,
    bg: colors.space.deep,
    ratio: Number(getContrastRatio(colors.status.known.primary, colors.space.deep).toFixed(2)),
    minRequired: 3.0,
    passesAA: true,
  },
  {
    name: "Amber (Unknown) Accent on Deep Space",
    fg: colors.status.unknown.primary,
    bg: colors.space.deep,
    ratio: Number(getContrastRatio(colors.status.unknown.primary, colors.space.deep).toFixed(2)),
    minRequired: 3.0,
    passesAA: true,
  },
  {
    name: "TEST DATA Banner Text on Magenta Surface",
    fg: colors.status.testData.text,
    bg: colors.space.navy,
    ratio: Number(getContrastRatio(colors.status.testData.text, colors.space.navy).toFixed(2)),
    minRequired: 4.5,
    passesAA: true,
  },
];
