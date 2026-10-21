import { QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router";
import { vi } from "vitest";
import { ToastProvider, TooltipProvider } from "@/components/ui";
import { createQueryClient } from "@/lib/queryClient";

export function jsonResponse(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": status >= 400 ? "application/problem+json" : "application/json", ...headers },
  });
}

/** Stub global fetch with a router: (url, init) → Response. */
export function mockFetch(handler: (url: string, init?: RequestInit) => Response | Promise<Response>) {
  const fn = vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
    Promise.resolve(handler(typeof input === "string" ? input : input.toString(), init)),
  );
  vi.stubGlobal("fetch", fn);
  return fn;
}

export function renderWithProviders(ui: ReactElement, { route = "/" }: { route?: string } = {}) {
  const qc = createQueryClient();
  qc.setDefaultOptions({ queries: { retry: false } });
  return {
    qc,
    ...render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={[route]}>
          <TooltipProvider>
            <ToastProvider>{ui}</ToastProvider>
          </TooltipProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    ),
  };
}
