"""Build the backtest set from a repo's real history (read-only).

Ground truth = what the maintainer actually did:
  merged, merge commit has an "on merge" note or conflict list  -> merge-with-fix (the note is the fix)
  merged, plain merge commit                                     -> merge
  closed without merge                                           -> close
  open with the rework label                                     -> rework
  open with the hold label                                       -> hold
Open PRs without either label were never decided and are left out.

Snapshot = the PR as the maintainer saw it when deciding:
  merged: the merge commit's second parent against the merge base (the PR as merged, before fixes)
  others: the last PR commit dated before the decision time (refs/pull/N/head fetched into refs/pr/N)
Commit dates are author-set, so a few snapshots of reworked PRs may include a later push; recorded per PR.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

DIFF_FILE_CHARS = 2500
DIFF_TOTAL_CHARS = 14000


def sh(args: list[str], cwd: str | None = None, check: bool = True) -> str:
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"{' '.join(args[:4])}…: {r.stderr.strip()[:300]}")
    return r.stdout


def gh_json(args: list[str]) -> object:
    return json.loads(sh(["gh", *args]))


def iso(ts: str | None) -> datetime | None:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else None


def merge_commits(git_dir: str, branch: str = "origin/main") -> dict[int, dict]:
    """PR number -> {sha, note} from merge commits named 'Merge PR #N' or GitHub's 'Merge pull request #N'."""
    out = {}
    raw = sh(["git", "log", branch, "--merges", "--format=%H%x1f%s%x1f%b%x1e"], cwd=git_dir)
    for rec in raw.split("\x1e"):
        rec = rec.strip()
        if not rec:
            continue
        sha, subj, body = (rec.split("\x1f") + ["", ""])[:3]
        m = re.search(r"(?:Merge PR|Merge pull request) #(\d+)", subj)
        if not m:
            continue
        n = int(m.group(1))
        note = ""
        b = body.strip()
        if re.search(r"on merge", b, re.I) or b.startswith("# Conflicts"):
            note = b
        out.setdefault(n, {"sha": sha, "note": note})
    return out


def label_times(repo: str, number: int, names: set[str]) -> dict[str, str]:
    """When each label was last added (issue events API)."""
    events = gh_json(["api", f"repos/{repo}/issues/{number}/events", "--paginate"])
    out = {}
    for e in events:
        if e.get("event") == "labeled" and (e.get("label") or {}).get("name") in names:
            out[e["label"]["name"]] = e["created_at"]
    return out


def pr_files_from_git(git_dir: str, base: str, head: str) -> list[dict]:
    """Per-file additions/deletions/status and a trimmed patch for base...head."""
    files = []
    numstat = sh(["git", "diff", "--numstat", "-M", f"{base}...{head}"], cwd=git_dir)
    status = {}
    for line in sh(["git", "diff", "--name-status", "-M", f"{base}...{head}"], cwd=git_dir).splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            status[parts[-1]] = {"A": "added", "D": "removed", "M": "modified"}.get(parts[0][0], "renamed")
    for line in numstat.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        a, d, path = parts[0], parts[1], parts[-1]
        if "=>" in path:  # rename shorthand
            path = re.sub(r"\{[^}]*=> ([^}]*)\}", r"\1", path).replace("//", "/")
        binary = a == "-"
        patch = ""
        if not binary:
            patch = sh(["git", "diff", "-M", f"{base}...{head}", "--", path], cwd=git_dir, check=False)
        files.append({"path": path, "additions": 0 if binary else int(a), "deletions": 0 if binary else int(d),
                      "status": status.get(path, "modified"), "binary": binary, "patch": patch})
    return files


def trim_diff(files: list[dict]) -> str:
    """A compact diff for the prompt: every file named, patches cut per file and in total."""
    out, total = [], 0
    for f in sorted(files, key=lambda f: (f.get("binary"), -(f["additions"] + f["deletions"]))):
        head = f"### {f['path']} ({f['status']}, +{f['additions']} -{f['deletions']}{', binary' if f.get('binary') else ''})"
        out.append(head)
        if f.get("binary") or total >= DIFF_TOTAL_CHARS:
            continue
        body = "\n".join(l for l in (f.get("patch") or "").splitlines()
                         if not l.startswith(("diff --git", "index ", "--- ", "+++ ")))
        cut = body[:DIFF_FILE_CHARS]
        if len(body) > len(cut):
            cut += f"\n… ({len(body) - len(cut)} more chars)"
        out.append(cut)
        total += len(cut)
    return "\n".join(out)


def list_folders_at(git_dir: str, when: str, branch: str = "origin/main") -> set[str]:
    commit = sh(["git", "rev-list", "-1", f"--before={when}", branch], cwd=git_dir).strip()
    if not commit:
        return set()
    names = sh(["git", "ls-tree", "--name-only", f"{commit}:examples"], cwd=git_dir, check=False)
    return {n for n in names.split() if n and "." not in n}


def list_folders_at_commit(git_dir: str, commit: str) -> set[str]:
    names = sh(["git", "ls-tree", "--name-only", f"{commit}:examples"], cwd=git_dir, check=False)
    return {n for n in names.split() if n and "." not in n}


