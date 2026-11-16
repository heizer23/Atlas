import { afterEach, describe, expect, it, vi } from "vitest";
import { apiFetch, isApiError } from "../platform-ui/api/client";

function mockFetch(status: number, body: string) {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(body || null, { status })));
}

describe("apiFetch empty bodies", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("treats a 204 as success", async () => {
    mockFetch(204, "");
    expect(isApiError(await apiFetch("/x", { method: "DELETE" }))).toBe(false);
  });

  it("still reports an empty non-2xx response as an error", async () => {
    mockFetch(502, "");
    expect(isApiError(await apiFetch("/x"))).toBe(true);
  });

  it("passes through a JSON ApiError", async () => {
    mockFetch(404, JSON.stringify({ error: { code: "NOT_FOUND", message: "m", request_id: "r" } }));
    expect(isApiError(await apiFetch("/x"))).toBe(true);
  });
});
