"""An in-memory GitHub for phase 2 tests, optionally backed by a real bare git repo (the E2E simulation).

Merges really happen in the bare repo (a merge commit on main), mergeability is computed with git merge-tree,
and a PR counts as merged once its head is reachable from main, the way GitHub decides it.
"""
from __future__ import annotations

import itertools
import os
import subprocess
import tempfile

from maintainer_bot.live import MARKER


def sticky_body(sha: str, verdict: str, *, reason="Thanks for the PR! Clean list, every package checked.",
                fix="", ask="", question="", priority="p2") -> str:
    words = {"merge": "merge", "merge-with-fix": "merge with a small fix", "rework": "a few changes first",
             "close": "close (kindly)"}
    lines = [f"{MARKER} sha={sha[:12]} v=1 -->"]
    if verdict == "hold":
        lines += ["**maintainer-bot review** · this one needs **a maintainer decision**", "", reason, "",
                  f"Why it goes to a maintainer: {question or 'launcher code'}."]
    else:
        lines += [f"**maintainer-bot review** · suggests **{words[verdict]}** ({priority})", "", reason]
        if fix:
            lines += ["", f"**The small fix:** {fix}"]
        if ask:
            lines += ["", f"**What would help:** {ask}"]
    lines += ["", "<details><summary>Checks</summary>", "", "- **OK**: fine", "", "</details>", "",
              "<sub>Reviewed by maintainer-bot · runs on [0G Private Computer](https://pc.0g.ai)</sub>"]
    return "\n".join(lines)


VERDICT_LABEL = {"merge": "bot-suggests:merge", "merge-with-fix": "bot-suggests:merge-with-fix",
                 "rework": "bot-suggests:rework", "close": "bot-suggests:close", "hold": "needs-maintainer"}


