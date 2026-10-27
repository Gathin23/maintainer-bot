import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""Metrics for the 0GM research arms. Usage: [MB_DATASET=recent] eval_0gm.py ARM [ARM ...] (opus-baseline = stored).

Prints one JSON line per arm, and writes runs/0gm[-recent]/eval.json.
"""
import json
import statistics

sys.argv, ARMS = sys.argv[:1], sys.argv[1:]
import research_0gm as R  # noqa: E402  (loads the dataset)
from maintainer_bot import v4  # noqa: E402

CLOSEISH = ("close", "showcase", "addon")
SAFETY_FLAGS = ("uninstall_steps", "core_packages_disabled", "protected_packages_disabled",
                "pairing_or_input_packages_disabled", "hide_without_undo", "private_dns_setup",
                "firmware_updater_disabled", "adds_internet_permission", "new_permissions", "network_use",
                "changed_config_defaults", "home_path_touched", "manifest_changes", "sensitive_paths")


def pr_rc(said, truth, keys):
    tp = sum(1 for s, t in zip(said, truth) if s in keys and t in keys)
    p = sum(1 for s in said if s in keys)
    a = sum(1 for t in truth if t in keys)
    return {"precision": round(tp / p, 3) if p else None, "recall": round(tp / a, 3) if a else None,
            "said": p, "actual": a}


def load(arm):
    """ARM, or BASE+second=OTHER: BASE's judgement with OTHER's verdict as the second opinion (critic off)."""
    if "+second=" in arm:
        base, other = arm.split("+second=")
        sec = {e["pr"]: e for e in R.results(other)}
        out = []
        for e in R.results(base):
            o = sec.get(e["pr"])
            out.append({**e, "second": {"verdict": o["verdict"], "confidence": o.get("confidence")} if o else {},
                        "critic": {}})
        return out
    return R.results(arm)


COMMON: set = set()


def arm_metrics(arm):
    res = [e for e in load(arm) if e["pr"] in R.by and not e.get("skipped_model")]
    if COMMON:
        res = [e for e in res if e["pr"] in COMMON]
    truth = [R.by[e["pr"]]["truth"] for e in res]
    said = [e["verdict"] for e in res]
    fam = sum(1 for s, t in zip(said, truth) if v4.family(s) == v4.family(t))
    dirn = sum(1 for s, t in zip(said, truth) if v4.DIRECTION[v4.family(s)] == v4.DIRECTION[v4.family(t)])
    hold = sum(1 for s in said if s == "hold")
    out = {"arm": arm, "n": len(res),
           "raw_same_home": round(fam / len(res), 3), "raw_same_direction": round(dirn / len(res), 3),
           "raw_hold_rate": round(hold / len(res), 3),
           "close": pr_rc(said, truth, CLOSEISH), "rework": pr_rc(said, truth, ("rework", "theme")),
           "accept": pr_rc(said, truth, ("merge", "merge-with-fix"))}
    # merges said where the maintainer did not accept: the expensive mistake
    out["raw_wrong_merges"] = [e["pr"] for e, t in zip(res, truth)
                               if e["verdict"] in v4.ACCEPT and v4.family(t) != "accept"]
    # PRs with a safety-relevant fact where the maintainer did not accept: did the model avoid a plain merge?
    risky = [(e, t) for e, t in zip(res, truth)
             if any(R.by[e["pr"]]["facts"].get(k) for k in SAFETY_FLAGS) and v4.family(t) != "accept"]
    out["safety_relevant_not_accepted"] = len(risky)
    out["safety_caught"] = sum(1 for e, t in risky if e["verdict"] not in v4.ACCEPT)
    pol = {"use_critic": False, "use_second": False}
    m = v4.evaluate(res, R.by, pol)
    out["policy_decision_only"] = {k: (round(m[k], 3) if isinstance(m[k], float) else m[k])
                                   for k in ("decided", "coverage", "precision", "precision_same_direction")}
    out["policy_decision_only"]["wrong_merges"] = [x["pr"] for x in m["wrong_merges"]]
    if arm == "opus-baseline" or "+second=" in arm:
        m2 = v4.evaluate(res, R.by, {"use_critic": arm == "opus-baseline"})
        out["policy_as_shipped"] = {k: (round(m2[k], 3) if isinstance(m2[k], float) else m2[k])
                                    for k in ("decided", "coverage", "precision", "precision_same_direction")}
        out["policy_as_shipped"]["wrong_merges"] = [x["pr"] for x in m2["wrong_merges"]]
    st = [e.get("stats") or {} for e in res]
    if any(s.get("usd") is not None for s in st):
        usd = [s.get("usd", 0) for s in st]
        secs = [s.get("secs", 0) for s in st]
        out["usd_per_review"] = round(statistics.mean(usd), 5)
        out["usd_total"] = round(sum(usd), 4)
        out["in_tokens_median"] = statistics.median([s.get("in", 0) for s in st]) if st[0].get("in") is not None else None
        out["secs_median"] = statistics.median(secs)
        out["secs_p90"] = sorted(secs)[int(.9 * len(secs))]
    return out


if __name__ == "__main__":
    sets = []
    for a in ARMS:
        sets.append({e["pr"] for e in load(a) if e["pr"] in R.by and not e.get("skipped_model")})
    COMMON.update(set.intersection(*sets))
    print("common PRs:", len(COMMON))
    allm = [arm_metrics(a) for a in ARMS]
    for m in allm:
        print(json.dumps(m))
    json.dump(allm, open(f"{R.OUT}/eval.json", "w"), indent=1)
