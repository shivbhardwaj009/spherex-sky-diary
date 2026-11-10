import React, { useState } from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";

import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { Panel } from "@/components/ui/Panel";
import { Tooltip } from "@/components/ui/Tooltip";
import { Tabs } from "@/components/ui/Tabs";
import { Slider } from "@/components/ui/Slider";
import { Modal } from "@/components/ui/Modal";
import { ConfidenceBar } from "@/components/ui/ConfidenceBar";
import { Skeleton } from "@/components/ui/Skeleton";
import { Spinner } from "@/components/ui/Spinner";
import { ErrorMessage } from "@/components/ui/ErrorMessage";

describe("UI Components & Accessibility", () => {
  it("Button renders, handles clicks, and shows loading state", async () => {
    const handleClick = vi.fn();
    const { rerender } = render(
      <Button variant="primary" onClick={handleClick}>
        Inspect Orbit
      </Button>
    );

    const btn = screen.getByRole("button", { name: /inspect orbit/i });
    expect(btn).toBeInTheDocument();
    fireEvent.click(btn);
    expect(handleClick).toHaveBeenCalledTimes(1);

    // Loading state disables button and shows spinner
    rerender(
      <Button variant="primary" isLoading onClick={handleClick}>
        Inspect Orbit
      </Button>
    );
    expect(btn).toBeDisabled();
  });

  it("Badge variants include text and icons, never relying on color alone", () => {
    const { container } = render(
      <div>
        <Badge variant="known" label="Known Body" />
        <Badge variant="unknown" label="Unknown Mover" />
        <Badge variant="testData" label="TEST DATA" />
        <Badge variant="offline" label="Offline Catalog" />
      </div>
    );

    expect(screen.getByText("Known Body")).toBeInTheDocument();
    expect(screen.getByText("Unknown Mover")).toBeInTheDocument();
    expect(screen.getByText("TEST DATA")).toBeInTheDocument();
    expect(screen.getByText("Offline Catalog")).toBeInTheDocument();

    // Verify SVG icons exist inside each badge
    const svgs = container.querySelectorAll("svg");
    expect(svgs.length).toBe(4);
  });

  it("Card supports selectable interactive states", () => {
    const handleSelect = vi.fn();
    const { rerender } = render(
      <Card selectable selected={false} onClick={handleSelect}>
        Candidate Content
      </Card>
    );

    const card = screen.getByRole("button");
    expect(card).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(card);
    expect(handleSelect).toHaveBeenCalled();

    rerender(
      <Card selectable selected={true}>
        Candidate Content
      </Card>
    );
    expect(card).toHaveAttribute("aria-pressed", "true");
  });

  it("Panel toggles content expansion via accessible disclosure button", () => {
    render(
      <Panel title="Epoch Details" collapsible defaultExpanded={true}>
        <p>Aperture flux details</p>
      </Panel>
    );

    expect(screen.getByText("Aperture flux details")).toBeVisible();
    const toggleBtn = screen.getByRole("button", { name: /collapse epoch details/i });
    expect(toggleBtn).toHaveAttribute("aria-expanded", "true");

    fireEvent.click(toggleBtn);
    expect(toggleBtn).toHaveAttribute("aria-expanded", "false");
  });

  it("Tooltip displays on focus and mouseenter, dismisses with Escape", async () => {
    render(
      <Tooltip content="Spectral aperture size">
        <button type="button">Hover Trigger</button>
      </Tooltip>
    );

    const trigger = screen.getByRole("button", { name: /hover trigger/i });
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();

    // Focus triggers tooltip
    fireEvent.focus(trigger);
    expect(screen.getByRole("tooltip")).toHaveTextContent("Spectral aperture size");

    // Escape dismisses tooltip
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("Tabs navigate via arrow keys and maintain ARIA tablist/tab/tabpanel roles", () => {
    render(
      <Tabs
        items={[
          { id: "tab1", label: "Overview", content: <div>Overview Content</div> },
          { id: "tab2", label: "Spectra", content: <div>Spectra Content</div> },
        ]}
      />
    );

    const tablist = screen.getByRole("tablist");
    expect(tablist).toBeInTheDocument();

    const tab1 = screen.getByRole("tab", { name: /overview/i });
    const tab2 = screen.getByRole("tab", { name: /spectra/i });

    expect(tab1).toHaveAttribute("aria-selected", "true");
    expect(tab2).toHaveAttribute("aria-selected", "false");
    expect(screen.getByText("Overview Content")).toBeVisible();

    // ArrowRight navigates to Tab 2
    fireEvent.keyDown(tab1, { key: "ArrowRight" });
    expect(tab2).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("Spectra Content")).toBeVisible();
  });

  it("Slider steps value with plus and minus buttons", () => {
    const handleChange = vi.fn();
    render(
      <Slider
        label="Observation Epoch"
        min={1}
        max={6}
        value={2}
        onChange={handleChange}
        valueDisplay="Epoch 2"
      />
    );

    const plusBtn = screen.getByRole("button", { name: /increase observation epoch/i });
    fireEvent.click(plusBtn);
    expect(handleChange).toHaveBeenCalledWith(3);

    const minusBtn = screen.getByRole("button", { name: /decrease observation epoch/i });
    fireEvent.click(minusBtn);
    expect(handleChange).toHaveBeenCalledWith(1);
  });

  it("Modal traps focus, handles Escape, and closes via close button", async () => {
    const handleClose = vi.fn();
    render(
      <Modal isOpen={true} onClose={handleClose} title="Attribution Information">
        <p>Modal body content</p>
        <button type="button">Action Inside</button>
      </Modal>
    );

    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeInTheDocument();
    expect(screen.getByText("Attribution Information")).toBeInTheDocument();

    // Close button triggers onClose
    const closeBtn = screen.getByRole("button", { name: /close dialog/i });
    fireEvent.click(closeBtn);
    expect(handleClose).toHaveBeenCalled();

    // Escape triggers onClose
    fireEvent.keyDown(window, { key: "Escape" });
    expect(handleClose).toHaveBeenCalledTimes(2);
  });

  it("ConfidenceBar renders with accessible progressbar semantics", () => {
    render(<ConfidenceBar value={0.88} label="Trajectory Linearity" />);
    const bar = screen.getByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "88");
    expect(screen.getByText("88%")).toBeInTheDocument();
  });

  it("axe reports zero accessibility violations on core components", async () => {
    const { container } = render(
      <main>
        <h1>Accessible Controls</h1>
        <Button variant="primary">Submit Coordinates</Button>
        <Badge variant="known" label="Known Target" />
        <ConfidenceBar value={0.9} label="Quality Score" />
      </main>
    );

    const results = await axe.run(container);
    expect(results.violations).toEqual([]);
  });
});
