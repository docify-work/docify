import { describe, expect, it } from "vitest";
import { NAV_SECTIONS, WORKSPACE_NAV, canSee } from "@/components/layout/nav";
import { githubAvatar, personLabel, SEVERITIES, severityTone } from "./quality";

describe("quality helpers", () => {
  it("serves avatars from the CSP-allowed host only", () => {
    expect(githubAvatar("Ganesh-Mk")).toBe("https://avatars.githubusercontent.com/Ganesh-Mk?size=48");
    expect(githubAvatar(null)).toBeNull();
  });

  it("labels people by login, falling back to the name", () => {
    expect(personLabel({ login: "grace", name: "Grace Hopper" })).toBe("@grace");
    expect(personLabel({ login: null, name: "Grace Hopper" })).toBe("Grace Hopper");
    expect(personLabel({})).toBe("unknown");
  });

  it("maps every severity to a tone", () => {
    for (const s of SEVERITIES) expect(severityTone[s]).toBeTruthy();
  });
});

describe("workspace nav", () => {
  it("groups the new code-health pages and keeps admin pages hidden from members", () => {
    expect(NAV_SECTIONS.find((s) => s.key === "health")?.items.map((i) => i.key)).toEqual(["insights", "checks", "issues"]);
    const visible = WORKSPACE_NAV.filter((n) => canSee(n.access, "member")).map((n) => n.key);
    expect(visible).toContain("issues");
    expect(visible).not.toContain("settings");
    expect(WORKSPACE_NAV.every((n) => n.hint.length > 0)).toBe(true);
  });
});
