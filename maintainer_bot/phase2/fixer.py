"""The small fix for merge-with-fix: edits proposed through the 0G router, checked here before anything runs.

Reuses phase 1's propose_edits tool (exact search/replace pairs; the model never runs code). The checks:
each search string occurs exactly once in the file it edits, at most MAX_CHANGED_LINES changed lines in total,
and no edits to sensitive paths (workflows, the bot's rules, the prompt's safety rules, disable/restore).
"""
from __future__ import annotations

import re
from typing import Callable

from .. import fix as fix_mod

MAX_CHANGED_LINES = fix_mod.MAX_CHANGED_LINES
SENSITIVE = fix_mod.SENSITIVE + (".opencodereview/",)

Reader = Callable[[str], "str | None"]


def needles(fix_text: str, paths: list[str]) -> list[str]:
    """Words worth finding in big files: backticked and quoted bits, folder names and their brand word
    (a missing README row has no folder name to find, but its neighbours share the brand)."""
    out = re.findall(r"`([^`]{3,80})`", fix_text) + re.findall(r"\"([^\"]{3,80})\"", fix_text)
    slugs = re.findall(r"\b[a-z0-9]+(?:-[a-z0-9]+)+\b", fix_text)
    for p in paths:
        m = re.match(r"^examples/([^/]+)/", p)
        if m:
            slugs.append(m.group(1))
    for sl in slugs:
        out.append(sl)
        if len(sl.split("-")[0]) >= 3:
            out.append(sl.split("-")[0])
    return [x for x in dict.fromkeys(out) if x]


def context(read: Reader, fix_text: str, paths: list[str], limit_files: int = 6) -> dict[str, str]:
    mentioned = re.findall(r"[\w./-]+\.(?:md|txt|json|py|sh|xml|kt|java)\b", fix_text)
    if any(not m.startswith("examples/") for m in re.findall(r"\S*README\b(?!\.md)", fix_text)):
        mentioned.append("README.md")  # "the README's main TV table" means the top-level README
    want = list(dict.fromkeys([p for p in paths if not p.endswith((".png", ".jpg", ".jpeg", ".webp"))] + mentioned))
    words = needles(fix_text, paths)
    out = {}
    for p in want[:limit_files]:
        text = read(p)
        if text is None:
            continue
        out[p] = fix_mod.excerpt(text, words, radius=3) if len(text) > 6000 else text
    return out


def validate(edits: list[dict], read: Reader, max_lines: int = MAX_CHANGED_LINES) -> list[str]:
    problems, changed = [], 0
    if not edits:
        return ["no edits proposed"]
    for e in edits:
        path = e.get("path", "")
        if not path or path.startswith(SENSITIVE) or ".." in path.split("/") or path.startswith("/"):
            problems.append(f"{path or '(no path)'}: not a path the bot may edit")
            continue
        text = read(path)
        if text is None:
            if e.get("search"):
                problems.append(f"{path}: file not found")
            changed += e.get("replace", "").count("\n") + 1
            continue
        hits = text.count(e["search"]) if e.get("search") else 0
        if hits != 1:
            problems.append(f"{path}: search text found {hits} times (needs exactly 1)")
        changed += max(e.get("search", "").count("\n"), e.get("replace", "").count("\n")) + 1
    if changed > max_lines:
        problems.append(f"{changed} changed lines (limit {max_lines})")
    return problems


def make(*, pr: int, title: str, fix_text: str, paths: list[str], diff: str, read: Reader, propose: Callable,
         model: str, ledger, max_lines: int = MAX_CHANGED_LINES) -> dict:
    """{"edits", "summary", "problems"}; problems non-empty means: don't apply, leave it for a maintainer."""
    if not fix_text:
        return {"edits": [], "summary": "", "problems": ["the review has no fix text"]}
    files = context(read, fix_text, paths)
    res = propose(pr={"pr": pr, "title": title}, fix_text=fix_text, diff=diff, context_files=files, model=model,
                  ledger=ledger, tag=f"fix-{pr}")
    edits = [e for e in (res.get("edits") or []) if isinstance(e, dict)]
    summary = re.sub(r"^on merge:?\s*", "", (res.get("summary") or "").strip(), flags=re.I)
    return {"edits": edits, "summary": summary, "problems": validate(edits, read, max_lines)}
