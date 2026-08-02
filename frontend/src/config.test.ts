import { afterEach, describe, expect, it, vi } from "vitest";

describe("frontend config", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it("uses same-origin API calls when VITE_API_BASE is unset", async () => {
    const { DEFAULT_API_BASE } = await import("./config");

    expect(DEFAULT_API_BASE).toBe("");
  });

  it("uses VITE_API_BASE when local development provides one", async () => {
    vi.stubEnv("VITE_API_BASE", "http://127.0.0.1:8000");
    vi.resetModules();

    const { DEFAULT_API_BASE } = await import("./config");

    expect(DEFAULT_API_BASE).toBe("http://127.0.0.1:8000");
  });
});
