import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""0GM long-context research on the v4 backtest set (219 decided PRs). Usage:

    research_0gm.py sizes                       prompt sizes per block set, no calls
    research_0gm.py run ARM [PR ...]            run one arm (all PRs, or the listed ones); resumable
    research_0gm.py eval ARM [ARM ...]          metrics for finished arms (and the stored Opus baseline)

ARM is model:blocks:thinking, e.g. 0gm-1.0-35b-a3b::off (today's prompt), 0gm-1.0-35b-a3b:DFRPXI:off (everything).
Spend goes to runs/ledger-0gm.jsonl with a hard cap.
"""
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

from maintainer_bot import ledger, longctx, v4
from maintainer_bot.ledger import BudgetExceeded

GIT = os.environ.get("MB_GIT_DIR", os.path.expanduser("~/Arsenal/tv-vibehack"))
CAP = float(os.environ.get("MB_CAP", "150"))
# The rules as the decisions' reviewers saw them. The bot repo's current MAINTAINER.md names several v4 test PRs
# (#672-#674, #687, #751, #794, ...) that were mined after the test, so using it here leaks the answers.
RULES_V4 = subprocess.run(["git", "-C", os.path.expanduser("~/Arsenal/maintainer-bot"), "show",
                           "ce0cfd7:examples/cleanyourtv/MAINTAINER.md"], capture_output=True, text=True).stdout
RULES_RECENT = subprocess.run(["git", "-C", GIT, "show", "59b6ac76:.github/maintainer/MAINTAINER.md"],
                              capture_output=True, text=True).stdout
OUT = "runs/0gm"
os.makedirs(OUT, exist_ok=True)
longctx.load_issue_cache(f"{OUT}/issues.json")

DATASET = os.environ.get("MB_DATASET", "v4")


LAUNCH = os.path.expanduser("~/Arsenal/cleanyourtv-launch")
MEM_ROUNDS = {"round-ab-decisions.md": "2026-10-25T12:00:00Z", "round-ac-decisions.md": "2026-10-26T05:00:00Z"}
MEM_BUCKETS = [(r"^## Merge as is", "merge"), (r"^## Merge with a fix", "merge-with-fix"), (r"^## Ask \(new", "rework"),
               (r"^## Close", "close"), (r"^## Hold", "hold")]


def round_memory() -> list[dict]:
    """The maintainer's decisions from Rounds AB and AC (25-26 Oct, before the recent set), as retrieval memory:
    the live precedents file stops at 22 Oct."""
    import re as _re
    out = []
    for fname, when in MEM_ROUNDS.items():
        cur = None
        for line in open(os.path.join(LAUNCH, fname), encoding="utf-8"):
            if line.startswith("## "):
                cur = next((v for pat, v in MEM_BUCKETS if _re.match(pat, line)), None)
                continue
            m = _re.match(r"^\| #(\d+) \| (.*?) \|", line)
            if cur and m:
                cells = [c.strip() for c in line.split("|")]
                note = " ".join(c for c in cells[3:] if c and c != "-")
                out.append({"pr": int(m.group(1)), "title": _re.sub(r"\s*\(@[^)]*\)\s*$", "", m.group(2)),
                            "truth": cur, "decided_at": when, "maintainer_note": note[:700], "fix": ""})
    return out


def rules_addendum() -> str:
    """Policy lines the maintainer set in Rounds AB and AC, quoted from the round notes (before the recent set)."""
    ac = open(os.path.join(LAUNCH, "round-ac-decisions.md"), encoding="utf-8").read()
    ab = open(os.path.join(LAUNCH, "round-ab-decisions.md"), encoding="utf-8").read()
    bar = next(l for l in ac.splitlines() if l.startswith("The same bar as Round AB"))
    def section(text, start):
        i = text.index(start)
        j = text.index("\n## ", i + 3)
        return text[i:j]
    return ("## Policies set in Rounds AB and AC (25-26 Oct), from the maintainer's round notes\n" + bar + "\n\n"
            + section(ab, "## The calls I was least sure of") + "\n" + section(ac, "## Calls I'm least sure of"))


def load_recent():
    """Rounds AD/AE: facts were computed at build time; precedents are the live file the bot read then."""
    from maintainer_bot import batch, dataset, checklists, live, retrieval
    d = "data/cleanyourtv-recent"
    rows = dataset.load(d)
    snaps = {r["pr"]: dataset.load_snapshot(d, r["pr"]) for r in rows}
    facts = json.load(open(f"{d}/facts_v4.json"))
    for r in rows:
        r["facts"] = facts[str(r["pr"])]
        r["type"] = checklists.pr_type([f["path"] for f in snaps[r["pr"]]["files"]], r["title"])
        r["family"] = v4.family(r["truth"])
    prec = longctx._git(GIT, "show", "59b6ac76:.github/maintainer/precedents.jsonl")
    hist, files, bodies = live.load_precedents(prec)
    if os.environ.get("MB_MEMORY"):
        hist += round_memory()
    mine = {r["pr"] for r in rows}
    hist = [h for h in hist if h["pr"] not in mine]
    for r in rows:
        files[r["pr"]] = [f["path"] for f in snaps[r["pr"]]["files"]]
        bodies[r["pr"]] = snaps[r["pr"]].get("body") or ""
    index = v4.MemoryIndex(hist, rows, files, bodies)
    titles = {**{h["pr"]: h["title"] for h in hist}, **{r["pr"]: r["title"] for r in rows}}
    for r in rows:
        b = {}
        ov = v4.overlaps(batch.open_overlaps(r, rows, files, titles, limit=12))[:6]
        if ov:
            b["other_open_prs_touching_the_same_files"] = ov
        aom = batch.already_on_main(snaps[r["pr"]]["files"], GIT, r["facts"].get("main_at_review", ""))
        if aom:
            b["already_on_main"] = aom
        r["batch"] = b
    return rows, snaps, index


RULES = RULES_RECENT if DATASET == "recent" else RULES_V4
assert len(RULES) > 5000, "rules not found"
if DATASET == "recent" and os.environ.get("MB_MEMORY"):
    longctx.ADDENDUM = rules_addendum()
if DATASET == "recent":
    OUT = "runs/0gm-recent" + ("-mem" if os.environ.get("MB_MEMORY") else "")
    os.makedirs(OUT, exist_ok=True)
    rows, snaps, index = load_recent()
else:
    rows, snaps, index = v4.load("data/cleanyourtv-v4", GIT, "data/cleanyourtv")
by = {r["pr"]: r for r in rows}


def arm_dir(arm: str) -> str:
    return f"{OUT}/" + arm.replace(":", "_").replace("/", "-")


def parse(arm: str):
    model, blocks, thinking = (arm.split(":") + ["", ""])[:3]
    return model, blocks, (None if thinking in ("", "off") else thinking)


def run(arm: str, prs: list[int] | None, workers: int = 8):
    model, blocks, thinking = parse(arm)
    d = arm_dir(arm)
    os.makedirs(d, exist_ok=True)
    path = f"{d}/results.jsonl"
    done = set()
    if os.path.exists(path):
        done = {json.loads(l)["pr"] for l in open(path) if l.strip() and "error" not in json.loads(l)}
    todo = [r for r in rows if (not prs or r["pr"] in prs) and r["pr"] not in done]
    L = ledger.Ledger("runs/ledger-0gm.jsonl", CAP)
    before = L.spent
    print(arm, "todo", len(todo), "spent so far", round(before, 3))
    with ThreadPoolExecutor(workers) as pool, open(path, "a") as fh:
        futs = {pool.submit(longctx.judge, r, snaps[r["pr"]], model=model, blocks=blocks, thinking=thinking,
                            index=index, snaps=snaps, git_dir=GIT, rules_md=RULES, ledger=L): r for r in todo}
        for fut in as_completed(futs):
            try:
                e = fut.result()
            except BudgetExceeded:
                print("cap reached")
                continue
            except Exception as err:  # noqa: BLE001
                e = {"pr": futs[fut]["pr"], "error": str(err)[:200]}
            fh.write(json.dumps(e) + "\n")
            fh.flush()
    longctx.save_issue_cache(f"{OUT}/issues.json")
    print(arm, "this run $", round(L.spent - before, 4))


def results(arm: str) -> list[dict]:
    if arm == "opus-baseline" and DATASET == "recent":
        out = []
        for r in rows:
            lv = r.get("live") or {}
            if lv.get("m"):
                out.append({"pr": r["pr"], "verdict": lv["m"], "confidence": float(lv.get("c") or 0),
                            "critic": {"blocker": bool(lv.get("crit"))}, "second": {"verdict": lv.get("sec")},
                            "live_final": lv.get("final")})
        return out
    if arm == "opus-baseline":
        out = []
        for split in ("train", "test"):
            out += [json.loads(l) for l in open(f"runs/v4-{split}/results.jsonl") if l.strip()]
        return [e for e in out if "error" not in e]
    path = f"{arm_dir(arm)}/results.jsonl"
    seen = {}
    for l in open(path):
        if l.strip():
            e = json.loads(l)
            if "error" not in e:
                seen[e["pr"]] = e
    return list(seen.values())


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "sizes":
        import statistics
        for blocks in ("", "D", "DF", "DR", "DP", "DX", "DI", "DFRPXI"):
            sz = [len(longctx.build_user(r, snaps[r["pr"]], blocks=blocks, index=index, snaps=snaps, git_dir=GIT,
                                         rules_md=RULES)) for r in rows]
            print(f"{blocks or 'today':8} median {statistics.median(sz):>8.0f}  p90 {sorted(sz)[int(.9 * len(sz))]:>8}  "
                  f"max {max(sz):>8}  ~tokens median {statistics.median(sz) / 3.6:>7.0f}")
        longctx.save_issue_cache(f"{OUT}/issues.json")
    elif mode == "run":
        run(sys.argv[2], [int(x) for x in sys.argv[3:]] or None)
    elif mode == "eval":
        for arm in sys.argv[2:]:
            res = results(arm)
            for label, pol in (("decision only", {"use_critic": False, "use_second": False}),):
                m = v4.evaluate(res, by, pol)
                print(arm, label, json.dumps({k: m[k] for k in ("n", "decided", "coverage", "precision",
                                                                  "precision_same_direction")}),
                      "wrong merges", len(m["wrong_merges"]), "safety", len(m["safety_misses"]))
