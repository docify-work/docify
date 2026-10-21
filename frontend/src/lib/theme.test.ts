import { beforeEach, describe, expect, it } from "vitest";
import { isAppPath, resolveTheme } from "./theme";

describe("theme rules", () => {
  beforeEach(() => localStorage.clear());

  it("treats only app routes as themeable", () => {
    for (const p of ["/app", "/w/acme", "/w/acme/docs/1", "/account", "/new"]) expect(isAppPath(p)).toBe(true);
    for (const p of ["/", "/login", "/signup", "/privacy", "/invite/x", "/wonder"]) expect(isAppPath(p)).toBe(false);
  });

  it("keeps public pages light whatever the preference", () => {
    expect(resolveTheme("dark", "/")).toBe("light");
    expect(resolveTheme("dark", "/login")).toBe("light");
  });

  it("applies the preference inside the app (light by default)", () => {
    expect(resolveTheme("light", "/w/acme")).toBe("light");
    expect(resolveTheme("dark", "/w/acme")).toBe("dark");
  });
});
