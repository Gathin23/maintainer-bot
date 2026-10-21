"""Replay past PRs through the bot and compare with what the maintainer actually did.

Resumable: results are appended per model to runs/<name>/results.jsonl and already-judged PRs are skipped.
"""
from __future__ import annotations

import json
import os
import random
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import dataset, decide, facts as facts_mod, memory
from .ledger import BudgetExceeded, Ledger
from .router import ToolCallFailed

CLASSES = ["merge", "merge-with-fix", "rework", "close", "hold"]


def prepare(data_dir: str, git_dir: str) -> list[dict]:
    """Facts for every PR as of its decision time (no model calls). Cached in data_dir/facts.json."""
    cache = os.path.join(data_dir, "facts.json")
    rows = dataset.load(data_dir)
    if os.path.exists(cache):
        with open(cache, encoding="utf-8") as f:
            fx = json.load(f)
        for r in rows:
            r["facts"] = fx[str(r["pr"])]
            r["top_dirs"] = r["facts"]["top_dirs"]
        return rows
    folder_cache: dict[str, set] = {}
    locale_cache: dict[str, int] = {}
    snaps = {r["pr"]: dataset.load_snapshot(data_dir, r["pr"]) for r in rows}
    import re
    pr_folders = {n: sorted({m.group(1) for f in s["files"] if (m := re.match(r"^examples/([^/]+)/", f["path"]))})
                  for n, s in snaps.items()}
    out = {}
    for r in rows:
        # main as the maintainer saw it: the merge's first parent for merged PRs, else main at decision time
        key = (r["merge_sha"] + "^1") if r.get("merge_sha") else r["decided_at"][:13]
        if key not in folder_cache:
            if r.get("merge_sha"):
                folder_cache[key] = dataset.list_folders_at_commit(git_dir, key)
                locale_cache[key] = dataset.locale_count_at_commit(git_dir, key)
            else:
                folder_cache[key] = dataset.list_folders_at(git_dir, r["decided_at"])
                locale_cache[key] = dataset.locale_count_at(git_dir, r["decided_at"])
        others = defaultdict(list)
        for o in rows:
            if o["pr"] != r["pr"] and o["created_at"] < r["decided_at"] < o["decided_at"]:
                if len(pr_folders.get(o["pr"], [])) <= 3:  # an omnibus PR is not a competing list
                    for fo in pr_folders.get(o["pr"], []):
                        others[fo].append(o["pr"])
        fx = facts_mod.compute(snaps[r["pr"]], existing_list_folders=folder_cache[key],
                               other_open_list_folders=dict(others), locale_count=locale_cache[key])
        # other PRs open at the same time with a near-identical title: likely the same TV or feature
        tw = memory._words(r["title"])
        sim = []
        for o in rows:
            if o["pr"] != r["pr"] and o["created_at"] < r["decided_at"] and (o["decided_at"] > r["created_at"]):
                ow = memory._words(o["title"])
                if tw and ow and len(tw & ow) / len(tw | ow) >= 0.5:
                    sim.append(o["pr"])
        fx["similar_titles_open_at_the_time"] = sim[:5]
        out[str(r["pr"])] = fx
        r["facts"] = fx
        r["top_dirs"] = fx["top_dirs"]
    with open(cache, "w", encoding="utf-8") as f:
        json.dump(out, f)
    return rows


def stratified_sample(rows: list[dict], n: int, seed: int = 21) -> list[dict]:
    """A fixed sample with every class represented roughly in proportion, minorities boosted."""
    rnd = random.Random(seed)
    by = defaultdict(list)
    for r in rows:
        by[r["truth"]].append(r)
    quota = {c: max(8, round(n * len(v) / len(rows))) for c, v in by.items()}
    while sum(quota.values()) > n:
        biggest = max(quota, key=quota.get)
        quota[biggest] -= 1
    pick = []
    for c, v in by.items():
        pick += rnd.sample(v, min(len(v), quota[c]))
    return sorted(pick, key=lambda r: r["decided_at"])


