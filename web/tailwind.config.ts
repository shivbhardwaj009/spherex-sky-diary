import type { Config } from "tailwindcss";
import { colors, spacing } from "./src/design/tokens";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/design/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        space: colors.space,
        status: colors.status,
        apptext: colors.text,
      },
      borderRadius: spacing.radius,
      zIndex: spacing.zIndex,
      minHeight: {
        touch: spacing.touchMin,
      },
      minWidth: {
        touch: spacing.touchMin,
      },
      boxShadow: {
        glass: colors.glass.shadow,
        glowCyan: "0 0 15px rgba(34, 211, 238, 0.35)",
        glowAmber: "0 0 15px rgba(251, 191, 36, 0.35)",
        glowRose: "0 0 15px rgba(244, 63, 94, 0.40)",
      },
      animation: {
        fadeIn: "fadeIn 0.2s ease-in-out",
        slideUp: "slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1)",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%": { transform: "translateY(100%)" },
          "100%": { transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
