import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""precedents.jsonl for the live reviewer: the v3-era decisions plus 21-22 Oct's, in the v4 verdicts.

Usage: export_precedents_v4.py <old data dir> <v4 data dir> <out.jsonl>
One line per PR with its latest decision; a PR decided twice (sent back, then merged or closed) keeps the
earlier verdict in the note ("earlier: rework"). Everything in it is already public on the PRs themselves.
"""
import json
import re

from maintainer_bot import dataset

old, new, out = sys.argv[1:4]


def files_of(data: str, n: int) -> list[str]:
    try:
        return [f["path"] for f in dataset.load_snapshot(data, n)["files"]][:40]
    except FileNotFoundError:
        return []


def note(t: dict) -> str:
    return re.sub(r"\s+", " ", t.get("maintainer_note") or "").strip()[:320]


entries: dict[int, dict] = {}
for t in dataset.load(old):
    entries[t["pr"]] = {"pr": t["pr"], "title": t["title"], "truth": t["truth"], "decided_at": t["decided_at"],
                        "maintainer_note": note(t), "fix": (t.get("fix") or "")[:320], "files": files_of(old, t["pr"])}
for t in dataset.load(new):
    before = entries.get(t["pr"])
    n = note(t)
    if before and before["truth"] != t["truth"]:
        n = f"(earlier: {before['truth']}) {n}".strip()
    entries[t["pr"]] = {"pr": t["pr"], "title": t["title"], "truth": t["truth"], "decided_at": t["decided_at"],
                        "maintainer_note": n[:360], "fix": (t.get("fix") or "")[:320], "files": files_of(new, t["pr"])}
rows = sorted(entries.values(), key=lambda e: e["decided_at"])
with open(out, "w", encoding="utf-8") as fh:
    for e in rows:
        fh.write(json.dumps(e, ensure_ascii=False) + "\n")
from collections import Counter
print(len(rows), "precedents ->", out, dict(Counter(e["truth"] for e in rows)))
