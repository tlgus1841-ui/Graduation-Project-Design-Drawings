import { describe, expect, it } from "vitest";
import { clockMs, elapsedMs, getPortLabel } from "./format.js";

describe("elapsedMs", () => {
  it("returns the gap in whole milliseconds", () => {
    expect(elapsedMs(10.123, 10.2005)).toBe("78 ms");
    expect(elapsedMs(10, 16.0414)).toBe("6,041 ms");
  });

  it("is a dash until both stamps exist", () => {
    expect(elapsedMs(10, null)).toBe("-");
  });
});

describe("clockMs", () => {
  it("formats unix seconds as HH:MM:SS.mmm in local time", () => {
    const ts = new Date(2026, 9, 26, 9, 5, 7, 42).getTime() / 1000;
    expect(clockMs(ts)).toBe("09:05:07.042");
  });

  it("shows a placeholder when there is no timestamp", () => {
    expect(clockMs(null)).toBe("--:--:--.---");
    expect(clockMs(undefined)).toBe("--:--:--.---");
  });
});

describe("getPortLabel", () => {
  it("returns 8-switch port labels for enterprise switches", () => {
    expect(getPortLabel("1:1")).toBe("Core S2");
    expect(getPortLabel("3:1")).toBe("H1 (사무1)");
    expect(getPortLabel("3:2")).toBe("H2 (사무2)");
    expect(getPortLabel("5:1")).toBe("H5 (Web)");
    expect(getPortLabel("7:2")).toBe("H_Patch");
    expect(getPortLabel("8:1")).toBe("H_Sinkhole");
  });

  it("supports legacy 4-switch fallback when isLarge=false", () => {
    expect(getPortLabel("1:1", false)).toBe("H_legit");
    expect(getPortLabel("1:2", false)).toBe("H_attacker");
    expect(getPortLabel("4:1", false)).toBe("H_server");
  });

  it("returns dash for missing or invalid port", () => {
    expect(getPortLabel(null)).toBe("-");
    expect(getPortLabel("99:99")).toBe("-");
  });
});