class FakeApi:
    repo = "o/r"

    def __init__(self, bare: str | None = None):
        self.bare = bare
        self.prs: dict[int, dict] = {}
        self.issues: dict[int, dict] = {}
        self.comments: dict[int, list[dict]] = {}
        self.check_state: dict[str, dict] = {}
        self.default_checks = {"state": "success", "failed": [], "pending": []}
        self.calls: list[tuple] = []
        self.deleted: list[str] = []
        self.red_branches: set[str] = set()
        self._ids = itertools.count(1000)
        self._num = itertools.count(500)

    # ---- setup helpers ----
    def add_pr(self, n, *, title, sha, verdict=None, paths=("examples/x/debloat.txt",), labels=(), author="someone",
               sticky_sha=None, draft=False, **sticky_kw):
        lab = list(labels) + ([VERDICT_LABEL[verdict]] if verdict else []) + \
            ([sticky_kw.get("priority", "p2")] if verdict and verdict != "hold" else [])
        self.prs[n] = {"number": n, "title": title, "author": author, "state": "open", "merged": False,
                       "draft": draft, "head_sha": sha, "head_ref": f"feature-{n}", "base_ref": "main",
                       "labels": lab, "paths": list(paths), "mergeable": True, "own_branch": False}
        self.comments[n] = []
        if verdict:
            self.comments[n].append({"id": next(self._ids), "author": "github-actions[bot]", "association": "NONE",
                                     "body": sticky_body(sticky_sha or sha, verdict, **sticky_kw),
                                     "created_at": "2026-10-21T00:00:00Z"})

    def git(self, *args, env=None):
        return subprocess.run(["git", *args], cwd=self.bare, capture_output=True, text=True,
                              env={**os.environ, **(env or {})})

    # ---- Api surface ----
    def _merged(self, sha):
        return self.bare is not None and self.git("merge-base", "--is-ancestor", sha, "main").returncode == 0

    def pr(self, n):
        p = self.prs[n]
        if self.bare and p["state"] == "open" and self._merged(p["head_sha"]) and not p.get("bot"):
            p["state"], p["merged"] = "closed", True  # GitHub marks it merged once main contains the head
        return {k: v for k, v in p.items() if k not in ("paths",)} | {"mergeable_state": "clean",
                                                                     "url": f"https://x/pull/{n}"}

    def pr_paths(self, n):
        return list(self.prs[n]["paths"])

    def pr_patches(self, n):
        return "\n".join(f"--- {p}\n+row" for p in self.prs[n]["paths"])

    def wait_mergeable(self, n):
        p = self.prs[n]
        if self.bare:
            r = self.git("merge-tree", "--write-tree", "main", p["head_sha"])
            p["mergeable"] = r.returncode == 0
        return self.pr(n)

    def open_prs(self):
        return [{"number": n, "title": p["title"], "author": p["author"], "head_sha": p["head_sha"],
                 "draft": p["draft"], "labels": list(p["labels"]), "head_ref": p["head_ref"],
                 "own_branch": p["own_branch"]}
                for n, p in sorted(self.prs.items()) if p["state"] == "open"]

    def checks(self, sha, ignore=()):
        for p in self.prs.values():
            if p.get("bot") and p["head_sha"] == sha and p["head_ref"] in self.red_branches:
                return {"state": "failure", "failed": ["Lists, tools and docs"], "pending": []}
        return self.check_state.get(sha, self.default_checks)

    def merge(self, n, sha, title, message=""):
        p = self.prs[n]
        self.calls.append(("merge", n, sha, title))
        if p["head_sha"] != sha:
            raise RuntimeError("head moved")
        if self.bare:
            with tempfile.TemporaryDirectory() as tmp:
                run = lambda *a: subprocess.run(["git", *a], cwd=tmp, capture_output=True, text=True,  # noqa: E731
                                                env={**os.environ, "FAKE_GH_MERGE": "1",
                                                     "GIT_AUTHOR_NAME": "GitHub", "GIT_AUTHOR_EMAIL": "gh@x",
                                                     "GIT_COMMITTER_NAME": "GitHub", "GIT_COMMITTER_EMAIL": "gh@x"})
                run("clone", "-q", self.bare, ".")
                run("fetch", "-q", "origin", sha)
                msg = [title] + ([message] if message else [])
                r = run("merge", "--no-ff", "-m", "\n\n".join(msg), sha)
                if r.returncode != 0:
                    raise RuntimeError("PUT merge: HTTP 405 not mergeable")
                r = run("push", "-q", "origin", "HEAD:main")
                if r.returncode != 0:
                    raise RuntimeError(r.stderr)
                new = run("rev-parse", "HEAD").stdout.strip()
        else:
            new = "f" * 40
        p["state"], p["merged"] = "closed", True
        return {"sha": new, "merged": True}

    def create_pr(self, head, base, title, body):
        n = next(self._num)
        sha = self.git("rev-parse", f"refs/heads/{head}").stdout.strip() if self.bare else "b" * 40
        self.prs[n] = {"number": n, "title": title, "author": "maintainer-bot[bot]", "state": "open",
                       "merged": False, "draft": False, "head_sha": sha, "head_ref": head, "base_ref": base,
                       "labels": [], "paths": [], "mergeable": True, "own_branch": True, "bot": True, "body": body}
        self.comments[n] = []
        self.calls.append(("create_pr", n, head, title))
        return {"number": n, "url": f"https://x/pull/{n}"}

    def find_pr_for_branch(self, branch):
        for n, p in self.prs.items():
            if p.get("bot") and p["head_ref"] == branch and p["state"] == "open":
                if self.bare:
                    p["head_sha"] = self.git("rev-parse", f"refs/heads/{branch}").stdout.strip()
                return {"number": n, "url": f"https://x/pull/{n}"}
        return None

    def close_pr(self, n):
        self.calls.append(("close", n))
        self.prs[n]["state"] = "closed"

    def delete_branch(self, branch):
        self.deleted.append(branch)

    def comment(self, n, body):
        c = {"id": next(self._ids), "author": "maintainer-bot[bot]", "association": "NONE", "body": body,
             "created_at": "2026-10-22T00:00:00Z"}
        self.comments.setdefault(n, []).append(c)
        self.calls.append(("comment", n))
        return {"id": c["id"], "url": ""}

    def add_labels(self, n, labels):
        self.calls.append(("labels", n, tuple(labels)))
        self.prs[n]["labels"] += [l for l in labels if l not in self.prs[n]["labels"]]

    def issue(self, n):
        i = self.issues[n]
        return {"number": n, "title": i["title"], "body": i["body"], "state": i["state"], "labels": i["labels"],
                "author": i["author"]}

    def issue_comments(self, n):
        return list(self.comments.get(n, []))

    def queue_issues(self, label):
        return [{"number": n, "title": i["title"], "body": i["body"], "author": i["author"], "created_at": ""}
                for n, i in self.issues.items() if label in i["labels"] and i["state"] == "open"]

    def create_issue(self, title, body, labels):
        n = next(self._num)
        self.issues[n] = {"title": title, "body": body, "labels": list(labels), "state": "open",
                          "author": "maintainer-bot[bot]"}
        self.comments[n] = []
        return {"number": n, "url": f"https://x/issues/{n}"}

    def update_issue(self, n, **fields):
        self.issues[n].update(fields)

    def sticky(self, n, marker):
        for c in self.comments.get(n, []):
            if marker in c["body"]:
                return c["body"]
        return ""
