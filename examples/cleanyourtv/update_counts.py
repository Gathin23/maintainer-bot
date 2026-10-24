"""README tables and counts for CleanYourTV after a batch of merges: runs the repo's tools/gen_tables.py.

    python3 update_counts.py REPO_ROOT [--font Fredoka.ttf] [--check]

The repo generates its TV tables (README.md and examples/README.md), the brand line, the card alt text
("N TV models · B brands · L languages"), the languages row and STATS in tools/readme_stats.py from every
examples/<folder>/tv.json; with a font it also redraws docs/stats.png and docs/card.jpg. This script runs that
generator in the checkout (it is repo code, so the workflow runs it in the job without secrets) and prints a JSON
summary on its last line: the counts, the brands that are new on the brand line (so the counts PR can ask for
the spelling to be checked) or gone from it, and the files that changed. --check writes nothing.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

OUTPUTS = ("README.md", "examples/README.md", "tools/readme_stats.py", "docs/stats.png", "docs/card.jpg")


def brand_line_names(readme: str) -> set[str]:
    """The names on the README brand line, between the tv-brands markers."""
    m = re.search(r"<!-- tv-brands:start[^\n]*-->\n(.*?)\n<!-- tv-brands:end -->", readme, re.S)
    names = set()
    for line in (m.group(1) if m else "").splitlines():
        line = line.strip()
        p = re.match(r"^(.*) projectors$", line)
        if p:
            names |= {x.strip() for x in re.split(r",| and ", p.group(1)) if x.strip()}
            continue
        for part in line.split("·"):
            part = re.sub(r"^\*\*(.+?)\*\*\s+\d+$", r"\1", part.strip())
            if part:
                names.add(part)
    return names


def summary(root: Path) -> dict:
    """The counts from the data itself: tv.json brands, folders, launcher locales (+ English)."""
    lists = [p for p in (root / "examples").iterdir() if p.is_dir()]
    brands = set()
    for p in lists:
        try:
            brands.add(json.loads((p / "tv.json").read_text(encoding="utf-8"))["brand"])
        except (OSError, ValueError, KeyError):
            pass
    languages = len(list((root / "launcher/app/src/main/res").glob("values-*/strings.xml"))) + 1
    return {"tv_models": len(lists), "brands": len(brands), "languages": languages, "_brands": brands}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--font", help="Fredoka TTF; without it the images are not redrawn")
    ap.add_argument("--check", action="store_true", help="print what would change, write nothing")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    before_readme = (root / "README.md").read_text(encoding="utf-8")
    before = {p: (root / p).read_bytes() for p in OUTPUTS if (root / p).is_file()}
    cmd = [sys.executable, str(root / "tools" / "gen_tables.py"), "--root", str(root)]
    cmd += ["--check"] if a.check else (["--font", a.font] if a.font else [])
    r = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    if r.returncode not in ((0, 1) if a.check else (0,)):
        sys.exit("tools/gen_tables.py: " + (r.stderr or r.stdout).strip()[-400:])
    s = summary(root)
    on_line = brand_line_names(before_readme)
    out = {k: s[k] for k in ("tv_models", "brands", "languages")}
    out["new_brands"] = sorted(s["_brands"] - on_line, key=str.casefold)
    out["gone_brands"] = sorted(on_line - s["_brands"], key=str.casefold)
    if a.check:
        out["stale"] = r.returncode == 1
    else:
        out["changed"] = [p for p in OUTPUTS if (root / p).is_file() and (root / p).read_bytes() != before.get(p)]
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
