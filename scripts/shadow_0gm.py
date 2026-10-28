import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""Shadow comparison on Rounds AG/AG2 (28 Oct): today's live review vs DPX + fresh memory (Opus 5.5), and GLM vs
0GM as the second opinion. Small and capped.

Usage: shadow_0gm.py BARE_GIT_DIR OUT_DIR [--n 20] [--cap 4.5] [--estimate]

Truth: the reviewer verdicts in ~/Arsenal/cleanyourtv-launch/round-ag/review-*.md (applied as Round AG/AG2), with
GitHub's merged flag as a cross-check. Each PR is rebuilt at the commit the reviewers read (their head SHA) with
main as they had it (fa1a2f00 for AG, 9f086119 for AG2), from a bare clone; nothing is checked out or run.
Arms:
  live      the live bot's stored judgement on that PR (its sticky's mb-review record): no model call
  dpx_mem   Opus 5.5 with context-blocks DPX and the memory refreshed up to Round AF (leak-free: AF ended
            27 Oct 13:50 UTC, before Round AG); decision call only
  second    GLM-5.3-Flash and 0GM (reasoning medium) as the second opinion on today's prompt (rules and
            precedents as on main at fa1a2f00), scored with Opus's stored verdict through the real policy
The sample PRs themselves are left out of every memory.
"""
import argparse
import glob
import json
import re
import subprocess
from collections import Counter

from maintainer_bot import batch, checklists, context, dataset, facts as facts_mod, live, router, v4
from maintainer_bot.ledger import Ledger

ap = argparse.ArgumentParser()
ap.add_argument("git")
ap.add_argument("out")
ap.add_argument("--n", type=int, default=20)
ap.add_argument("--cap", type=float, default=4.5, help="absolute cap on the rollout ledger")
ap.add_argument("--ledger", default="runs/rollout/ledger-2026-10-28.jsonl")
ap.add_argument("--estimate", action="store_true", help="build prompts and stop (no model calls)")
a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)
GIT, REPO = a.git, "Gathin23/cleanyourtv"
LAUNCH = os.path.expanduser("~/Arsenal/cleanyourtv-launch")
MAINS = {"ag": "fa1a2f00", "ag2": "9f086119"}
WHEN = {"ag": "2026-10-28T01:30:00Z", "ag2": "2026-10-28T03:00:00Z"}
TRUTH = {"MERGE": "merge", "MERGE+FIX": "merge-with-fix", "ASK": "rework", "CLOSE": "close", "HOLD": "hold"}
MEM = "runs/rollout/memory-until-af"


def git(*args):
    r = subprocess.run(["git", "-C", GIT, *args], capture_output=True, text=True, errors="replace")
    return r.stdout if r.returncode == 0 else ""


def gh(path):
    r = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    return json.loads(r.stdout or "null")


# ---------- truth ----------
reviews = {}
for f in sorted(glob.glob(f"{LAUNCH}/round-ag/review-*.md")):
    rnd = "ag" if f[-4] in "ABC" else "ag2"
    for line in open(f, encoding="utf-8"):
        m = re.match(r"^\| #(\d+) \| ([A-Z+]+)([^|]*)\| ([0-9a-f]{7,40}) \| @?([^|]*)\|(.*)", line)
        if m and m.group(2) in TRUTH:
            n = int(m.group(1))
            reviews[n] = {"pr": n, "round": rnd, "truth": TRUTH[m.group(2)], "sha": m.group(4),
                          "clock": "after" in m.group(3) or "clock" in m.group(6).lower(),
                          "note": re.sub(r"\s+", " ", m.group(6)).strip(" |")[:600]}
print(len(reviews), "reviewed PRs in Rounds AG/AG2")

# ---------- the live bot's stored judgements ----------
cache_path = os.path.join(a.out, "stickies.json")
stickies = json.load(open(cache_path)) if os.path.exists(cache_path) else {}
for n in reviews:
    if str(n) not in stickies:
        cs = gh(f"repos/{REPO}/issues/{n}/comments?per_page=100") or []
        body = next((c["body"] for c in cs if live.MARKER in (c.get("body") or "")), "")
        sha = re.search(r"sha=([0-9a-f]+)", body)
        stickies[str(n)] = {"data": live.read_data(body), "sha": sha.group(1) if sha else ""}
json.dump(stickies, open(cache_path, "w"))


def usable(r):
    s = stickies[str(r["pr"])]
    full = git("rev-parse", "--verify", "-q", r["sha"] + "^{commit}").strip()
    return (not r["clock"] and s["data"].get("m") and full
            and (s["sha"].startswith(r["sha"][:12]) or r["sha"].startswith(s["sha"][:12])))


pool = sorted((r for r in reviews.values() if usable(r)), key=lambda r: r["pr"])
want = {"merge": 5, "merge-with-fix": 3, "rework": 5, "close": 3, "hold": 4}
sample = []
for t, k in want.items():
    group = [r for r in pool if r["truth"] == t]
    step = max(1, len(group) // k) if group else 1
    sample += group[::step][:k]
sample = sample[:a.n]
print("usable", len(pool), Counter(r["truth"] for r in pool), "sample", len(sample), Counter(r["truth"] for r in sample))

# ---------- rebuild the PRs as the reviewers read them ----------
views, rows, snaps = {}, [], {}
for r in reviews.values():   # every reviewed PR: other open PRs for the X block
    main = git("rev-parse", MAINS[r["round"]]).strip()
    head = git("rev-parse", "--verify", "-q", r["sha"] + "^{commit}").strip() or \
        git("rev-parse", f"refs/pull/{r['pr']}/head").strip()
    if not head:
        continue
    base = git("merge-base", main, head).strip() or main
    files = dataset.pr_files_from_git(GIT, base, head)
    p = gh(f"repos/{REPO}/pulls/{r['pr']}") if r in sample else {}
    snaps[r["pr"]] = {"pr": r["pr"], "title": (p or {}).get("title") or f"#{r['pr']}",
                      "author": ((p or {}).get("user") or {}).get("login", ""),
                      "body": ((p or {}).get("body") or "")[:4000], "created_at": (p or {}).get("created_at", ""),
                      "files": files, "default_branch": "main", "merged": bool((p or {}).get("merged_at")),
                      "main": main}
for r in sample:
    s, main = snaps[r["pr"]], snaps[r["pr"]]["main"]
    if main not in views:
        views[main] = v4.main_view(GIT, main)
    mv = views[main]
    c = v4.conflicts(GIT, main, git("rev-parse", "--verify", "-q", r["sha"] + "^{commit}").strip())
    fx = facts_mod.compute_v4(s, existing_list_folders=mv["list_folders"], main_locales=mv["locales"],
                              examples_readme=mv["examples_readme"], theme_folders_on_main=mv["themes"],
                              addon_folders_on_main=mv["addons"], conflicts_with_main=v4.blocking_conflicts(c))
    if c:
        fx["conflict_files"] = c if isinstance(c, list) else []
    fx["main_at_review"] = main
    paths = [f["path"] for f in s["files"]]
    rows.append({"pr": r["pr"], "title": s["title"], "decided_at": WHEN[r["round"]], "truth": None,
                 "type": checklists.pr_type(paths, s["title"]), "facts": fx, "batch": {}, "review": r})

files_by_pr = {n: [f["path"] for f in s["files"]] for n, s in snaps.items()}
titles = {n: s["title"] for n, s in snaps.items()}
others = [{"pr": n, "created_at": "", "decided_at": "9999"} for n in snaps]
for row in rows:
    ov = v4.overlaps(batch.open_overlaps({**row, "created_at": ""}, others, files_by_pr, titles, limit=12))[:6]
    if ov:
        row["batch"]["other_open_prs_touching_the_same_files"] = ov


def memory(prec_text: str, rules_path: str):
    hist, files, bodies = live.load_precedents(prec_text)
    mine = {r["pr"] for r in rows}
    hist = [h for h in hist if h["pr"] not in mine]
    for r in rows:
        files[r["pr"]] = files_by_pr[r["pr"]]
        bodies[r["pr"]] = snaps[r["pr"]]["body"]
    return v4.MemoryIndex(hist, rows, files, bodies), open(rules_path, encoding="utf-8").read()


old_prec = git("show", "fa1a2f00:.github/maintainer/precedents.jsonl")
os.makedirs(os.path.join(a.out, "rules"), exist_ok=True)
old_rules_path = os.path.join(a.out, "rules", "MAINTAINER-fa1a2f00.md")
open(old_rules_path, "w").write(git("show", "fa1a2f00:.github/maintainer/MAINTAINER.md"))
idx_old, rules_old = memory(old_prec, old_rules_path)
idx_new, rules_new = memory(open(f"{MEM}/precedents.jsonl").read(), f"{MEM}/MAINTAINER.md")


def related(row):
    own = files_by_pr[row["pr"]]
    out = []
    for o in row["batch"].get("other_open_prs_touching_the_same_files", [])[:6]:
        s = snaps.get(o["pr"])
        if s:
            out.append(f"### Open PR #{o['pr']}: {s['title'][:100]} (shares {', '.join(o['shared_files'][:3])})\n"
                       + context.full_diff(s["files"], 5000))
    main = row["facts"]["main_at_review"]
    paths = [p for p in own if p not in v4.TABLE_FILES][:12]
    if paths:
        since = git("log", "-1", "--format=%ct", main).strip()
        since = str(int(since) - 7 * 86400) if since else "0"
        for line in git("log", "--first-parent", f"--since={since}", "--format=%h %s", "-n", "6", main, "--",
                        *paths).splitlines():
            sha = line.split()[0]
            out.append(f"### Merged on main this week: {line}\n"
                       + context.cut(git("show", "--format=", "-m", "--first-parent", sha, "--", *paths), 4000))
    return "\n\n".join(out)


prompts = {}
for row in rows:
    s = snaps[row["pr"]]
    dpx, used, info = context.build(row, s, rules_new, idx_new, "DPX", related(row))
    today = v4.prompt(row, s, rules_old, v4.retrieval.render(idx_old.similar(row, k=5)))
    prompts[row["pr"]] = {"dpx": dpx, "today": today, "info": info}
est = {n: (len(p["dpx"]) / 3.0, len(p["today"]) / 3.0) for n, p in prompts.items()}
opus = router.price("claude-opus-5.5")
print("est. Opus DPX input $%.2f (no cache), median prompt %.0fK chars" % (
    sum(e[0] for e in est.values()) * opus.prompt, sorted(len(p["dpx"]) for p in prompts.values())[len(prompts) // 2] / 1000))
if a.estimate:
    raise SystemExit(0)

L = Ledger(a.ledger, a.cap)
start = L.spent
res_path = os.path.join(a.out, "results.jsonl")
done = {}
if os.path.exists(res_path):
    for line in open(res_path):
        e = json.loads(line)
        done[(e["pr"], e["arm"])] = e


def save(e):
    done[(e["pr"], e["arm"])] = e
    with open(res_path, "a") as f:
        f.write(json.dumps(e) + "\n")


SYSTEM = v4.SYSTEM + live.LIVE_SYSTEM
import threading
from concurrent.futures import ThreadPoolExecutor
_lock = threading.Lock()
_save = save


def save(e):  # noqa: F811 - thread-safe
    with _lock:
        _save(e)


def one(row):
    n = row["pr"]
    if v4.always_maintainer(row["facts"]):
        for arm in ("dpx_mem", "glm", "0gm"):
            if (n, arm) not in done:
                save({"pr": n, "arm": arm, "verdict": "hold", "confidence": 0, "skipped": "always the maintainer"})
        return
    if (n, "dpx_mem") not in done:
        before = L.spent
        try:
            d = router.call_tool(model="claude-opus-5.5", system=SYSTEM + context.LONG_NOTE, user=prompts[n]["dpx"],
                                 tool=v4.TOOL, ledger=L, max_tokens=3000, tag=f"shadow-dpx:{n}")
            save({"pr": n, "arm": "dpx_mem", "verdict": d.get("verdict") if d.get("verdict") in v4.FAMILY else "hold",
                  "confidence": float(d.get("confidence") or 0), "reasons": d.get("reasons") or [],
                  "fix": d.get("fix", ""), "usd": round(L.spent - before, 4), "info": prompts[n]["info"]})
        except Exception as e:  # noqa: BLE001
            print(n, "dpx failed", str(e)[:120])
            if "cap" in str(e):
                return
    for arm, model, thinking in (("glm", "glm-5.3-flash", None), ("0gm", "0gm-1.0-35b-a3b", "medium")):
        if (n, arm) in done:
            continue
        before = L.spent
        try:
            d = router.call_tool_any(model=model, system=v4.SYSTEM, user=prompts[n]["today"], tool=v4.TOOL, ledger=L,
                                     max_tokens=9000, tag=f"shadow-second-{arm}:{n}", thinking=thinking, retries=3,
                                     timeout=300)
            save({"pr": n, "arm": arm, "verdict": d.get("verdict"), "confidence": float(d.get("confidence") or 0),
                  "usd": round(L.spent - before, 5)})
        except Exception as e:  # noqa: BLE001
            print(n, arm, "failed", str(e)[:120])
    print(n, {k[1]: done[k].get("verdict") for k in list(done) if k[0] == n}, f"spent ${L.spent - start:.3f}",
          flush=True)


with ThreadPoolExecutor(4) as pool:
    list(pool.map(one, rows))

json.dump({"rows": [{"pr": r["pr"], "type": r["type"], "truth": r["review"]["truth"], "round": r["review"]["round"],
                     "note": r["review"]["note"], "merged": snaps[r["pr"]]["merged"],
                     "live": stickies[str(r["pr"])]["data"], "facts": r["facts"]} for r in rows]},
          open(os.path.join(a.out, "sample.json"), "w"), indent=1, default=str)
print(f"spent this run ${L.spent - start:.3f}; rollout ledger total ${L.spent:.3f}")
