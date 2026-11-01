#!/usr/bin/env python3
"""Create a Docify GitHub App with GitHub's *manifest flow* (Master Doc §9.1, D22).

GitHub has no API to create an App silently — a signed-in owner must click "Create" once.
This script does everything else:

  1. builds the App manifest (permissions, events, callback/setup/webhook URLs)
  2. serves a one-button page on http://localhost:8765
  3. receives GitHub's redirect (?code=...), exchanges it for the App's credentials
  4. writes them into the git-ignored .env (never printed, never committed)

Usage (stdlib only):
  python scripts/create-github-app.py --env dev --webhook-url https://smee.io/<channel>
  python scripts/create-github-app.py --env staging --base-url https://staging.docify.work --webhook-url <lambda url>
  python scripts/create-github-app.py --env prod --base-url https://docify.work --webhook-url <lambda url>
  python scripts/create-github-app.py --env ci-bot          # docify-ci-bot (D34): contents write, no webhook

Where the credentials go (never printed, never committed):
  dev      -> .env (local backend)
  staging/prod -> .secrets/<env>/github/{app_private_key,client_secret,webhook_secret}
              (git-ignored; feed them to SSM with scripts/init-params.sh --from-dir .secrets).
              Public ids (app id, slug, client id) are printed for deploy/values/<env>.yaml.
  ci-bot   -> .secrets/ci-bot/{client_id,private_key.pem} -> GitHub secrets CI_BOT_APP_ID / CI_BOT_PRIVATE_KEY
"""

from __future__ import annotations

import argparse
import html
import json
import secrets
import threading
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

PORT = 8765
ROOT = Path(__file__).resolve().parents[1]
STATE = secrets.token_urlsafe(16)


def manifest(env: str, base_url: str, webhook_url: str, owner: str) -> dict:
    if env == "ci-bot":
        # Release bot (D34): pushes the image-tag bump commits to main (ruleset bypass actor).
        return {
            "name": f"docify-ci-bot ({owner})"[:34],
            "url": "https://github.com/docify-work/docify",
            "description": "Docify release bot: commits image-tag bumps to main.",
            "redirect_url": f"http://localhost:{PORT}/callback",
            "public": False,
            "default_permissions": {"contents": "write", "metadata": "read"},
            "default_events": [],
        }
    name = {"dev": "Docify Dev", "staging": "Docify Staging", "prod": "Docify"}[env]
    return {
        # App names are global on GitHub; suffix with the owner to avoid clashes.
        "name": f"{name} ({owner})"[:34],
        "url": "https://github.com/docify-work/docify",
        "description": "Docify keeps documentation for your repositories up to date with AI.",
        "hook_attributes": {"url": webhook_url, "active": True},
        "redirect_url": f"http://localhost:{PORT}/callback",
        "callback_urls": [f"{base_url}/api/auth/github/callback"],
        "setup_url": f"{base_url}/api/github/setup",
        "setup_on_update": True,
        # OFF: with it ON GitHub ignores the Setup URL (§9.1).
        "request_oauth_on_install": False,
        # D59: the prod App is public (any account can install it; AI spend is capped by
        # AI_DAILY_BUDGET_USD / AI_WS_MONTHLY_BUDGET_USD). dev + staging stay private (D21).
        "public": env == "prod",
        "default_permissions": {
            "contents": "read",
            "metadata": "read",
            "pull_requests": "read",
            "emails": "read",
        },
        "default_events": ["push", "repository"],
    }


PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Create Docify GitHub App</title>
<style>body{{font:15px system-ui;max-width:560px;margin:80px auto;color:#1f2328}}
button{{font:600 15px system-ui;background:#4f46e5;color:#fff;border:0;border-radius:8px;padding:12px 20px;cursor:pointer}}
code{{background:#f2f4f7;padding:2px 6px;border-radius:4px}} .muted{{color:#656d76;font-size:13px}}</style></head>
<body><h2>Create “{name}”</h2>
<p>Make sure you're signed in to GitHub as <b>{owner}</b>, then click the button and press
<b>Create GitHub App</b> on the GitHub page.</p>
<form action="https://github.com/settings/apps/new?state={state}" method="post">
<input type="hidden" name="manifest" value="{manifest}"><button type="submit">Continue on GitHub →</button></form>
<p class="muted">{perms}</p></body></html>"""

DONE = """<!doctype html><html><head><meta charset="utf-8"><title>Done</title>
<style>body{{font:15px system-ui;max-width:560px;margin:80px auto;color:#1f2328}}</style></head>
<body><h2>✅ {title}</h2><p>{body}</p><p>You can close this tab and go back to Claude.</p></body></html>"""


def set_env_values(values: dict[str, str]) -> None:
    """Upsert KEY=value lines in .env (git-ignored). Multi-line values are stored with \\n escapes."""
    path = ROOT / ".env"
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    keys = set(values)
    kept = [ln for ln in lines if ln.split("=", 1)[0].strip() not in keys]
    for k, v in values.items():
        kept.append(f'{k}="{v.replace(chr(10), chr(92) + "n")}"')
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def write_secret_files(folder: Path, files: dict[str, str]) -> None:
    """Write each value to folder/<name> (git-ignored .secrets/). Never printed."""
    for rel, value in files.items():
        f = folder / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(value, encoding="utf-8", newline="\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", choices=["dev", "staging", "prod", "ci-bot"], default="dev")
    ap.add_argument("--base-url", default="http://localhost:5173", help="where the SPA + /api are served")
    ap.add_argument("--webhook-url", default="", help="smee.io channel (dev) or the env's Lambda URL (not for ci-bot)")
    ap.add_argument("--owner", default="docify-work")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    if args.env != "ci-bot" and not args.webhook_url:
        ap.error("--webhook-url is required for dev/staging/prod")

    m = manifest(args.env, args.base_url.rstrip("/"), args.webhook_url, args.owner)
    perms = ("Permissions: contents <b>write</b>, metadata read. No webhook, no events. Only on this account."
             if args.env == "ci-bot" else
             "Permissions: contents, metadata, pull requests, email addresses — all <b>read-only</b>.<br>"
             "Events: push, repository. Installable only on this account.")
    page = PAGE.format(name=html.escape(m["name"]), owner=html.escape(args.owner), state=STATE,
                       manifest=html.escape(json.dumps(m)), perms=perms)
    done = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a: object) -> None:  # keep the terminal quiet
            pass

        def _send(self, body: str, status: int = 200) -> None:
            data = body.encode()
            self.send_response(status)
            self.send_header("content-type", "text/html; charset=utf-8")
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            url = urllib.parse.urlparse(self.path)
            if url.path == "/":
                self._send(page)
                return
            if url.path != "/callback":
                self._send("not found", 404)
                return
            q = urllib.parse.parse_qs(url.query)
            if q.get("state", [""])[0] != STATE or "code" not in q:
                self._send(DONE.format(title="Something went wrong", body="State mismatch — run the script again."),
                           400)
                return
            req = urllib.request.Request(
                f"https://api.github.com/app-manifests/{q['code'][0]}/conversions", method="POST",
                headers={"Accept": "application/vnd.github+json", "User-Agent": "docify-setup"})
            with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - fixed https URL
                app = json.load(resp)
            if args.env == "dev":
                set_env_values({
                    "GITHUB_APP_ID": str(app["id"]),
                    "GITHUB_APP_SLUG": app["slug"],
                    "GITHUB_CLIENT_ID": app["client_id"],
                    "GITHUB_CLIENT_SECRET": app["client_secret"],
                    "GITHUB_WEBHOOK_SECRET": app.get("webhook_secret") or "",
                    "GITHUB_APP_PRIVATE_KEY": app["pem"],
                })
                where = ".env"
            elif args.env == "ci-bot":
                write_secret_files(ROOT / ".secrets" / "ci-bot", {
                    "client_id": app["client_id"],
                    "private_key.pem": app["pem"],
                })
                where = ".secrets/ci-bot/"
            else:
                write_secret_files(ROOT / ".secrets" / args.env / "github", {
                    "app_private_key": app["pem"],
                    "client_secret": app["client_secret"],
                    "webhook_secret": app.get("webhook_secret") or "",
                })
                where = f".secrets/{args.env}/github/"
            # Ids below are public (they appear in install URLs); secrets are only in the files.
            print(f"Created GitHub App '{app['name']}' (slug {app['slug']}, id {app['id']}, "
                  f"client id {app['client_id']}).")
            print(f"Credentials saved to {where} (git-ignored). Install it here:")
            print(f"  {app['html_url']}/installations/new")
            self._send(DONE.format(title=f"“{html.escape(app['name'])}” created",
                                   body=f"Credentials were saved to your local <code>{html.escape(where)}</code>."))
            done.set()

    server = HTTPServer(("127.0.0.1", PORT), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"Open http://localhost:{PORT} and click the button (signed in as {args.owner}).")
    if not args.no_browser:
        webbrowser.open(f"http://localhost:{PORT}")
    done.wait()
    server.shutdown()


if __name__ == "__main__":
    main()
