"""Pretty-print eval_0gm.py output lines (stdin)."""
import json
import sys

for line in sys.stdin:
    line = line.strip()
    if not line.startswith("{"):
        print(line)
        continue
    d = json.loads(line)
    pd = d["policy_decision_only"]
    ps = d.get("policy_as_shipped") or {}
    extra = f" | with 2nd cov={ps.get('coverage')} prec={ps.get('precision')} WM={len(ps.get('wrong_merges', []))}" if ps else ""
    print(f"{d['arm'][:58]:58} n={d['n']} home={d['raw_same_home']} dir={d['raw_same_direction']} "
          f"rawWM={len(d['raw_wrong_merges'])} safe={d['safety_caught']}/{d['safety_relevant_not_accepted']} "
          f"close={d['close']['precision']}/{d['close']['recall']} rework={d['rework']['precision']}/{d['rework']['recall']} "
          f"| pol cov={pd['coverage']} prec={pd['precision']} WM={len(pd['wrong_merges'])}{extra} "
          f"| $={d.get('usd_per_review')} tok={d.get('in_tokens_median')} s={d.get('secs_median')}")
