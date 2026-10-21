"""Turn a GitHub webhook into a small queue message, or None if we don't care (Master Doc §9.4).

Pure standard library: copied verbatim into the Lambda. The worker re-reads current
state from GitHub anyway (rule 8), so the message only needs ids and hints.
"""

from __future__ import annotations

from typing import Any

FORWARDED_INSTALLATION_ACTIONS = {"created", "deleted", "suspend", "unsuspend", "new_permissions_accepted"}
FORWARDED_REPOSITORY_ACTIONS = {
    "renamed", "transferred", "edited", "archived", "unarchived", "privatized", "publicized", "deleted",
}
MAX_MESSAGE_BYTES = 8 * 1024


def normalise(event: str, delivery_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    action = payload.get("action")
    installation = payload.get("installation") or {}
    repo = payload.get("repository") or {}
    msg: dict[str, Any] = {
        "v": 1, "kind": "github_event", "delivery_id": str(delivery_id)[:100], "event": event,
        "action": action, "installation_id": installation.get("id"), "repo_id": repo.get("id"),
    }

    if event == "push":
        default_branch = repo.get("default_branch")
        if not default_branch or payload.get("ref") != f"refs/heads/{default_branch}" or payload.get("deleted"):
            return None
        msg.update({
            "ref": payload.get("ref"), "before": payload.get("before"), "after": payload.get("after"),
            "default_branch": default_branch, "forced": bool(payload.get("forced")), "deleted": False,
        })
        return msg

    if event == "installation":
        if action not in FORWARDED_INSTALLATION_ACTIONS:
            return None
        return msg

    if event == "installation_repositories":
        if action not in ("added", "removed"):
            return None
        msg["repos_added"] = [r.get("id") for r in payload.get("repositories_added") or []][:200]
        msg["repos_removed"] = [r.get("id") for r in payload.get("repositories_removed") or []][:200]
        return msg

    if event == "repository":
        if action not in FORWARDED_REPOSITORY_ACTIONS:
            return None
        if action == "edited":
            changes = payload.get("changes") or {}
            if "default_branch" not in changes:
                return None
            msg["default_branch"] = repo.get("default_branch")
        msg["full_name"] = repo.get("full_name")
        return msg

    return None
