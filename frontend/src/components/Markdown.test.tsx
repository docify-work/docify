import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { parseHighlights } from "@/lib/highlight";
import { linkCitations, safeUrl } from "@/lib/markdown";
import { Markdown } from "./Markdown";

describe("<Markdown> sanitisation", () => {
  it("never renders images", () => {
    const { container } = render(
      <Markdown>
        {
          "Logo: ![alt text](https://example.com/x.png) and ![ref][r]\n\n[r]: https://example.com/y.png"
        }
      </Markdown>,
    );
    expect(container.querySelector("img")).toBeNull();
  });

  it("skips raw HTML entirely", () => {
    const { container } = render(
      <Markdown>
        {
          'Hi <script>alert(1)</script><img src=x onerror=alert(1)> <b>bold</b>\n\n<div onclick="x()">block</div>'
        }
      </Markdown>,
    );
    expect(container.querySelector("script, img, b, div[onclick]")).toBeNull();
    expect(container.innerHTML).not.toMatch(/onerror|onclick|<script/i);
  });

  it("drops non-http(s) link targets", () => {
    render(
      <Markdown>
        {
          "[js](javascript:alert(1)) [data](data:text/html;base64,xx) [mail](mailto:a@b.c) [vb](vbscript:x)"
        }
      </Markdown>,
    );
    for (const name of ["js", "data", "mail", "vb"]) {
      expect(screen.getByText(name).closest("a")).toBeNull();
    }
  });

  it("opens external links in a new tab with safe rel", () => {
    render(
      <Markdown>
        {"[gh](https://github.com/acme/api/blob/abc/x.py#L1-L9)"}
      </Markdown>,
    );
    const a = screen.getByRole("link", { name: "gh" });
    expect(a).toHaveAttribute(
      "href",
      "https://github.com/acme/api/blob/abc/x.py#L1-L9",
    );
    expect(a).toHaveAttribute("target", "_blank");
    expect(a).toHaveAttribute("rel", "nofollow noopener noreferrer");
  });

  it("keeps relative links in the same tab (still with rel)", () => {
    render(
      <Markdown>
        {"[setup](./setup.md) [anchor](#install) [abs](/w/acme)"}
      </Markdown>,
    );
    for (const name of ["setup", "anchor", "abs"]) {
      const a = screen.getByRole("link", { name });
      expect(a).not.toHaveAttribute("target");
      expect(a).toHaveAttribute("rel", "nofollow noopener noreferrer");
    }
  });

  it("renders GFM tables and code blocks", () => {
    const { container } = render(
      <Markdown>
        {"| a | b |\n|---|---|\n| 1 | 2 |\n\n```py\nprint(1)\n```"}
      </Markdown>,
    );
    expect(container.querySelector("table")).not.toBeNull();
    expect(container.querySelector("pre code")?.textContent).toContain(
      "print(1)",
    );
  });
});

describe("markdown helpers", () => {
  it("safeUrl allows only http(s) and relative URLs", () => {
    expect(safeUrl("https://x.y/z")).toBe("https://x.y/z");
    expect(safeUrl("HTTP://x.y")).toBe("HTTP://x.y");
    expect(safeUrl("/w/acme")).toBe("/w/acme");
    expect(safeUrl("#top")).toBe("#top");
    expect(safeUrl("docs/a.md")).toBe("docs/a.md");
    expect(safeUrl(" javascript:alert(1)")).toBe("");
    expect(safeUrl("JaVaScRiPt:alert(1)")).toBe("");
    expect(safeUrl("data:text/html,x")).toBe("");
    expect(safeUrl("//evil.example/x")).toBe("");
  });

  it("links [n] citation markers to sources, but not inside code fences", () => {
    const sources = [
      {
        n: 1,
        kind: "code" as const,
        repo: "acme/api",
        path: "a.py",
        start_line: 1,
        end_line: 5,
        commit_sha: "abc",
        url: "https://github.com/acme/api/blob/abc/a.py#L1-L5",
      },
    ];
    const out = linkCitations("See [1] and [2].\n\n```\narr[1]\n```", sources);
    expect(out).toContain(
      '[1](https://github.com/acme/api/blob/abc/a.py#L1-L5 "docify-cite")',
    );
    expect(out).toContain("[2]");
    expect(out).toContain("arr[1]\n```");
    render(<Markdown>{out}</Markdown>);
    const cite = screen.getByRole("link", { name: "1" });
    expect(cite).toHaveClass("md-cite");
    expect(cite).toHaveAttribute("target", "_blank");
  });

  it("turns ts_headline <b> markers into highlight segments without HTML", () => {
    expect(parseHighlights("use <b>session</b> cookie <i>x</i>")).toEqual([
      { text: "use ", hit: false },
      { text: "session", hit: true },
      { text: " cookie x", hit: false },
    ]);
  });

  it("supports the plain-text «…» markers the API sends", () => {
    expect(parseHighlights("hash «password» with «bcrypt»")).toEqual([
      { text: "hash ", hit: false },
      { text: "password", hit: true },
      { text: " with ", hit: false },
      { text: "bcrypt", hit: true },
    ]);
  });
});
