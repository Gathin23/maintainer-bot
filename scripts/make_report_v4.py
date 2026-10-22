import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""Numbers for report/v4.md: v4 vs v3 on today's decisions, per split, with no model calls.

v3 is what actually ran: the live sticky comment each PR had before the maintainer decided (phase 1 went live on
21 Oct ~16:00 UTC), and for the Round M PRs decided before that, the v3 dry run of the same evening
(runs/live-round-m/bot.json). Usage: make_report_v4.py <fetch dir with comments.json> > runs/v4-report.md
"""
import json
import re
from collections import Counter, defaultdict

from maintainer_bot import dataset, v4

fetch = sys.argv[1]
GIT = os.environ["MB_GIT_DIR"]
rows, snaps, _ = v4.load("data/cleanyourtv-v4", GIT, "data/cleanyourtv")
by = {r["pr"]: r for r in rows}
comments = json.load(open(os.path.join(fetch, "comments.json")))
W = {"merge": "merge", "merge with a small fix": "merge-with-fix", "a few changes first": "rework",
     "close (kindly)": "close", "a maintainer decision": "hold"}


def v3_live(n: int, decided_at: str) -> tuple[str, str, str] | None:
    """(final, model's own verdict, source) from the sticky comment as it was before the decision."""
    for c in comments.get(str(n), {}).get("comments", []):
        b = c["body"]
        if "<!-- maintainer-bot" not in b or c["upd"] > decided_at:
            continue
        if "needs **a maintainer" in b:
            own = re.search(r"own suggestion would be: (.+?)\.", b)
            return "hold", W.get(own.group(1), "hold") if own else "hold", "live"
        m = re.search(r"suggests \*\*(.+?)\*\*", b)
        v = W.get(m.group(1) if m else "", "hold")
        return v, v, "live"
    return None


roundm = {e["pr"]: e for e in json.load(open("runs/live-round-m/bot.json"))}
v3 = {}
for r in rows:
    got = v3_live(r["pr"], r["decided_at"])
    if not got and r["pr"] in roundm:
        e = roundm[r["pr"]]
        got = (e["verdict"], e["model_verdict"], "round-m dry run")
    if got:
        v3[r["pr"]] = {"final": got[0], "model": got[1], "source": got[2]}

results = {}
for split in ("train", "test"):
    p = f"runs/v4-{split}/results.jsonl"
    if os.path.exists(p):
        for line in open(p):
            e = json.loads(line)
            if "error" not in e:
                results[e["pr"]] = e

L = [json.loads(l) for l in open("runs/ledger-v4.jsonl")]
cost = defaultdict(float)
calls = Counter()
for e in L:
    k = e["tag"].split(":")[0]
    cost[k] += e["usd"]
    calls[k] += 1


def table(m: dict) -> str:
    out = ["| Verdict the bot gave alone | Times | Right | Precision |", "|---|---|---|---|"]
    names = {"accept": "merge / merge-with-fix", "rework": "rework", "close": "close", "showcase": "showcase",
             "addon": "addon", "theme": "theme"}
    for k, v in m["per_verdict"].items():
        if v["said"]:
            out.append(f"| {names[k]} | {v['said']} | {v['right']} | {v['precision']:.0%} |")
    return "\n".join(out)


def fmt(m: dict) -> str:
    p = m["precision"]
    d = m["precision_same_direction"]
    return (f"{m['decided']}/{m['n']} ({m['coverage']:.0%}) | {p:.0%} | {d:.0%} | {len(m['wrong_merges'])} | "
            f"{len(m['safety_misses'])}") if p is not None else f"0/{m['n']} | – | – | 0 | 0"


print("# v4 backtest numbers (generated)\n")
for split in ("train", "test", "all"):
    pick = [r for r in rows if split == "all" or r["split"] == split]
    both = [r for r in pick if r["pr"] in v3 and r["pr"] in results]
    m4 = v4.evaluate([results[r["pr"]] for r in both], by)
    m3 = v4.metrics([{"pr": r["pr"], "truth": r["truth"], "final": v3[r["pr"]]["final"]} for r in both])
    m3raw = v4.metrics([{"pr": r["pr"], "truth": r["truth"], "final": v3[r["pr"]]["model"]} for r in both])
    m4all = v4.evaluate([results[r["pr"]] for r in pick if r["pr"] in results], by)
    m4tested = v4.evaluate([results[r["pr"]] for r in pick if r["pr"] in results], by, {"big_core_rework_lines": None})
    m4raw = v4.metrics([{"pr": r["pr"], "truth": r["truth"], "final": results[r["pr"]]["verdict"]}
                        for r in pick if r["pr"] in results])
    print(f"## {split}: {len(pick)} PRs, {len(both)} with a v3 review and a v4 result\n")
    print("| | Decided without the maintainer | Precision (exact home) | Precision (same direction) | Wrong merges | Safety misses |")
    print("|---|---|---|---|---|---|")
    print(f"| v3 as it ran (same PRs) | {fmt(m3)} |")
    print(f"| v4 as tested, policy fixed on train (all {len(m4tested['rows'])} PRs) | {fmt(m4tested)} |")
    print(f"| v4 as shipped, + the rework guard chosen after the test (same PRs) | {fmt(m4)} |")
    print(f"| v4 as shipped (all {len(m4all['rows'])} PRs) | {fmt(m4all)} |")
    print(f"| v3 raw model, no policy (same PRs) | {fmt(m3raw)} |")
    print(f"| v4 raw model, no policy | {fmt(m4raw)} |")
    print()
    print("v4 with policy, per verdict:\n")
    print(table(m4all))
    print()
    tc = Counter((by[x["pr"]]["type"], "alone" if v4.family(x["final"]) != "escalate" else "held") for x in m4all["rows"])
    ok = Counter(by[x["pr"]]["type"] for x in m4all["rows"]
                 if v4.family(x["final"]) != "escalate" and v4.family(x["final"]) == v4.family(x["truth"]))
    tc3 = Counter(by[x["pr"]]["type"] for x in m3["rows"] if v4.family(x["final"]) != "escalate")
    n3 = Counter(by[x["pr"]]["type"] for x in m3["rows"])
    print("| Type | PRs | v3 decided alone (of PRs with a v3 review) | v4 decided alone | v4 right when alone |")
    print("|---|---|---|---|---|")
    for t in sorted({by[x["pr"]]["type"] for x in m4all["rows"]}):
        a, h = tc[(t, "alone")], tc[(t, "held")]
        print(f"| {t} | {a + h} | {tc3[t]}/{n3[t]} | {a} | {ok[t]}/{a} |")
    print()
    if m4all["wrong_merges"]:
        print("Wrong merges (v4): " + "; ".join(f"#{x['pr']} (Gathin: {x['truth']}, bot: {x['bot']})" for x in m4all["wrong_merges"]))
    if m4all["safety_misses"]:
        print("\nSafety misses (v4): " + "; ".join(f"#{x['pr']} (Gathin: {x['truth']}, bot: {x['bot']})" for x in m4all["safety_misses"]))
    wrong = [x for x in m4all["rows"] if v4.family(x["final"]) not in ("escalate", v4.family(x["truth"]))]
    if wrong:
        print("\nEvery case v4 decided alone and differently from Gathin:\n")
        for x in wrong:
            print(f"- #{x['pr']} ({by[x['pr']]['type']}) {by[x['pr']]['title'][:80]}: Gathin **{x['truth']}**, "
                  f"bot **{x['final']}** ({x['confidence']:.2f}). " + "; ".join(x.get("reasons") or [])[:260])
    held = Counter(re.sub(r"\(.*|[0-9.]+ is below.*|:.*", "", x["why"]).strip() for x in m4all["rows"]
                   if v4.family(x["final"]) == "escalate")
    print("\nWhy v4 held the rest: " + "; ".join(f"{k or 'model asked'} ×{v}" for k, v in held.most_common()))
    print()

print("## Cost\n")
for k in sorted(cost):
    print(f"- {k}: {calls[k]} calls, ${cost[k]:.2f}")
tot = sum(cost.values())
n = len(results)
print(f"- total ${tot:.2f} for {n} PRs reviewed (${tot / max(1, n):.3f} per PR, probe calls included)")
json.dump({"v3": v3, "n_results": n}, open("runs/v4-baseline.json", "w"))
