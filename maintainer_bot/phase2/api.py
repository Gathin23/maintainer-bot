"""The GitHub calls phase 2 needs, on top of the phase-1 client. Tests swap this for a fake with the same methods."""
from __future__ import annotations

import time

from ..live import GitHub


class Api(GitHub):
    # ---- pull requests ----
    def pr(self, n: int) -> dict:
        p = self.get(f"/pulls/{n}")
        return {"number": n, "title": p["title"], "author": p["user"]["login"], "state": p["state"],
                "merged": bool(p.get("merged")), "draft": p.get("draft", False), "head_sha": p["head"]["sha"],
                "head_ref": p["head"]["ref"], "base_ref": p["base"]["ref"],
                "mergeable": p.get("mergeable"), "mergeable_state": p.get("mergeable_state", ""),
                "labels": [l["name"] for l in p.get("labels") or []], "url": p["html_url"]}

    def pr_paths(self, n: int) -> list[str]:
        return [f["filename"] for f in self.paged(f"/pulls/{n}/files", limit=300)]

    def pr_patches(self, n: int, limit: int = 12000) -> str:
        out = []
        for f in self.paged(f"/pulls/{n}/files", limit=300):
            out.append(f"--- {f['filename']}\n{(f.get('patch') or '')[:3000]}")
        return "\n".join(out)[:limit]

    def wait_mergeable(self, n: int, tries: int = 6, delay: float = 5) -> dict:
        """GitHub computes mergeability lazily; poll until it is known."""
        p = self.pr(n)
        for _ in range(tries):
            if p["mergeable"] is not None:
                return p
            time.sleep(delay)
            p = self.pr(n)
        return p

    def open_prs(self) -> list[dict]:
        return [{"number": p["number"], "title": p["title"], "author": p["user"]["login"],
                 "head_sha": p["head"]["sha"], "draft": p.get("draft", False), "head_ref": p["head"]["ref"],
                 "own_branch": (p["head"].get("repo") or {}).get("full_name") == self.repo,
                 "labels": [l["name"] for l in p.get("labels") or []]}
                for p in self.paged("/pulls", limit=1000, state="open")]

    def checks(self, sha: str, ignore: tuple[str, ...] = ()) -> dict:
        """{"state": success|pending|failure|none, "failed": [...], "pending": [...]} over check runs and statuses."""
        runs = self.get(f"/commits/{sha}/check-runs", per_page=100).get("check_runs", [])
        status = self.get(f"/commits/{sha}/status")
        failed, pending, ok = [], [], 0
        for r in runs:
            if r["name"] in ignore:
                continue
            if r["status"] != "completed":
                pending.append(r["name"])
            elif r.get("conclusion") in ("success", "neutral", "skipped"):
                ok += 1
            elif r.get("conclusion") == "action_required":  # a first-time contributor's run waits for approval
                pending.append(f"{r['name']} (needs approval)")
            else:
                failed.append(r["name"])
        for s in status.get("statuses", []):
            if s["context"] in ignore:
                continue
            if s["state"] == "pending":
                pending.append(s["context"])
            elif s["state"] == "success":
                ok += 1
            else:
                failed.append(s["context"])
        state = "failure" if failed else "pending" if pending else "success" if ok else "none"
        return {"state": state, "failed": failed, "pending": pending}

    def merge(self, n: int, sha: str, title: str, message: str = "") -> dict:
        return self.write("PUT", f"/pulls/{n}/merge", {"merge_method": "merge", "sha": sha,
                                                         "commit_title": title, "commit_message": message})

    def create_pr(self, head: str, base: str, title: str, body: str) -> dict:
        r = self.write("POST", "/pulls", {"head": head, "base": base, "title": title, "body": body})
        return {"number": r.get("number"), "url": r.get("html_url", "")}

    def find_pr_for_branch(self, branch: str) -> dict | None:
        owner = self.repo.split("/")[0]
        hits = self.get("/pulls", head=f"{owner}:{branch}", state="open")
        return {"number": hits[0]["number"], "url": hits[0]["html_url"]} if hits else None

    def close_pr(self, n: int) -> None:
        self.write("PATCH", f"/pulls/{n}", {"state": "closed"})

    # ---- issues and comments ----
    def comment(self, n: int, body: str) -> dict:
        r = self.write("POST", f"/issues/{n}/comments", {"body": body})
        return {"id": r.get("id"), "url": r.get("html_url", "")}

    def add_labels(self, n: int, labels: list[str]) -> None:
        self.write("POST", f"/issues/{n}/labels", {"labels": labels})

    def issue(self, n: int) -> dict:
        i = self.get(f"/issues/{n}")
        return {"number": n, "title": i["title"], "body": i.get("body") or "", "state": i["state"],
                "labels": [l["name"] for l in i.get("labels") or []], "author": i["user"]["login"]}

    def issue_comments(self, n: int) -> list[dict]:
        return [{"id": c["id"], "author": c["user"]["login"], "association": c.get("author_association", ""),
                 "body": c.get("body") or "", "created_at": c["created_at"]}
                for c in self.paged(f"/issues/{n}/comments", limit=500)]

    def queue_issues(self, label: str) -> list[dict]:
        return [{"number": i["number"], "title": i["title"], "body": i.get("body") or "",
                 "author": i["user"]["login"], "created_at": i["created_at"]}
                for i in self.paged("/issues", limit=50, state="open", labels=label) if "pull_request" not in i]

    def create_issue(self, title: str, body: str, labels: list[str]) -> dict:
        r = self.write("POST", "/issues", {"title": title, "body": body, "labels": labels})
        return {"number": r.get("number"), "url": r.get("html_url", "")}

    def update_issue(self, n: int, **fields) -> None:
        self.write("PATCH", f"/issues/{n}", fields)

    def sticky(self, n: int, marker: str) -> str:
        for c in self.paged(f"/issues/{n}/comments", limit=300):
            if marker in (c.get("body") or ""):
                return c["body"]
        return ""

    def delete_branch(self, branch: str) -> None:
        if branch.startswith("bot/"):
            try:
                self.write("DELETE", f"/git/refs/heads/{branch}")
            except RuntimeError:
                pass
