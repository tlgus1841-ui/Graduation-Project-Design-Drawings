import { describe, expect, it } from "vitest";
import { clockMs } from "./format.js";

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
