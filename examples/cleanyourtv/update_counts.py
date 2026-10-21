"""README counts for CleanYourTV after a batch of merges (deterministic, no model calls).

    python3 update_counts.py REPO_ROOT [--font Fredoka.ttf] [--check]

Counts TV models (folders in examples/), brands (each folder's prefix mapped to a name on the README brand
line) and languages (launcher values-*/strings.xml plus English), then rewrites:
  - the README card alt text ("N TV models · B brands · L languages · K launcher")
  - the brand line under "Tested lists from contributors" (only when a count or a brand changed)
  - the "| **L languages** |" feature row
  - STATS in tools/readme_stats.py
and, when a font is given, redraws docs/stats.png and docs/card.jpg with the repo's own tools.
A folder whose brand is not on the line yet takes the first word of its TV cell in examples/README.md and is
reported as a new brand, so the maintainer can check the spelling in the PR.
Exit code 0 = nothing to change or changed; prints a JSON summary. --check prints and writes nothing.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

LEAD = "Tested lists from contributors"
SEP = " · "
WIDTH = 120


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def variants(name: str) -> set[str]:
    """Folder prefixes a brand name may appear as: "Tele System" -> tele-system, telesystem, tele;
    "PRISM+" -> prism, prismplus."""
    full = slug(name)
    plus = slug(name.replace("+", " plus"))
    return {full, plus, full.replace("-", ""), plus.replace("-", ""), slug(name.split()[0])} - {""}


def folders(root: Path) -> list[str]:
    return sorted(p.name for p in (root / "examples").iterdir() if p.is_dir())


def languages(root: Path) -> int:
    res = root / "launcher/app/src/main/res"
    return len(list(res.glob("values-*/strings.xml"))) + 1


def brand_block(lines: list[str]) -> tuple[int, int]:
    """(first, last+1) line indexes of the brand paragraph."""
    i = next(i for i, l in enumerate(lines) if l.startswith(LEAD))
    start = i + 1
    while not lines[start].strip():
        start += 1
    end = start
    while end < len(lines) and lines[end].strip():
        end += 1
    return start, end


def parse_brands(block: list[str]) -> tuple[dict[str, int], list[str]]:
    """({name: count} for TVs, [projector brands])."""
    counts, projectors = {}, []
    for line in block:
        line = line.strip()
        m = re.match(r"^(.*) projectors$", line)
        if m:
            projectors = [p.strip() for p in re.split(r",| and ", m.group(1)) if p.strip()]
            continue
        for part in line.split("·"):
            part = part.strip()
            if not part:
                continue
            b = re.match(r"^\*\*(.+?)\*\*\s+(\d+)$", part)
            if b:
                counts[b.group(1)] = int(b.group(2))
            else:
                counts[part] = 1
    return counts, projectors


def tv_cells(root: Path) -> dict[str, str]:
    out = {}
    for line in (root / "examples/README.md").read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\|\s*`([^`/]+)/`\s*\|\s*([^|]+)\|", line)
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


def assign(names: list[str], folder_names: list[str], cells: dict[str, str]) -> tuple[dict[str, list[str]], list[str]]:
    """{brand: [folders]} plus the brands that were not on the line before."""
    keys = []
    for n in names:
        keys += [(k, n) for k in variants(n)]
    keys.sort(key=lambda k: -len(k[0]))  # longest prefix wins ("insignia-fire-tv" before "insignia")
    out: dict[str, list[str]] = {}
    new = []
    for f in folder_names:
        hit = next((n for k, n in keys if f == k or f.startswith(k + "-")), None)
        if hit is None:
            cell = cells.get(f, f)
            hit = re.split(r"[\s,(]", cell.strip())[0] or f.split("-")[0]
            if hit not in new:
                new.append(hit)
            keys += [(k, hit) for k in variants(hit)]
            keys.sort(key=lambda k: -len(k[0]))
        out.setdefault(hit, []).append(f)
    return out, new


def wrap(entries: list[str]) -> list[str]:
    lines, cur = [], ""
    for e in entries:
        piece = e + " ·"
        if cur and len(cur) + 1 + len(piece) > WIDTH:
            lines.append(cur)
            cur = piece
        else:
            cur = f"{cur} {piece}" if cur else piece
    if cur:
        lines.append(cur)
    return lines


def render_brands(counts: dict[str, int], projectors: list[str]) -> list[str]:
    tv = {n: c for n, c in counts.items() if n not in projectors}
    bold = sorted((n for n, c in tv.items() if c > 1), key=lambda n: (-tv[n], n.casefold()))
    plain = sorted((n for n, c in tv.items() if c == 1), key=str.casefold)
    out = wrap([f"**{n}** {tv[n]}" for n in bold]) + wrap(plain)
    if projectors:
        ps = sorted(projectors, key=str.casefold)
        out.append((", ".join(ps[:-1]) + " and " + ps[-1] if len(ps) > 1 else ps[0]) + " projectors")
    return out


def compute(root: Path) -> dict:
    readme = (root / "README.md").read_text(encoding="utf-8")
    lines = readme.split("\n")
    s, e = brand_block(lines)
    old_counts, projectors = parse_brands(lines[s:e])
    names = list(old_counts) + projectors
    fl = folders(root)
    by_brand, new = assign(names, fl, tv_cells(root))
    for b in new:  # a new projector brand goes on the projector line
        if all("projector" in tv_cells(root).get(f, "").lower() for f in by_brand[b]):
            projectors.append(b)
    counts = {n: len(fs) for n, fs in by_brand.items()}
    gone = [n for n in names if n not in counts]
    return {"tv_models": len(fl), "brands": len(counts), "languages": languages(root), "counts": counts,
            "projectors": [p for p in projectors if p in counts], "new_brands": new, "gone_brands": gone,
            "brand_lines": (s, e), "old_counts": old_counts}


def apply(root: Path, c: dict) -> list[str]:
    changed = []
    readme_p = root / "README.md"
    text = readme_p.read_text(encoding="utf-8")
    lines = text.split("\n")
    s, e = c["brand_lines"]
    old_tv, old_proj = parse_brands(lines[s:e])
    new_tv = {n: k for n, k in c["counts"].items() if n not in c["projectors"]}
    if new_tv != old_tv or sorted(old_proj) != sorted(c["projectors"]):  # rewrite only when something changed
        lines[s:e] = render_brands(c["counts"], c["projectors"])
    text2 = "\n".join(lines)
    text2 = re.sub(r"\b\d+ TV models · \d+ brands · \d+ languages · ",
                   f"{c['tv_models']} TV models · {c['brands']} brands · {c['languages']} languages · ", text2)
    text2 = re.sub(r"^\| \*\*\d+ languages\*\* \|", f"| **{c['languages']} languages** |", text2, flags=re.M)
    if text2 != text:
        readme_p.write_text(text2, encoding="utf-8")
        changed.append("README.md")
    stats_p = root / "tools/readme_stats.py"
    st = stats_p.read_text(encoding="utf-8")
    st2 = re.sub(r'\("\d+", "TV MODELS"\)', f'("{c["tv_models"]}", "TV MODELS")', st)
    st2 = re.sub(r'\("\d+", "BRANDS"\)', f'("{c["brands"]}", "BRANDS")', st2)
    st2 = re.sub(r'\("\d+", "LANGUAGES"\)', f'("{c["languages"]}", "LANGUAGES")', st2)
    if st2 != st:
        stats_p.write_text(st2, encoding="utf-8")
        changed.append("tools/readme_stats.py")
    return changed


def redraw(root: Path, font: str) -> list[str]:
    py = sys.executable
    subprocess.run([py, "tools/readme_stats.py", font, "docs/stats.png"], cwd=root, check=True)
    subprocess.run([py, "tools/readme_card.py", font, "docs/card.jpg"], cwd=root, check=True)
    return ["docs/stats.png", "docs/card.jpg"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--font", help="Fredoka TTF; without it the images are not redrawn")
    ap.add_argument("--check", action="store_true", help="print what would change, write nothing")
    a = ap.parse_args(argv)
    root = Path(a.root)
    c = compute(root)
    summary = {k: c[k] for k in ("tv_models", "brands", "languages", "new_brands", "gone_brands")}
    if a.check:
        print(json.dumps(summary))
        return 0
    changed = apply(root, c)
    if changed and a.font:
        changed += redraw(root, a.font)
    summary["changed"] = changed
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
