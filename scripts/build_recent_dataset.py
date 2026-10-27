import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""A second backtest set: Rounds AD and AE (26-27 Oct), decided by Gathin on the round files' recommendations.

Usage: build_recent_dataset.py <bare git dir with refs/pull/N/head> <out dir>

Truth comes from the round files' buckets (merge, merge-with-fix, ask = rework, close, hold). The PR is rebuilt
at the commit the live bot last reviewed (its sticky's sha) when that commit is still reachable, else at the
PR's last head; main is the round's main. The live bot's own judgement (the sticky's mb-review JSON: the
model's verdict, confidence and the policy's final call, all from Opus 5.5 on v4.1.1) is kept as the baseline.
"""
import json
import re
import subprocess

from maintainer_bot import checklists, dataset, facts as facts_mod, v4

git, out = sys.argv[1], sys.argv[2]
REPO = "Gathin23/cleanyourtv"
LAUNCH = os.path.expanduser("~/Arsenal/cleanyourtv-launch")
ROUNDS = {"round-ad.md": ("b06ab21105c49900cb1ed76b24414dba1e21d0db", "2026-10-26T18:00:00Z"),
          "round-ae.md": ("59b6ac76", "2026-10-27T03:00:00Z")}
BUCKET = [(r"^## Merge as is", "merge"), (r"^## Merge with a fix", "merge-with-fix"), (r"^## Ask", "rework"),
          (r"^## Close", "close"), (r"^## Hold", "hold")]


def sh(*a, check=True):
    r = subprocess.run(list(a), capture_output=True, text=True, errors="replace")
    if check and r.returncode:
        raise RuntimeError(r.stderr[:300])
    return r.stdout


def parse(path):
    rows, cur = {}, None
    for line in open(path, encoding="utf-8"):
        if line.startswith("## "):
            cur = next((v for pat, v in BUCKET if re.match(pat, line)), None)
            continue
        m = re.match(r"^\| #(\d+) \|", line)
        if cur and m:
            cells = [c.strip() for c in line.split("|")]
            rows[int(m.group(1))] = (cur, cells[-2] if len(cells) > 2 else "")
    return rows


def sticky(n):
    cs = json.loads(sh("gh", "api", f"repos/{REPO}/issues/{n}/comments?per_page=100") or "[]")
    for c in cs:
        b = c.get("body") or ""
        if "<!-- maintainer-bot" in b:
            m = re.search(r"<!-- mb-review (\{.*?\}) -->", b, re.S)
            sha = re.search(r"maintainer-bot sha=([0-9a-f]+)", b)
            return (json.loads(m.group(1)) if m else {}), (sha.group(1) if sha else "")
    return {}, ""


os.makedirs(os.path.join(out, "prs"), exist_ok=True)
want = {}
for fname, (main, when) in ROUNDS.items():
    for n, (truth, why) in parse(os.path.join(LAUNCH, fname)).items():
        want[n] = (truth, why, main, when)
print(len(want), "PRs")
sh("git", "-C", git, "fetch", "-q", "origin", *[f"+refs/pull/{n}/head:refs/pull/{n}/head" for n in want], check=False)

rows, views = [], {}
for n, (truth, why, main, when) in sorted(want.items()):
    p = json.loads(sh("gh", "api", f"repos/{REPO}/pulls/{n}"))
    review, rsha = sticky(n)
    head = sh("git", "-C", git, "rev-parse", f"refs/pull/{n}/head", check=False).strip()
    if rsha:
        full = sh("git", "-C", git, "rev-parse", "--verify", "-q", rsha + "^{commit}", check=False).strip()
        if full:
            head = full
    if not head:
        print("no head for", n)
        continue
    main_full = sh("git", "-C", git, "rev-parse", main).strip()
    base = sh("git", "-C", git, "merge-base", main_full, head, check=False).strip() or main_full
    files = dataset.pr_files_from_git(git, base, head)
    snap = {"pr": n, "title": p["title"], "author": p["user"]["login"], "created_at": p["created_at"],
            "body": (p.get("body") or "")[:4000], "files": files}
    if main_full not in views:
        views[main_full] = v4.main_view(git, main_full)
    mv = views[main_full]
    c = v4.conflicts(git, main_full, head)
    fx = facts_mod.compute_v4(snap, existing_list_folders=mv["list_folders"], main_locales=mv["locales"],
                              examples_readme=mv["examples_readme"], theme_folders_on_main=mv["themes"],
                              addon_folders_on_main=mv["addons"], conflicts_with_main=v4.blocking_conflicts(c))
    if c:
        fx["conflict_files"] = c if isinstance(c, list) else []
    fx["main_at_review"] = main_full
    row = {"pr": n, "title": p["title"], "author": p["user"]["login"], "created_at": p["created_at"],
           "truth": truth, "fix": "", "decided_at": when, "merge_sha": "", "maintainer_note": why[:700],
           "snapshot_note": "the commit the live bot reviewed" if rsha else "last head", "main_at": main_full,
           "head": head, "split": "recent", "live": review, "facts": fx}
    json.dump({**snap, **{k: row[k] for k in ("truth", "decided_at", "main_at", "head")}},
              open(os.path.join(out, "prs", f"{n}.json"), "w"))
    rows.append(row)
with open(os.path.join(out, "truth.jsonl"), "w") as f:
    for r in rows:
        f.write(json.dumps({k: v for k, v in r.items() if k != "facts"}) + "\n")
json.dump({str(r["pr"]): r["facts"] for r in rows}, open(os.path.join(out, "facts_v4.json"), "w"))
print("wrote", len(rows), "rows;", sum(1 for r in rows if r["live"]), "with a live review")