def locale_count_at_commit(git_dir: str, commit: str) -> int:
    names = sh(["git", "ls-tree", "-r", "--name-only", commit, "launcher/app/src/main/res"], cwd=git_dir, check=False)
    return sum(1 for n in names.split() if re.search(r"/values-[^/]+/strings\.xml$", n))


def locale_count_at(git_dir: str, when: str, branch: str = "origin/main") -> int:
    """How many translated launcher strings.xml files existed on main at that time."""
    commit = sh(["git", "rev-list", "-1", f"--before={when}", branch], cwd=git_dir).strip()
    if not commit:
        return 0
    names = sh(["git", "ls-tree", "-r", "--name-only", commit, "launcher/app/src/main/res"], cwd=git_dir, check=False)
    return sum(1 for n in names.split() if re.search(r"/values-[^/]+/strings\.xml$", n))


def build(repo: str, git_dir: str, out_dir: str, *, rework_label="needs-rework", hold_label="on-hold",
          workers: int = 8) -> list[dict]:
    """Write out_dir/truth.jsonl and out_dir/prs/<n>.json; returns the truth rows."""
    os.makedirs(os.path.join(out_dir, "prs"), exist_ok=True)
    prs = gh_json(["pr", "list", "-R", repo, "--state", "all", "--limit", "2000", "--json",
                   "number,title,author,state,createdAt,mergedAt,closedAt,labels,body,isDraft,baseRefName"])
    merges = merge_commits(git_dir)
    rows = []
    need_refs = []
    for p in prs:
        labels = {l["name"] for l in p["labels"]}
        author = (p.get("author") or {}).get("login", "")
        if author == repo.split("/")[0] or (p.get("author") or {}).get("is_bot"):
            continue  # the maintainer's own PRs and bots are not part of the test
        row = {"pr": p["number"], "title": p["title"], "author": author, "created_at": p["createdAt"]}
        if p["state"] == "MERGED":
            mc = merges.get(p["number"])
            if not mc:
                continue  # merged through GitHub's UI or squash: no snapshot we trust
            row.update(truth="merge-with-fix" if mc["note"] else "merge", fix=mc["note"][:600],
                       decided_at=p["mergedAt"], merge_sha=mc["sha"])
        elif p["state"] == "CLOSED":
            row.update(truth="close", fix="", decided_at=p["closedAt"])
            need_refs.append(p["number"])
        elif rework_label in labels or hold_label in labels:
            row.update(truth="rework" if rework_label in labels else "hold", fix="", decided_at=None,
                       label=rework_label if rework_label in labels else hold_label)
            need_refs.append(p["number"])
        else:
            continue
        row["_raw"] = p
        rows.append(row)

    # fetch PR heads for the non-merged ones (read-only from GitHub's side)
    for i in range(0, len(need_refs), 60):
        chunk = need_refs[i:i + 60]
        sh(["git", "fetch", "-q", "origin", *[f"+refs/pull/{n}/head:refs/pr/{n}" for n in chunk]],
           cwd=git_dir, check=False)

    def snapshot(row: dict) -> dict | None:
        p = row.pop("_raw")
        try:
            if row.get("decided_at") is None:
                times = label_times(repo, row["pr"], {row["label"]})
                row["decided_at"] = times.get(row["label"]) or p["createdAt"]
            if row["truth"] in ("merge", "merge-with-fix"):
                base, head = f"{row['merge_sha']}^1", f"{row['merge_sha']}^2"
                row["snapshot_note"] = "PR as merged (second parent), before fixes"
            else:
                ref = f"refs/pr/{row['pr']}"
                head = sh(["git", "rev-list", "-1", f"--before={row['decided_at']}", ref], cwd=git_dir,
                          check=False).strip() or sh(["git", "rev-parse", ref], cwd=git_dir, check=False).strip()
                if not head:
                    return None
                base = "origin/main"
                row["snapshot_note"] = "last PR commit dated before the decision"
            files = pr_files_from_git(git_dir, base, head)
            snap = {**row, "body": (p.get("body") or "")[:4000], "files": files}
            with open(os.path.join(out_dir, "prs", f"{row['pr']}.json"), "w", encoding="utf-8") as f:
                json.dump(snap, f)
            return row
        except Exception as e:  # keep going; the report lists what was skipped
            row["error"] = str(e)[:200]
            return None

    with ThreadPoolExecutor(workers) as ex:
        done = [r for r in ex.map(snapshot, rows) if r]
    done.sort(key=lambda r: r["decided_at"])
    with open(os.path.join(out_dir, "truth.jsonl"), "w", encoding="utf-8") as f:
        for r in done:
            f.write(json.dumps(r) + "\n")
    return done


def load(out_dir: str) -> list[dict]:
    with open(os.path.join(out_dir, "truth.jsonl"), encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def load_snapshot(out_dir: str, n: int) -> dict:
    with open(os.path.join(out_dir, "prs", f"{n}.json"), encoding="utf-8") as f:
        return json.load(f)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
