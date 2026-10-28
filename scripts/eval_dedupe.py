import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""Score a dedupe pass (dedupe --out FILE) against git and the round notes. No model calls.

Usage: eval_dedupe.py RESULT.json BARE_GIT_DIR [OUT.json]

Textual truth, per pair: merge one PR into main, then the other on top (git merge-tree, nothing checked out);
the pair collides when the second merge conflicts in a file both PRs change. Order: A first, or B first when A
alone conflicts with main; when both already conflict with main, the two heads are merged directly.
Known pairs (recall): the collisions named in the Round AG/AG2 notes (28 Oct).
"""
import json
import subprocess

res = json.load(open(sys.argv[1]))
GIT = sys.argv[2]
ADITH = [2271, 2274, 2275, 2276, 2278, 2279, 2280, 2284, 2287, 2288]
KNOWN_PAIRS = {frozenset(p) for p in [(2317, 2321), (2317, 2326), (2321, 2326), (2316, 2317), (1990, 2114)]} | \
    {frozenset((a, b)) for i, a in enumerate(ADITH) for b in ADITH[i + 1:]}
KNOWN_MAIN = {(2289, "tcl-g10-google-tv"), (2282, "formovie-mprojm05"),
              (1666, "xiaomi-mitv-astp0")}   # #1666: Round AA ask "fold into xiaomi-mitv-astp0"


def git(*a):
    r = subprocess.run(["git", "-C", GIT, *a], capture_output=True, text=True)
    return r.returncode, r.stdout


main = git("rev-parse", "main")[1].strip()
cache = {}


def head(n):
    return git("rev-parse", f"refs/pull/{n}/head")[1].strip()


def merge(a, b):
    """(tree, conflicted files) of merging b into a."""
    rc, out = git("merge-tree", "--write-tree", "--name-only", "--no-messages", a, b)
    lines = out.splitlines()
    return (lines[0] if lines else ""), (set(lines[1:]) if rc == 1 else set())


def own_files(n):
    base = git("merge-base", main, head(n))[1].strip()
    return set(git("diff", "--name-only", base, head(n))[1].split())


def textual(a, b):
    key = (a, b)
    if key in cache:
        return cache[key]
    ha, hb = head(a), head(b)
    both = own_files(a) & own_files(b)
    ta, ca = merge(main, ha)
    tb, cb = merge(main, hb)
    if ca and cb:   # both already conflict with main: compare their own changes directly
        _, cc = merge(ha, hb)
        out = bool(cc & both)
    else:
        first, second, t = (ha, hb, ta) if not ca else (hb, ha, tb)
        c1 = git("commit-tree", t, "-p", main, "-p", first, "-m", "eval")[1].strip()
        _, cc = merge(c1, second)
        out = bool(cc & both)
    cache[key] = out
    return out


rows = []
for c in res["pairs"]:
    r = c["result"]
    t = textual(c["a"], c["b"])
    rows.append({"a": c["a"], "b": c["b"], "kind": r["kind"], "source": r.get("source"), "hub": bool(r.get("hub")),
                 "textual_conflict": t, "known": frozenset((c["a"], c["b"])) in KNOWN_PAIRS})
reported = [x for x in rows if x["kind"] not in ("none", "error")]
scored = [x for x in reported if x["textual_conflict"] is not None]
tp_text = [x for x in scored if x["textual_conflict"] or x["kind"] in ("stacked", "duplicate", "collision", "supersedes", "split") and x["known"]]
cleared = [x for x in rows if x["kind"] == "none"]
cleared_scored = [x for x in cleared if x["textual_conflict"] is not None]
known_found = sorted(tuple(sorted(k)) for k in KNOWN_PAIRS if any(frozenset((x["a"], x["b"])) == k for x in reported))
known_missed = sorted(tuple(sorted(k)) for k in KNOWN_PAIRS if tuple(sorted(k)) not in known_found)
mains = {(m["pr"], m["folder"]): m["result"]["kind"] for m in res["main"]}
main_reported = {k for k, v in mains.items() if v == "same-device"}
out = {
    "stats": res["stats"],
    "pairs_reported": len(reported), "pairs_scored_by_git": len(scored),
    "precision_textual": round(len(tp_text) / len(scored), 3) if scored else None,
    "by_source": {s: {"reported": sum(1 for x in reported if (x["source"], x["hub"]) == s),
                      "true": sum(1 for x in tp_text if (x["source"], x["hub"]) == s),
                      "scored": sum(1 for x in scored if (x["source"], x["hub"]) == s)}
                  for s in {(x["source"], x["hub"]) for x in reported}},
    "model_cleared": len(cleared), "model_cleared_but_conflict": sum(1 for x in cleared_scored if x["textual_conflict"]),
    "known_pairs": len(KNOWN_PAIRS), "known_found": len(known_found), "known_missed": known_missed,
    "known_main": sorted(KNOWN_MAIN), "known_main_found": sorted(KNOWN_MAIN & main_reported),
    "main_reported": sorted(main_reported), "main_false": sorted(main_reported - KNOWN_MAIN),
    "rows": rows,
}
out["by_source"] = {f"{k[0]}{' (hub lines)' if k[1] else ''}": v for k, v in out["by_source"].items()}
if len(sys.argv) > 3:
    json.dump(out, open(sys.argv[3], "w"), indent=1, default=str)
print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=1, default=str))
