import { describe, expect, it } from "vitest";
import { clockMs, elapsedMs } from "./format.js";

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
