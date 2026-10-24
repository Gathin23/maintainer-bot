"""Which PRs an /approve wave may act on (the launch gate).

A wave only acts on PRs whose every file is in the low-risk parts of the repo: the TV lists and their notes
(examples/), docs/, themes/, SHOWCASE.md, table rows and the brand line in README.md, and launcher translations
(launcher/app/src/main/res/values-<locale>/strings.xml, which CI lints and builds). Script files are left out even
inside those folders. Everything else (launcher code, addons/, tools/, PROMPT.md, scripts, workflows) stays for the
maintainer, who can still merge it by hand or move it with /close #n or /rework #n.

The gate reads file names (old and new, so a rename out of launcher/ doesn't slip through) and, for README.md,
the patch. It fails closed: a missing patch, too many files or an unknown path keeps the PR out of the wave.
"""
from __future__ import annotations

import re

FOLDERS = ("examples/", "docs/", "themes/")
DATA_EXT = (".txt", ".md", ".json", ".png", ".jpg", ".jpeg", ".webp", ".gif")
FILES = ("SHOWCASE.md",)
TABLE_FILES = ("README.md",)
TRANSLATION = re.compile(r"^launcher/app/src/main/res/values-(?:[a-z]{2,3}(?:-r[A-Z]{2})?|b\+[a-z]{2,3}(?:\+[A-Za-z0-9]+)*)"
                         r"/strings\.xml$")
# README's brand line ("**TCL** 57 · **Sony** 31 · … ·" and "Acer · AIWA · … ·"): plain names and counts only, no
# links or HTML. List PRs bump it, and the counts step rewrites it after the wave anyway.
_NAME = r"[A-Za-z0-9+.&' -]+"
_ITEM = rf"(?:\*\*{_NAME}\*\* \d+|{_NAME})"
BRAND_LINE = re.compile(rf"^{_ITEM}(?:(?: · {_ITEM})+(?: ·)?| ·)$")  # at least one separator: not a sentence
MAX_FILES = 300  # the files API lists at most this many here; more and the gate can't see them all


def path_reason(path: str) -> str:
    """'' when a wave may touch this path, else why not."""
    if path in FILES or path in TABLE_FILES or TRANSLATION.match(path):
        return ""
    if path.startswith(FOLDERS) and ".." not in path.split("/"):
        return "" if path.lower().endswith(DATA_EXT) else f"{path} is not a list, note or picture"
    return f"changes {path}"


def table_only(patch: str | None) -> bool:
    """True when every added or removed line of a patch is a markdown table row, a brand line, or blank."""
    if not patch:
        return False  # binary, or too big for the API to show: fail closed
    for line in patch.splitlines():
        text = line[1:].strip()
        if line[:1] in ("+", "-") and text and not text.startswith("|") and not BRAND_LINE.match(text):
            return False
    return True


def check(files: list[dict]) -> str:
    """'' when a wave may act on a PR with these files ({filename, previous_filename?, patch?}), else the reason."""
    if not files:
        return "no files"
    if len(files) >= MAX_FILES:
        return f"{len(files)}+ files"
    for f in files:
        for p in (f["filename"], f.get("previous_filename")):
            why = path_reason(p) if p else ""
            if why:
                return why
        if f["filename"] in TABLE_FILES and not table_only(f.get("patch")):
            return f"{f['filename']} changes outside the table rows"
    return ""


def edits_reason(edits: list[dict]) -> str:
    """The same gate for a fix's search/replace edits: '' when they stay inside it."""
    for e in edits:
        why = path_reason(e["path"])
        if why:
            return why
        if e["path"] in TABLE_FILES:
            patch = "\n".join(["-" + l for l in (e.get("search") or "").splitlines()] +
                              ["+" + l for l in (e.get("replace") or "").splitlines()])
            if not table_only(patch or "+"):
                return f"{e['path']} edit outside the table rows"
    return ""
