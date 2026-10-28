import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""Collect the live shadow run (MB-SHADOW lines in the maintainer-bot workflow logs) and compare it with the live
reviews and, when given, the maintainer's round decisions. Read-only; no model calls.

Usage: shadow_logs.py --since 2026-10-29 [--repo Gathin23/cleanyourtv] [--rounds 'round-ah/review-*.md'] [--out FILE]

--rounds: review files with `| #N | VERDICT | sha | ...` rows (the Round AG format); paths are relative to
~/Arsenal/cleanyourtv-launch unless absolute.
"""
import argparse
import glob
import json
import re
import subprocess

from maintainer_bot import live, v4

ap = argparse.ArgumentParser()
ap.add_argument("--since", required=True)
ap.add_argument("--repo", default="Gathin23/cleanyourtv")
ap.add_argument("--rounds", default="")
ap.add_argument("--out", default="")
a = ap.parse_args()
TRUTH = {"MERGE": "merge", "MERGE+FIX": "merge-with-fix", "ASK": "rework", "CLOSE": "close", "HOLD": "hold"}
ACC = ("merge", "merge-with-fix")


def gh(*args):
    return subprocess.run(["gh", *args], capture_output=True, text=True).stdout


runs = json.loads(gh("run", "list", "-R", a.repo, "--workflow", "maintainer-bot.yml", "--event",
                     "pull_request_target", "--created", f">={a.since}", "--limit", "1000",
                     "--json", "databaseId") or "[]")
shadow: dict[int, dict] = {}
for r in sorted(runs, key=lambda r: r["databaseId"]):
    for m in re.finditer(r"MB-SHADOW (\{.*\})", gh("run", "view", str(r["databaseId"]), "-R", a.repo, "--log")):
        try:
            e = json.loads(m.group(1))
        except ValueError:
            continue
        if e.get("verdict"):
            shadow[e["pr"]] = e          # the latest shadow review of each PR
truth = {}
if a.rounds:
    base = os.path.expanduser("~/Arsenal/cleanyourtv-launch")
    for f in glob.glob(a.rounds if os.path.isabs(a.rounds) else os.path.join(base, a.rounds)):
        for line in open(f, encoding="utf-8"):
            m = re.match(r"^\| #(\d+) \| ([A-Z+]+)", line)
            if m and m.group(2) in TRUTH:
                truth[int(m.group(1))] = TRUTH[m.group(2)]
rows = []
for n, e in sorted(shadow.items()):
    body = next((c["body"] for c in json.loads(gh("api", f"repos/{a.repo}/issues/{n}/comments?per_page=100") or "[]")
                 if live.MARKER in (c.get("body") or "")), "")
    d = live.read_data(body)
    rows.append({"pr": n, "live": d.get("final"), "live_model": d.get("m"), "shadow": e["verdict"],
                 "shadow_model": e.get("model_verdict"), "shadow_usd": e.get("cost_usd"), "truth": truth.get(n),
                 "diff_cut": (e.get("context") or {}).get("diff_cut")})


def summary(key):
    dec = [r for r in rows if r[key] and r[key] != "hold"]
    scored = [r for r in dec if r["truth"]]
    return {"decided_alone": f"{len(dec)}/{len(rows)}",
            "precision_vs_rounds": f"{sum(1 for r in scored if v4.family(r[key]) == v4.family(r['truth']))}/{len(scored)}",
            "wrong_merges_vs_rounds": sum(1 for r in scored if r[key] in ACC and r["truth"] not in ACC)}


out = {"prs": len(rows), "same_final": sum(1 for r in rows if r["live"] == r["shadow"]),
       "live": summary("live"), "shadow": summary("shadow"),
       "shadow_usd": round(sum(r["shadow_usd"] or 0 for r in rows), 2), "rows": rows}
print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=1))
for r in rows:
    if r["live"] != r["shadow"]:
        print(f"#{r['pr']}: live {r['live']} ({r['live_model']}), shadow {r['shadow']} ({r['shadow_model']}), "
              f"rounds {r['truth']}")
if a.out:
    json.dump(out, open(a.out, "w"), indent=1)