def run(rows: list[dict], *, data_dir: str, run_dir: str, model: str, rules_md: str, ledger: Ledger,
        workers: int = 6, limit: int | None = None) -> list[dict]:
    os.makedirs(run_dir, exist_ok=True)
    path = os.path.join(run_dir, "results.jsonl")
    done = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    e = json.loads(line)
                    if "error" not in e:  # failed calls are retried on the next run
                        done[e["pr"]] = e
    todo = [r for r in rows if r["pr"] not in done][: limit if limit else None]

    def one(r: dict) -> dict:
        snap = dataset.load_snapshot(data_dir, r["pr"])
        ex = memory.similar(r, rows, k=8)
        res = decide.decide(snap, r["facts"], rules_md=rules_md, examples_md=memory.render(ex),
                            diff=dataset.trim_diff(snap["files"]), model=model, ledger=ledger,
                            tag=f"backtest:{r['pr']}")
        return {"pr": r["pr"], "truth": r["truth"], "decided_at": r["decided_at"], "title": r["title"],
                "examples": [e["pr"] for e in ex], **res}

    stop = False
    with ThreadPoolExecutor(workers) as pool, open(path, "a", encoding="utf-8") as out:
        futs = {pool.submit(one, r): r for r in todo}
        for fut in as_completed(futs):
            try:
                e = fut.result()
            except BudgetExceeded:
                stop = True
                continue
            except (ToolCallFailed, Exception) as err:  # record and keep going
                e = {"pr": futs[fut]["pr"], "truth": futs[fut]["truth"], "error": str(err)[:200]}
            done[e["pr"]] = e
            out.write(json.dumps(e) + "\n")
            out.flush()
    if stop:
        print("stopped: spend cap reached")
    return [done[r["pr"]] for r in rows if r["pr"] in done]


def reapply(results: list[dict], rows: list[dict]) -> list[dict]:
    """Re-run the deterministic overrides on saved model verdicts (no model calls): for tuning the rules."""
    fx = {r["pr"]: r["facts"] for r in rows}
    out = []
    for r in results:
        if "model_verdict" not in r:
            out.append(r)
            continue
        v, why = facts_mod.apply_overrides(r["model_verdict"], fx[r["pr"]])
        out.append({**r, "verdict": v, "override": why})
    return out


def metrics(results: list[dict]) -> dict:
    ok = [r for r in results if "verdict" in r]
    cm = defaultdict(Counter)
    for r in ok:
        cm[r["truth"]][r["verdict"]] += 1
    agree = sum(cm[c][c] for c in CLASSES)
    # "merge family" agreement: merge vs merge-with-fix is a small difference in practice
    fam = lambda v: "merge" if v in ("merge", "merge-with-fix") else v
    agree_fam = sum(1 for r in ok if fam(r["truth"]) == fam(r["verdict"]))
    escalated = [r for r in ok if r["verdict"] == "hold" and r["truth"] != "hold"]
    safety = [r for r in ok if r["verdict"] in ("merge", "merge-with-fix") and r["truth"] in ("close", "rework", "hold")]
    decided = [r for r in ok if r["verdict"] != "hold"]
    agree_decided = sum(1 for r in decided if fam(r["truth"]) == fam(r["verdict"]))
    per_class = {c: {"n": sum(cm[c].values()), "recall": (cm[c][c] / sum(cm[c].values())) if sum(cm[c].values()) else None,
                     "precision": (cm[c][c] / sum(cm[t][c] for t in CLASSES)) if sum(cm[t][c] for t in CLASSES) else None}
                 for c in CLASSES}
    model_only = Counter((r["truth"], r.get("model_verdict")) for r in ok)
    return {
        "n": len(ok), "errors": len(results) - len(ok),
        "exact_agreement": agree / len(ok) if ok else 0,
        "merge_family_agreement": agree_fam / len(ok) if ok else 0,
        "escalated_to_maintainer": len(escalated),
        "agreement_when_bot_decides": agree_decided / len(decided) if decided else 0,
        "bot_decides_share": len(decided) / len(ok) if ok else 0,
        "safety_misses": safety,
        "confusion": {t: dict(cm[t]) for t in CLASSES},
        "per_class": per_class,
        "overrides": sum(1 for r in ok if r.get("override")),
        "model_only_agreement": sum(1 for r in ok if fam(r.get("model_verdict") or "") == fam(r["truth"])) / len(ok) if ok else 0,
    }
