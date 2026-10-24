"""CleanYourTV's generated TV tables: the rows an older list PR added become its examples/<folder>/tv.json.

The repo writes the README.md and examples/README.md TV tables, the brand line and the counts from every
examples/<folder>/tv.json (tools/gen_tables.py). A list PR from before that carries its row in the tables
instead. On merge the bot gives the two README files main's generated sections, keeps the PR's other edits in
them (prose, the notes list, other tables), and turns the PR's rows into tv.json, the same way
`tools/gen_tables.py --adopt` does; the counts job then regenerates the tables from the tv.json files.

This is a port of --adopt, not a call to it: the job that merges holds a write token and never runs repo code.
"""
from __future__ import annotations

import json
import re

GENERATED = ("README.md", "examples/README.md")
EXAMPLES_ROW = re.compile(r"^\| `([A-Za-z0-9][A-Za-z0-9._-]*)/` \| (.+?) \| (.+?) \| (.+) \|$")
README_ROW = re.compile(r"^\| (.+?) \| (.+?) \|$")


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def guess_brand(folder: str, tv: str, known: list[str]) -> str:
    """The known brand whose name the folder starts with (the longest), else the TV cell's first word."""
    hits = [b for b in known if folder == slug(b) or folder.startswith(slug(b) + "-")
            or folder.startswith(slug(b).replace("-", "") + "-")]
    if hits:
        return max(hits, key=len)
    return re.split(r"[\s,(]", tv)[0]


def dumps(data: dict) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def from_rows(diff: str, existing: dict[str, dict], folders: set[str]) -> tuple[dict[str, str], list[str], list[str]]:
    """({path: tv.json text to write}, notes, problems) from the table hunks of a PR's diff.

    existing: {folder: its tv.json on the merge branch}; folders: the folders in examples/ on the merge branch.
    A folder without a tv.json gets one from its examples/README.md row (readme_os from a README row with the
    same TV when the OS differs). A folder that has one takes the row's new text only when the row the PR
    removed is what the tv.json still says; if main has changed that row since, it is a problem."""
    lines = diff.split("\n")
    added = [l[1:] for l in lines if l.startswith("+") and not l.startswith("+++")]
    removed = [l[1:] for l in lines if l.startswith("-") and not l.startswith("---")]
    rows = {m.group(1): m.groups()[1:] for m in map(EXAMPLES_ROW.match, added) if m}
    before = {m.group(1): m.groups()[1:] for m in map(EXAMPLES_ROW.match, removed) if m}
    readme_os = {m.group(1): m.group(2) for m in map(README_ROW.match, added) if m}
    known = sorted({d.get("brand", "") for d in existing.values()} - {""})
    writes, notes, problems = {}, [], []
    for name, (tv, os_cell, cell_notes) in sorted(rows.items()):
        if name not in folders:
            continue
        path = f"examples/{name}/tv.json"
        if name in existing:
            have = existing[name]
            now = (have.get("tv"), have.get("os"), have.get("notes"))
            if now == (tv, os_cell, cell_notes):
                continue
            if before.get(name) != now:
                problems.append(f"{path}: the row this PR edits has changed on main since")
                continue
            writes[path] = dumps({**have, "tv": tv, "os": os_cell, "notes": cell_notes})
            notes.append(f"{path}: the PR's edited row")
            continue
        brand = guess_brand(name, tv, known)
        data = {"tv": tv, "os": os_cell, "brand": brand, "notes": cell_notes}
        if readme_os.get(tv, os_cell) != os_cell:
            data["readme_os"] = readme_os[tv]
        writes[path] = dumps(data)
        notes.append(f"{path}: from the PR's row, brand {brand}" + ("" if brand in known else " (new brand)"))
    return writes, notes, problems


# The generated sections: between markers on today's main, located by their shape in a README from before.
SECTIONS = {"README.md": ("tv-brands", "tv-table"), "examples/README.md": ("tv-table",)}
HEADERS = {"README.md": "| TV | OS |", "examples/README.md": "| Folder |"}
BRAND_LEAD = "Tested lists from contributors"


def spans(text: str, path: str) -> dict[str, tuple[int, int]] | None:
    """{section: (first line, last line + 1)} for the generated sections of one README; None if one is missing."""
    lines = text.split("\n")
    out = {}
    for name in SECTIONS[path]:
        start = [i for i, l in enumerate(lines) if l.startswith(f"<!-- {name}:start")]
        end = [i for i, l in enumerate(lines) if l.strip() == f"<!-- {name}:end -->"]
        if len(start) == 1 and len(end) == 1 and start[0] < end[0]:
            out[name] = (start[0], end[0] + 1)
            continue
        if name == "tv-table":
            h = next((i for i, l in enumerate(lines) if l.startswith(HEADERS[path])), None)
            if h is None:
                return None
            e = h + 2
            while e < len(lines) and lines[e].startswith("|"):
                e += 1
            out[name] = (h, e)
        else:
            lead = next((i for i, l in enumerate(lines) if l.startswith(BRAND_LEAD)), None)
            if lead is None:
                return None
            s = lead + 1
            while s < len(lines) and not lines[s].strip():
                s += 1
            e = s
            while e < len(lines) and lines[e].strip():
                e += 1
            out[name] = (s, e)
    return out


def sections(text: str, path: str) -> dict[str, list[str]] | None:
    sp = spans(text, path)
    lines = text.split("\n")
    return None if sp is None else {name: lines[s:e] for name, (s, e) in sp.items()}


def with_sections_of(text: str, path: str, donor: str) -> str | None:
    """text with its generated sections replaced by donor's (main's); None when either lacks one."""
    sp, theirs = spans(text, path), sections(donor, path)
    if sp is None or theirs is None:
        return None
    lines = text.split("\n")
    for name, (s, e) in sorted(sp.items(), key=lambda x: -x[1][0]):  # bottom first, so indexes hold
        lines[s:e] = theirs[name]
    return "\n".join(lines)


def touches_sections(patch: str | None) -> bool:
    """Whether a file patch from the API changes a TV-table row or the brand line (None: can't tell, so yes)."""
    if patch is None:
        return True
    for line in patch.split("\n"):
        if line[:1] not in ("+", "-") or line.startswith(("+++", "---")):
            continue
        text = line[1:].strip()
        if EXAMPLES_ROW.match(text) or text.endswith(" projectors"):
            return True
        if README_ROW.match(text) and not text.startswith("| **") and not text.startswith("|---"):
            return True
        if not text.startswith("|") and " · " in text:
            return True
    return False
