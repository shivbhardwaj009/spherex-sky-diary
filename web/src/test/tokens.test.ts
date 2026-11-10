import { describe, it, expect } from "vitest";
import { contrastAudit, getContrastRatio, colors } from "@/design/tokens";

describe("Design System Tokens & Accessibility", () => {
  it("all defined core text-background token pairs meet WCAG AA contrast standards", () => {
    for (const audit of contrastAudit) {
      expect(
        audit.ratio,
        `Token pair '${audit.name}' failed contrast check: ${audit.ratio}:1 < ${audit.minRequired}:1`
      ).toBeGreaterThanOrEqual(audit.minRequired);
    }
  });

  it("body text on deep space background meets WCAG AA (>= 4.5:1)", () => {
    const primaryRatio = getContrastRatio(colors.text.primary, colors.space.deep);
    const secondaryRatio = getContrastRatio(colors.text.secondary, colors.space.deep);
    const mutedRatio = getContrastRatio(colors.text.muted, colors.space.deep);

    expect(primaryRatio).toBeGreaterThanOrEqual(4.5);
    expect(secondaryRatio).toBeGreaterThanOrEqual(4.5);
    expect(mutedRatio).toBeGreaterThanOrEqual(4.5);
  });

  it("status accents on deep space background meet WCAG AA UI threshold (>= 3.0:1)", () => {
    const cyanRatio = getContrastRatio(colors.status.known.primary, colors.space.deep);
    const amberRatio = getContrastRatio(colors.status.unknown.primary, colors.space.deep);
    const roseRatio = getContrastRatio(colors.status.testData.primary, colors.space.deep);

    expect(cyanRatio).toBeGreaterThanOrEqual(3.0);
    expect(amberRatio).toBeGreaterThanOrEqual(3.0);
    expect(roseRatio).toBeGreaterThanOrEqual(3.0);
  });
});
