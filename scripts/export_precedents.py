import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""Write the maintainer's past decisions as precedents.jsonl for the live reviewer.

Usage: export_precedents.py <data dir> <out.jsonl>
One line per decided PR: number, title, verdict, when, the public comment the maintainer left (trimmed) and
the changed paths. Everything in it is already public on the PRs themselves.
"""
import json

from maintainer_bot import dataset

data, out = sys.argv[1], sys.argv[2]
n = 0
with open(out, "w", encoding="utf-8") as fh:
    for line in open(os.path.join(data, "truth.jsonl"), encoding="utf-8"):
        t = json.loads(line)
        try:
            files = [f["path"] for f in dataset.load_snapshot(data, t["pr"])["files"]][:40]
        except Exception:  # noqa: BLE001
            files = []
        fh.write(json.dumps({"pr": t["pr"], "title": t["title"], "truth": t["truth"], "decided_at": t["decided_at"],
                             "maintainer_note": (t.get("maintainer_note") or "")[:320], "fix": (t.get("fix") or "")[:320],
                             "files": files}, ensure_ascii=False) + "\n")
        n += 1
print(n, "precedents ->", out)
