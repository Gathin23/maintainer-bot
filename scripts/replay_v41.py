import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""Replay 22 Oct's live v4 reviews under v4.1, with no model calls (and optionally a few with them).

Each v4 sticky comment stores the model's judgement (verdict, confidence, critic, second opinion). The replay
rebuilds the PR at the reviewed commit and main at the moment of the review from git (a bare clone; nothing
checked out or run), recomputes the facts with v4.1 and runs the v4.1 policy on the stored judgement, so
every verdict change comes from the new facts and rules alone.

Usage: replay_v41.py <fetch dir with prs.json + comments.json> <bare git dir> <out.json> [--model PR,PR,...]
--model re-runs the decision (Opus 5.5 + critic + second opinion) for the listed PRs with the v4.1 prompt,
for the fixes that change what the model is told (add-ons, duplicates); ledger runs/ledger-v41.jsonl, cap $5.
"""
import json
import re
import subprocess
from datetime import datetime, timedelta

from maintainer_bot import checklists, dataset, facts as facts_mod, ledger, live, retrieval, v4

fetch, git, out = sys.argv[1:4]
model_prs = {int(x) for x in sys.argv[sys.argv.index("--model") + 1].split(",")} if "--model" in sys.argv else set()
prs = {p["number"]: p for p in json.load(open(os.path.join(fetch, "prs.json")))}
comments = json.load(open(os.path.join(fetch, "comments.json")))


def g(*args, check=False):
    r = subprocess.run(["git", "-C", git, *args], capture_output=True, text=True, errors="replace")
    return r.returncode, r.stdout


nums = sorted(int(n) for n in comments)
for i in range(0, len(nums), 60):
    g("fetch", "-q", "origin", *[f"+refs/pull/{n}/head:refs/pr/{n}" for n in nums[i:i + 60]])
for n in sorted(prs):  # one bad ref fails a whole batch: fetch what is still missing one by one
    if g("rev-parse", "--verify", "-q", f"refs/pr/{n}")[0]:
        g("fetch", "-q", "origin", f"+refs/pull/{n}/head:refs/pr/{n}")
g("fetch", "-q", "origin", "+refs/heads/main:refs/remotes/origin/main")


def sticky(n):
    for c in comments.get(str(n), []):
        if "<!-- maintainer-bot" in c["body"]:
            return c
    return None


def main_at(when: str) -> str:
    return g("rev-list", "-1", "--first-parent", f"--before={when}", "origin/main")[1].strip()


def head_at(n: int, sha: str) -> str:
    code, full = g("rev-parse", "--verify", "-q", sha + "^{commit}")
    return full.strip() if code == 0 else ""


def pr_files(base: str, head: str) -> list[dict]:
    mb = g("merge-base", base, head)[1].strip()
    return dataset.pr_files_from_git(git, mb, head) if mb else []


views, rows = {}, []
merges = dataset.merge_commits(git, "origin/main")
for n in nums:
    c = sticky(n)
    if not c or n not in prs:
        continue
    data = live.read_data(c["body"])
    if not data.get("m"):
        continue
    sha = re.search(r"sha=([0-9a-f]{7,40})", c["body"]).group(1)
    head = head_at(n, sha)
    when = c["upd"]
    base = main_at(when)
    if not head or not base:
        print("skip", n, "commit not found")
        continue
    files = pr_files(base, head)
    p = prs[n]
    snap = {"pr": n, "title": p["title"], "body": (p.get("body") or "")[:4000], "created_at": p["createdAt"],
            "files": files, "author": p["author"]["login"], "head_sha": head}
    if base not in views:
        views[base] = v4.main_view(git, base)
    mv = views[base]
    c_files = v4.conflicts(git, base, head)
    fx = facts_mod.compute_v4(snap, existing_list_folders=mv["list_folders"], main_locales=mv["locales"],
                              examples_readme=mv["examples_readme"], theme_folders_on_main=mv["themes"],
                              addon_folders_on_main=mv["addons"], conflicts_with_main=bool(c_files))
    if isinstance(c_files, list):
        fx["conflict_files"] = c_files
    ci = re.search(r"CI fails: ([^\n]+)", c["body"])  # a live-only fact at review time, kept from the sticky
    if ci:
        fx["ci_failed"] = [x.strip() for x in ci.group(1).split(",")]
    # duplicates: PRs open at the time of the review, and main's last 7 days
    me = {"pr": n, "title": p["title"], "body": p.get("body") or "", "created_at": p["createdAt"],
          "files": [f["path"] for f in files], "file_patches": files}
    refs, words = facts_mod.issue_refs(me), facts_mod.title_words(p["title"])
    others = []
    week = (datetime.fromisoformat(when.replace("Z", "+00:00")) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for m, o in prs.items():
        closed = o.get("mergedAt") or o.get("closedAt")
        merged = bool(o.get("mergedAt")) and week <= o["mergedAt"] < when
        if m == n or o["createdAt"] > when:
            continue
        if not merged and (o["createdAt"] >= p["createdAt"] or (closed and closed < when)):
            continue
        od = {"pr": m, "title": o["title"], "body": o.get("body") or "", "created_at": o["createdAt"], "merged": merged}
        ow = facts_mod.title_words(o["title"])
        jacc = len(words & ow) / len(words | ow) if words and ow else 0
        if (refs & facts_mod.issue_refs(od)) or jacc >= 0.3:
            oh = g("rev-list", "-1", f"--before={when}", f"refs/pr/{m}")[1].strip()
            if merged and m in merges:
                ofiles = dataset.pr_files_from_git(git, merges[m]["sha"] + "^1", merges[m]["sha"] + "^2")
            else:
                ofiles = pr_files(base, oh) if oh else []
            if oh or ofiles:
                od["files"] = [f["path"] for f in ofiles]
                od["added"] = facts_mod.added_lines_of(ofiles)
                od["contained"] = bool(oh) and g("merge-base", "--is-ancestor", oh, head)[0] == 0
            else:
                od["files"] = []
            others.append(od)
    since = (datetime.fromisoformat(when.replace("Z", "+00:00")) - timedelta(days=7)).isoformat()
    commits, texts = [], {}
    for path in [x for x in me["files"] if facts_mod._meaningful(x)][:5]:
        log = g("log", base, f"--since={since}", "--format=%H%x1f%B%x1e", "--", path)[1]
        for rec in log.split("\x1e"):
            if rec.strip():
                h, _, msg = rec.strip().partition("\x1f")
                commits.append({"sha": h, "message": msg, "files": [path]})
        code, text = g("show", f"{base}:{path}")
        texts[path] = text if code == 0 else None
    fx.update(facts_mod.duplicate_facts(me, others, recent_commits=commits, main_texts=texts))
    ptype = checklists.pr_type([f["path"] for f in files], p["title"])
    res = {"verdict": data["m"], "confidence": float(data.get("c") or 0), "critic": {"blocker": bool(data.get("crit"))},
           "second": {"verdict": data.get("sec")}}
    v41, why, fix = v4.final(res, fx)
    outcome = ("merged" if p.get("mergedAt") else "closed" if p["state"] == "CLOSED" else
               "open:" + ",".join(l["name"] for l in p["labels"] if l["name"] in ("needs-rework", "on-hold")))
    rows.append({"pr": n, "title": p["title"][:80], "type": ptype, "v4": data.get("final"), "model": data["m"],
                 "conf": data.get("c"), "v41": v41, "why": why[:200], "fix": fix[:200],
                 "lean": v4.lean(res) if v41 == "hold" else None, "outcome": outcome,
                 "flags": {k: fx[k] for k in ("conflict_files", "possible_duplicates", "already_on_main_live",
                                               "core_packages_disabled", "hide_without_undo", "binary_files",
                                               "addon_folders") if fx.get(k)},
                 "_snap": snap, "_fx": fx})

if model_prs:
    L = ledger.Ledger("runs/ledger-v41.jsonl", 5.0)
    rules = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "examples", "cleanyourtv",
                              "MAINTAINER.md"), encoding="utf-8").read()
    prec = live.load_precedents(open(os.environ["MB_PRECEDENTS"], encoding="utf-8").read())
    for r in rows:
        if r["pr"] not in model_prs:
            continue
        hist, files_by_pr, bodies = prec
        row = {"pr": r["pr"], "title": r["_snap"]["title"], "decided_at": "2026-10-22T23:59:59Z", "truth": None,
               "type": r["type"], "facts": r["_fx"], "batch": {}}
        idx = retrieval.Index([h for h in hist if h["pr"] != r["pr"]] + [row],
                              {**files_by_pr, r["pr"]: r["_snap"]["files"] and [f["path"] for f in r["_snap"]["files"]]},
                              {**bodies, r["pr"]: r["_snap"]["body"]})
        try:
            res = v4.judge(row, r["_snap"], idx, rules_md=rules, model="claude-opus-5.5", critic_model="claude-sonnet-5",
                           second_model="glm-5.3-flash", ledger=L, system_extra=live.LIVE_SYSTEM)
        except Exception as e:  # noqa: BLE001
            r["model_rerun"] = {"error": str(e)[:160]}
            continue
        v, why, fix = v4.final(res, r["_fx"])
        r["model_rerun"] = {"model": res["verdict"], "conf": res["confidence"], "v41": v, "why": why[:200],
                            "fix": fix[:200], "reasons": res.get("reasons", [])[:2]}
    print("model spend", round(L.spent, 3))

for r in rows:
    r.pop("_snap"), r.pop("_fx")
json.dump(rows, open(out, "w"), indent=1)
changed = [r for r in rows if r["v41"] != r["v4"]]
print(len(rows), "replayed;", len(changed), "verdicts change")
