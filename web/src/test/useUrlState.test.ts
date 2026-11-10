import { describe, it, expect } from "vitest";
import { parseUrlParams, serializeUrlParams } from "@/lib/useUrlState";

describe("URL State Synchronization & Parsing", () => {
  it("parses valid coordinates and parameters from search string", () => {
    const search = "?ra=75.5000&dec=-15.2500&fov=0.500&epoch=epoch_03&object=mov_002";
    const state = parseUrlParams(search);

    expect(state.ra).toBe(75.5);
    expect(state.dec).toBe(-15.25);
    expect(state.fov).toBe(0.5);
    expect(state.epoch).toBe("epoch_03");
    expect(state.object).toBe("mov_002");
  });

  it("applies safe defaults on empty or invalid inputs", () => {
    const state = parseUrlParams("");
    expect(state.ra).toBe(60.0);
    expect(state.dec).toBe(20.0);
    expect(state.fov).toBe(0.2);
    expect(state.epoch).toBe("epoch_01");
    expect(state.object).toBeNull();
  });

  it("clamps coordinates within physical boundaries (0-360 RA, -90-90 Dec)", () => {
    const state = parseUrlParams("?ra=400&dec=-120&fov=-1");
    expect(state.ra).toBe(360.0);
    expect(state.dec).toBe(-90.0);
    expect(state.fov).toBe(0.2); // Negative FOV falls back to default 0.2
  });

  it("round-trips state cleanly into a query string", () => {
    const inputState = {
      ra: 133.7951,
      dec: -7.2452,
      fov: 0.15,
      epoch: "epoch_04",
      object: "wise_0855",
    };

    const query = serializeUrlParams(inputState);
    const parsed = parseUrlParams(`?${query}`);

    expect(parsed.ra).toBeCloseTo(inputState.ra, 3);
    expect(parsed.dec).toBeCloseTo(inputState.dec, 3);
    expect(parsed.fov).toBeCloseTo(inputState.fov, 2);
    expect(parsed.epoch).toBe(inputState.epoch);
    expect(parsed.object).toBe(inputState.object);
  });
});
