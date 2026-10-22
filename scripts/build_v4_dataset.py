import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""The v4 backtest set: every maintainer decision on cleanyourtv from 21 Oct 10:00 UTC (after the v3 dataset)
to the end of 22 Oct's morning rounds (Round M, the 21 Oct cleanup, the hub sweep, Round N, the TV run).

Usage: build_v4_dataset.py <fetch dir with prs.json, decided.json, comments.json> <bare git dir> <out dir>

Truth uses the v4 verdicts: merge, merge-with-fix, rework, close, showcase, addon, theme, hold.
A close is a showcase close when the maintainer's closing comment offers a fork + SHOWCASE row, an addon close
when it invites the PR under addons/. PRs their own author closed are left out (not a maintainer decision).
Split by time: train = decided before 2026-10-21T23:30Z (Round M, the cleanup round), test = the rest (22 Oct).
"""
import json
import re

from maintainer_bot import dataset

fetch, git, out = sys.argv[1], sys.argv[2], sys.argv[3]
SPLIT_AT = "2026-10-21T23:30:00Z"
HUB = "2026-10-22T00:13:00Z"     # the hub sweep's "still open on purpose" decision
TVRUN = "2026-10-22T01:30:00Z"   # tv-test-2026-10-22.md verdicts

prs = {p["number"]: p for p in json.load(open(os.path.join(fetch, "prs.json")))}
comments = json.load(open(os.path.join(fetch, "comments.json")))
decided = json.load(open(os.path.join(fetch, "decided.json")))

AUTHOR_CLOSED = {802, 782, 711, 662, 655, 646, 429, 355}
CLOSE_NOT_SHOWCASE = {472, 706}  # base rule (root, uninstall): a plain close, the showcase is only a side note
# fixes folded into merges, from the round notes (the merge commits don't always say)
FIXED = {326, 572, 757, 747, 775, 518, 745, 765, 722, 695, 407, 510, 640, 450, 719, 744, 762, 764, 799, 730,
         338, 657, 678, 697, 709, 716, 633, 635, 639, 643, 653, 654, 656, 682, 684, 497, 636}
# decided but not acted on GitHub: held on purpose in the hub sweep, TV-run verdicts, rebase asks
EXTRA = {
    **{n: ("hold", HUB, "tile-menu family: kept open until the hold-OK design is decided") for n in (464, 573, 756, 746, 758, 327)},
    **{n: ("hold", HUB, "needs a TV run first") for n in (311, 446, 546, 39, 566, 698)},
    **{n: ("hold", HUB, "China TCL rule: touches a safety rule in PROMPT.md, the maintainer decides") for n in (442, 693, 715, 753)},
    **{n: ("hold", HUB, "gethari Companion series: scope call for the maintainer") for n in (618, 619, 621, 622)},
    565: ("rework", TVRUN, "On a TV whose Home claimants include com.duokan.factorytest/.FactoryLauncher the guard counts it as another Home and lets a list disable the Home owner. Add the factory-test launcher to the exclusion list plus a test, and rebase onto main (disable.sh/ps1 conflict)."),
    687: ("rework", TVRUN, "Works, but it is a second hold-OK tile menu; keep one family (#464) and fold the Menu-key trigger into it."),
    787: ("rework", "2026-10-22T01:05:00Z", "Conflicts with main in docs/TROUBLESHOOTING.md; please rebase onto main."),
    790: ("rework", "2026-10-22T01:05:00Z", "Conflicts with main on the RESTART= line in tools/theme.sh; please rebase and keep both changes."),
}


def gathin_note(n: int, until: str) -> str:
    cs = [c for c in comments.get(str(n), {}).get("comments", [])
          if c["by"] == "Gathin23" and c["at"] <= until and not c["body"].startswith("/bot")]
    return re.sub(r"\s+", " ", cs[-1]["body"]).strip()[:700] if cs else ""


def classify_close(n: int, note: str) -> str:
    if n in CLOSE_NOT_SHOWCASE:
        return "close"
    if re.search(r"addons/|add-on", note, re.I):
        return "addon"
    if re.search(r"SHOWCASE|fork", note):
        return "showcase"
    return "close"


merges = dataset.merge_commits(git, "origin/main")
rows = []
for n, kind, at in decided:
    if n in AUTHOR_CLOSED and n != 680:
        continue
    p = prs[n]
    row = {"pr": n, "title": p["title"], "author": p["author"]["login"], "created_at": p["createdAt"]}
    if kind == "merged":
        mc = merges.get(n)
        if not mc:
            print("no merge commit for", n)
            continue
        fixed = bool(mc["note"]) or n in FIXED
        row.update(truth="merge-with-fix" if fixed else "merge", fix=mc["note"][:600], decided_at=at,
                   merge_sha=mc["sha"], maintainer_note=gathin_note(n, "2026-10-23"))
    elif kind == "closed":
        note = gathin_note(n, at[:17] + "59Z")
        if n == 680:  # the author closed it right after the showcase offer
            note = gathin_note(n, "2026-10-23")
        row.update(truth=classify_close(n, note), fix="", decided_at=at, maintainer_note=note)
    else:
        row.update(truth="rework" if kind == "needs-rework" else "hold", fix="", decided_at=at,
                   maintainer_note=gathin_note(n, "2026-10-23"))
    rows.append(row)
seen = {r["pr"] for r in rows}
for n, (truth, at, note) in EXTRA.items():
    if n in seen or n not in prs and not comments.get(str(n)):
        continue
    p = prs.get(n)
    if not p:
        print("not in the fetched PR list:", n)
        continue
    rows.append({"pr": n, "title": p["title"], "author": p["author"]["login"], "created_at": p["createdAt"],
                 "truth": truth, "fix": "", "decided_at": at, "maintainer_note": note})

# fetch heads for the PRs that were not merged (into the scratch bare repo only)
need = [r["pr"] for r in rows if not r.get("merge_sha")]
for i in range(0, len(need), 60):
    dataset.sh(["git", "fetch", "-q", "origin", *[f"+refs/pull/{n}/head:refs/pr/{n}" for n in need[i:i + 60]]],
               cwd=git, check=False)

os.makedirs(os.path.join(out, "prs"), exist_ok=True)
done = []
for r in rows:
    try:
        if r.get("merge_sha"):
            base, head = f"{r['merge_sha']}^1", f"{r['merge_sha']}^2"
            r["snapshot_note"] = "PR as merged (second parent), before fixes"
            r["main_at"] = dataset.sh(["git", "rev-parse", base], cwd=git).strip()
        else:
            ref = f"refs/pr/{r['pr']}"
            head = dataset.sh(["git", "rev-list", "-1", f"--before={r['decided_at']}", ref], cwd=git,
                              check=False).strip() or dataset.sh(["git", "rev-parse", ref], cwd=git, check=False).strip()
            if not head:
                print("no head for", r["pr"])
                continue
            r["main_at"] = dataset.sh(["git", "rev-list", "-1", f"--before={r['decided_at']}", "origin/main"],
                                      cwd=git).strip()
            base = r["main_at"]
            r["snapshot_note"] = "last PR commit dated before the decision"
        r["head"] = dataset.sh(["git", "rev-parse", head], cwd=git).strip()
        files = dataset.pr_files_from_git(git, base, head)
        snap = {**r, "body": (prs[r["pr"]].get("body") or "")[:4000] if "body" in prs[r["pr"]] else "", "files": files}
        with open(os.path.join(out, "prs", f"{r['pr']}.json"), "w", encoding="utf-8") as f:
            json.dump(snap, f)
        r["split"] = "train" if r["decided_at"] < SPLIT_AT else "test"
        done.append(r)
    except Exception as e:  # noqa: BLE001
        print("skip", r["pr"], str(e)[:160])
done.sort(key=lambda r: r["decided_at"])
with open(os.path.join(out, "truth.jsonl"), "w", encoding="utf-8") as f:
    for r in done:
        f.write(json.dumps(r) + "\n")
from collections import Counter
print(len(done), Counter(r["truth"] for r in done), Counter(r["split"] for r in done))
