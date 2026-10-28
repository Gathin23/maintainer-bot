import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""Score shadow_0gm.py's output (no model calls).

Usage: score_shadow.py OUT_DIR [LEDGER]

Cost comes from the ledger's shadow-* tags (the per-result "usd" is wrong when PRs ran in parallel).
"""
import json
import re

from maintainer_bot import v4

out = sys.argv[1]
sample = json.load(open(os.path.join(out, "sample.json")))["rows"]
res = {}
for line in open(os.path.join(out, "results.jsonl")):
    e = json.loads(line)
    res[(e["pr"], e["arm"])] = e
OFF = {"use_critic": False, "use_second": False}
ACC = ("merge", "merge-with-fix")


def ledger_usd():
    path = sys.argv[2] if len(sys.argv) > 2 else "runs/rollout/ledger-2026-10-28.jsonl"
    got = {"dpx_mem": 0.0, "glm": 0.0, "0gm": 0.0}
    mine = {r["pr"] for r in sample}
    for line in open(path):
        e = json.loads(line)
        m = re.match(r"shadow-(dpx|second-glm|second-0gm):(\d+)", e.get("tag", ""))
        if m and int(m.group(2)) in mine:
            got[{"dpx": "dpx_mem", "second-glm": "glm", "second-0gm": "0gm"}[m.group(1)]] += e["usd"]
    return {k: round(v, 4) for k, v in got.items()}


def fam(v):
    return v4.family(v) if v else None


def metrics(pairs):
    """pairs: [(truth, verdict)] -> same home, wrong merges, close P/R."""
    n = len(pairs)
    same = sum(1 for t, v in pairs if fam(t) == fam(v))
    wrong = sum(1 for t, v in pairs if v in ACC and t not in ACC)
    cp = [t for t, v in pairs if v == "close"]
    ct = [v for t, v in pairs if t == "close"]
    return {"n": n, "same_home": f"{same}/{n}", "wrong_merges": wrong,
            "close_p": f"{sum(1 for t in cp if t == 'close')}/{len(cp)}",
            "close_r": f"{sum(1 for v in ct if v == 'close')}/{len(ct)}"}


def policy(pairs):
    """pairs: [(truth, final)] -> decided alone, precision, wrong merges."""
    dec = [(t, f) for t, f in pairs if f != "hold"]
    right = sum(1 for t, f in dec if fam(t) == fam(f))
    return {"decided_alone": f"{len(dec)}/{len(pairs)}", "precision": f"{right}/{len(dec)}" if dec else "n/a",
            "wrong_merges": sum(1 for t, f in dec if f in ACC and t not in ACC)}


arms = {"live": [], "dpx_mem": []}
pol = {"live (as it ran: critic + GLM)": [], "live (critic, second off)": [], "dpx_mem (critic, second off)": [],
       "live + GLM second": [], "live + 0GM second": []}
second_agree = {"glm": [], "0gm": []}
rows_out = []
usd = {"dpx_mem": 0.0, "glm": 0.0, "0gm": 0.0}
for r in sample:
    n, t, fx, lv = r["pr"], r["truth"], r["facts"], r["live"]
    d, g, z = res.get((n, "dpx_mem")), res.get((n, "glm")), res.get((n, "0gm"))
    for k, e in (("dpx_mem", d), ("glm", g), ("0gm", z)):
        usd[k] += (e or {}).get("usd", 0) or 0
    live_res = {"verdict": lv.get("m"), "confidence": float(lv.get("c") or 0)}
    arms["live"].append((t, lv.get("m")))
    pol["live (as it ran: critic + GLM)"].append((t, lv.get("final")))
    pol["live (critic, second off)"].append((t, v4.final(live_res, fx, OFF)[0]))
    if d:
        arms["dpx_mem"].append((t, d["verdict"]))
        pol["dpx_mem (critic, second off)"].append((t, v4.final({"verdict": d["verdict"],
                                                                  "confidence": d["confidence"]}, fx, OFF)[0]))
    for arm, e, key in (("glm", g, "live + GLM second"), ("0gm", z, "live + 0GM second")):
        if e and e.get("verdict"):
            second_agree[arm].append((t, e["verdict"]))
            pol[key].append((t, v4.final({**live_res, "second": {"verdict": e["verdict"]}}, fx,
                                         {"use_critic": False})[0]))
    rows_out.append({"pr": n, "type": r["type"], "truth": t, "merged": r["merged"], "live_m": lv.get("m"),
                     "live_c": lv.get("c"), "live_final": lv.get("final"), "live_second": lv.get("sec"),
                     "dpx": d and d["verdict"], "dpx_c": d and d["confidence"], "glm": g and g.get("verdict"),
                     "0gm": z and z.get("verdict"),
                     "dpx_final": d and v4.final({"verdict": d["verdict"], "confidence": d["confidence"]}, fx, OFF)[0],
                     "note": r["note"][:160]})
report = {"model_verdict": {k: metrics(v) for k, v in arms.items()},
          "policy": {k: policy(v) for k, v in pol.items()},
          "second_opinion_vs_truth": {k: metrics(v) for k, v in second_agree.items()},
          "usd": ledger_usd(), "rows": rows_out}
json.dump(report, open(os.path.join(out, "score.json"), "w"), indent=1)
print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=1))
print("| PR | type | truth | live model (conf) → final | DPX+mem (conf) → policy | GLM | 0GM |")
for x in rows_out:
    print(f"| #{x['pr']} | {x['type']} | {x['truth']} | {x['live_m']} ({x['live_c']}) → {x['live_final']} | "
          f"{x['dpx']} ({x['dpx_c']}) → {x['dpx_final']} | {x['glm']} | {x['0gm']} |")
