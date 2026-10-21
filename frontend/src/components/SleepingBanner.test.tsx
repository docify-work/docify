import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SLEEPING_MESSAGE, probeBackend } from "@/lib/health";
import { mockFetch } from "@/test/utils";
import { SleepingBanner } from "./SleepingBanner";

describe("probeBackend", () => {
  it.each([502, 503, 504])("treats %i as sleeping", async (status) => {
    const f = vi.fn(() => Promise.resolve(new Response("", { status })));
    await expect(probeBackend(4000, f)).resolves.toBe("sleeping");
  });

  it("treats 200 (and other statuses) as awake", async () => {
    await expect(probeBackend(4000, vi.fn(() => Promise.resolve(new Response("{}", { status: 200 }))))).resolves.toBe("awake");
    await expect(probeBackend(4000, vi.fn(() => Promise.resolve(new Response("", { status: 500 }))))).resolves.toBe("awake");
  });

  it("treats network errors as sleeping", async () => {
    await expect(probeBackend(4000, vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))))).resolves.toBe("sleeping");
  });

  it("times out after the given delay and aborts the request", async () => {
    vi.useFakeTimers();
    try {
      let signal: AbortSignal | undefined;
      const hang = vi.fn(
        (_url: RequestInfo | URL, init?: RequestInit) =>
          new Promise<Response>((_resolve, reject) => {
            signal = init?.signal ?? undefined;
            signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
          }),
      );
      const result = probeBackend(4000, hang);
      await vi.advanceTimersByTimeAsync(3999);
      expect(signal?.aborted).toBe(false);
      await vi.advanceTimersByTimeAsync(1);
      await expect(result).resolves.toBe("sleeping");
      expect(signal?.aborted).toBe(true);
      expect(hang).toHaveBeenCalledWith("/api/health", expect.objectContaining({ signal }));
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("<SleepingBanner>", () => {
  it("shows the sleeping message when the backend is down", async () => {
    mockFetch(() => new Response("", { status: 503 }));
    render(<SleepingBanner />);
    expect(await screen.findByText(SLEEPING_MESSAGE)).toBeInTheDocument();
    expect(SLEEPING_MESSAGE).toMatch(/sleeping.*5 minutes/);
  });

  it("stays hidden when the backend is awake", async () => {
    const f = mockFetch(() => new Response('{"status":"ok"}', { status: 200 }));
    render(<SleepingBanner />);
    await vi.waitFor(() => expect(f).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 20));
    expect(screen.queryByText(SLEEPING_MESSAGE)).not.toBeInTheDocument();
  });
});
