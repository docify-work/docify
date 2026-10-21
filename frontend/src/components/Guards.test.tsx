import { screen } from "@testing-library/react";
import { Route, Routes, useLocation } from "react-router";
import { describe, expect, it } from "vitest";
import { jsonResponse, mockFetch, renderWithProviders } from "@/test/utils";
import { RequireAdmin, RequireAuth } from "./Guards";
import { WorkspaceContext, type WorkspaceCtx } from "@/hooks/useWorkspace";

function LoginProbe() {
  const loc = useLocation();
  return <div data-testid="login">{loc.pathname + loc.search}</div>;
}

const ME = {
  id: "u1",
  email: "ganesh@example.com",
  name: "Ganesh",
  avatar_url: null,
  email_verified: true,
  has_password: true,
  identities: [],
  workspaces: [],
};

function app() {
  return (
    <Routes>
      <Route path="/login" element={<LoginProbe />} />
      <Route
        path="/account"
        element={
          <RequireAuth>
            <div>secret account page</div>
          </RequireAuth>
        }
      />
    </Routes>
  );
}

describe("<RequireAuth>", () => {
  it("redirects anonymous users to /login with ?next", async () => {
    const fetch = mockFetch(() => jsonResponse({ status: 401, detail: "Please sign in.", code: "unauthorized" }, 401));
    renderWithProviders(app(), { route: "/account?tab=sessions" });
    expect(await screen.findByTestId("login")).toHaveTextContent("/login?next=%2Faccount%3Ftab%3Dsessions");
    expect(screen.queryByText("secret account page")).not.toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith("/api/me", expect.anything());
  });

  it("renders children for signed-in users", async () => {
    mockFetch(() => jsonResponse(ME));
    renderWithProviders(app(), { route: "/account" });
    expect(await screen.findByText("secret account page")).toBeInTheDocument();
  });

  it("shows a spinner while the session is loading", () => {
    mockFetch(() => new Promise<Response>(() => undefined) as unknown as Response);
    renderWithProviders(app(), { route: "/account" });
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.queryByText("secret account page")).not.toBeInTheDocument();
  });
});

describe("<RequireAdmin>", () => {
  const ctx = (role: "admin" | "member" | null, anonymous = false): WorkspaceCtx => ({
    ws: {
      id: "w1",
      slug: "acme",
      name: "Acme",
      role,
      is_public_demo: false,
      settings: { auto_publish: true, chat_enabled: true },
      created_at: "2026-01-01T00:00:00Z",
      repo_count: 0,
      member_count: 1,
    },
    slug: "acme",
    isAdmin: role === "admin",
    isMember: role !== null,
    isAnonymous: anonymous,
  });

  const page = (c: WorkspaceCtx) => (
    <WorkspaceContext.Provider value={c}>
      <Routes>
        <Route path="/login" element={<LoginProbe />} />
        <Route
          path="/w/acme/settings"
          element={
            <RequireAdmin>
              <div>admin settings</div>
            </RequireAdmin>
          }
        />
      </Routes>
    </WorkspaceContext.Provider>
  );

  it("renders for admins", () => {
    renderWithProviders(page(ctx("admin")), { route: "/w/acme/settings" });
    expect(screen.getByText("admin settings")).toBeInTheDocument();
  });

  it("shows an 'Admins only' notice to members", () => {
    renderWithProviders(page(ctx("member")), { route: "/w/acme/settings" });
    expect(screen.getByText("Admins only")).toBeInTheDocument();
    expect(screen.queryByText("admin settings")).not.toBeInTheDocument();
  });

  it("sends anonymous demo visitors to login", () => {
    renderWithProviders(page(ctx(null, true)), { route: "/w/acme/settings" });
    expect(screen.getByTestId("login")).toHaveTextContent("/login?next=%2Fw%2Facme%2Fsettings");
  });
});
