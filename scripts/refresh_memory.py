import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""Refresh the bot's memory (precedents.jsonl and the MAINTAINER.md policy block) from the round notes.

Usage:
  refresh_memory.py --launch ~/Arsenal/cleanyourtv-launch --base-precedents OLD.jsonl --base-rules MAINTAINER.md \
                    --out-dir DIR [--until af] [--policy BLOCK.md] [--no-github] [--repo Gathin23/cleanyourtv]

Writes DIR/precedents.jsonl (the base file plus every round up to --until, one line per PR, latest decision),
DIR/MAINTAINER.md (the base rules plus --policy, replacing an earlier copy of the same block),
DIR/policy-candidates.md (the raw policy material from the round notes, for a person to curate) and
DIR/summary.json (counts). GitHub is only read (gh api graphql); nothing is written anywhere else.
With --until, GitHub events after that round's cutoff are ignored, so a backtest's memory doesn't know the future.
"""
import argparse
import json
from collections import Counter

from maintainer_bot import memory_refresh as mr

ap = argparse.ArgumentParser()
ap.add_argument("--launch", default=os.path.expanduser("~/Arsenal/cleanyourtv-launch"))
ap.add_argument("--base-precedents", required=True)
ap.add_argument("--base-rules", required=True)
ap.add_argument("--out-dir", required=True)
ap.add_argument("--until", default="", help="last round to include (aa, ab, ... ag2); empty = all")
ap.add_argument("--policy", default="", help="the curated policy block to put into MAINTAINER.md")
ap.add_argument("--no-github", action="store_true")
ap.add_argument("--repo", default="Gathin23/cleanyourtv")
a = ap.parse_args()

base = [json.loads(l) for l in open(a.base_precedents, encoding="utf-8") if l.strip()]
rounds = mr.parse_rounds(a.launch, until=a.until or None)
entries = mr.fold(base, rounds)
new = {n for _, _, d in rounds for n in d}
stats = {}
if not a.no_github:
    gh = mr.fetch_prs(sorted(new), repo=a.repo)
    cutoff = mr.CUTOFF[a.until] if a.until else "9999-12-31T00:00:00Z"
    stats = mr.cross_check(entries, gh, cutoff=cutoff, only=new)
    stats["fetched"] = len(gh)
os.makedirs(a.out_dir, exist_ok=True)
with open(os.path.join(a.out_dir, "precedents.jsonl"), "w", encoding="utf-8") as f:
    f.write(mr.to_jsonl(entries))
rules = open(a.base_rules, encoding="utf-8").read()
if a.policy:
    rules = mr.apply_policy_block(rules, open(a.policy, encoding="utf-8").read())
with open(os.path.join(a.out_dir, "MAINTAINER.md"), "w", encoding="utf-8") as f:
    f.write(rules)
brief = ("round-ag/BRIEF.md",) if not a.until or a.until in ("ag", "ag2") else ()
with open(os.path.join(a.out_dir, "policy-candidates.md"), "w", encoding="utf-8") as f:
    f.write(mr.policy_candidates(a.launch, until=a.until or None, extra_files=brief))
base_prs = {e["pr"] for e in base}
summary = {
    "rounds": {k: {"decisions": len(d), "truth": dict(Counter(e["truth"] for e in d.values()))} for k, _, d in rounds},
    "precedents": len(entries), "existing": len(base_prs), "new_prs": len(new - base_prs),
    "updated_existing": len(new & base_prs), "truth": dict(Counter(e["truth"] for e in entries.values())),
    "github": stats, "until": a.until or "all", "rules_chars": len(rules),
}
json.dump(summary, open(os.path.join(a.out_dir, "summary.json"), "w"), indent=1)
print(json.dumps(summary, indent=1))
