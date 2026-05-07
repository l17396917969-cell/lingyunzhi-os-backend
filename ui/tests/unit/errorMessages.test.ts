import { describe, it, expect } from "vitest";
import { translateError } from "../../src/api/errorMessages";

describe("translateError", () => {
  it("returns zh-CN for known codes", () => {
    expect(translateError("UNAUTHORIZED")).toBe("身份验证失败，请重新登录");
    expect(translateError("FORBIDDEN")).toMatch(/权限/);
    expect(translateError("STALE_STAGING")).toMatch(/暂存区/);
    expect(translateError("TURN_IN_FLIGHT")).toMatch(/进行中/);
  });
  it("falls back for unknown codes", () => {
    expect(translateError("WHATEVER")).toBe("未知错误（WHATEVER）");
  });
  it("handles undefined", () => {
    expect(translateError(undefined)).toBe("未知错误");
  });
});
