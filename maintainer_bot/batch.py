"""Batch context (deterministic, no AI): what else was going on when the maintainer decided this PR.

A maintainer decides PRs as a group ("duplicates #545", "#552 already does this", "pick one of these two").
This module gives the decision step the same view, using only what existed at decision time:
  - other PRs open at that moment that touch the same files (shared table files like README.md excluded)
  - whether main at decision time already contains most of what this PR adds ("already on main")
"""
from __future__ import annotations

import re
import subprocess
from functools import lru_cache

# files almost every PR touches; overlap on them says nothing about competing work
SHARED_TABLE_FILES = {"README.md", "examples/README.md", "SHOWCASE.md", "README.zh-CN.md", "docs/PRESS.md",
                      "COVERAGE.md", "CHANGELOG.md"}
LOCALE_STRINGS = re.compile(r"^launcher/app/src/main/res/values-[^/]+/strings\.xml$")


def _meaningful(path: str) -> bool:
    return path not in SHARED_TABLE_FILES and not LOCALE_STRINGS.match(path)


def open_overlaps(target: dict, rows: list[dict], files_by_pr: dict[int, list[str]], titles: dict[int, str],
                  limit: int = 6) -> list[dict]:
    """PRs open when the target was decided (created before, decided after) that touch the same files."""
    mine = {p for p in files_by_pr.get(target["pr"], []) if _meaningful(p)}
    if not mine:
        return []
    out = []
    for o in rows:
        if o["pr"] == target["pr"]:
            continue
        if not (o["created_at"] < target["decided_at"] and o["decided_at"] > target["created_at"]):
            continue
        shared = sorted(mine & {p for p in files_by_pr.get(o["pr"], []) if _meaningful(p)})
        if shared:
            out.append({"pr": o["pr"], "title": titles.get(o["pr"], "")[:90], "shared_files": shared[:4],
                        "decided_before_this": o["decided_at"] < target["decided_at"]})
    out.sort(key=lambda x: -len(x["shared_files"]))
    return out[:limit]


@lru_cache(maxsize=4096)
def _blob(git_dir: str, commit: str, path: str) -> str | None:
    r = subprocess.run(["git", "-C", git_dir, "show", f"{commit}:{path}"], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


@lru_cache(maxsize=512)
def commit_at(git_dir: str, when: str, branch: str = "origin/main") -> str:
    r = subprocess.run(["git", "-C", git_dir, "rev-list", "-1", "--first-parent", f"--before={when}", branch],
                       capture_output=True, text=True)
    return r.stdout.strip()


def already_on_main(files: list[dict], git_dir: str, commit: str, min_lines: int = 4) -> dict:
    """How much of what this PR adds is already in main at `commit` (a superseded or duplicate change).

    Looks at added lines longer than 12 characters in files other than the shared tables; returns the share
    found verbatim in main's copy of the same file, per file and overall.
    """
    if not commit:
        return {}
    total = found = 0
    per = {}
    for f in files:
        path = f["path"]
        if not _meaningful(path) or f.get("binary"):
            continue
        added = [l[1:].strip() for l in (f.get("patch") or "").splitlines()
                 if l.startswith("+") and not l.startswith("+++") and len(l.strip()) > 13]
        if len(added) < 1:
            continue
        main_text = _blob(git_dir, commit, path)
        if main_text is None:
            total += len(added)
            continue
        hit = sum(1 for a in added if a in main_text)
        total += len(added)
        found += hit
        if hit:
            per[path] = round(hit / len(added), 2)
    if total < min_lines:
        return {}
    share = round(found / total, 2)
    # partial overlap is noise (code lines repeat across files); only a near-complete match means the change
    # (or the same list) has already landed another way
    return {"share_of_added_lines_already_on_main": share, "files_mostly_on_main":
            sorted(p for p, s in per.items() if s >= 0.8)[:5]} if share >= 0.8 else {}
