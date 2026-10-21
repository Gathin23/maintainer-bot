"""Live review of one pull request: read it through the GitHub API, decide with the v3 policy on the 0G router,
and keep ONE sticky comment plus a few labels up to date. Phase 1 only suggests: it never merges, closes,
approves or pushes.

Safety model (see README): nothing here checks out or runs PR code. The PR is read as data through the API
(title, body, file list, patches). The rules and the precedent file are read from the base repo's default
branch, never from the PR, so a PR cannot rewrite its own rules.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone

import requests

from . import checklists, facts as facts_mod, retrieval, v3
from .ledger import BudgetExceeded, Ledger

API = os.environ.get("GITHUB_API_URL", "https://api.github.com")
MARKER = "<!-- maintainer-bot"
FOOTER = "<sub>Reviewed by maintainer-bot · runs on [0G Private Computer](https://pc.0g.ai)</sub>"

# labels the bot may add or remove; it never touches any other label
TYPE_LABELS = {"tv-list": "tv-list", "launcher": "launcher", "tools": "scripts", "docs": "docs", "showcase": "docs",
               "theme": "launcher"}
VERDICT_LABELS = {"merge": "bot-suggests:merge", "merge-with-fix": "bot-suggests:merge-with-fix",
                  "rework": "bot-suggests:rework", "close": "bot-suggests:close", "hold": "needs-maintainer"}
PRIORITY_LABELS = ("p0", "p1", "p2", "p3")
BOT_OWNED = set(VERDICT_LABELS.values()) | set(PRIORITY_LABELS)
ALLOWED = BOT_OWNED | set(TYPE_LABELS.values()) | {"google-tv"}

# PRs that change the bot, CI or review config are never judged by the bot
SKIP_PATHS = (".github/", ".opencodereview/")

LIVE_SYSTEM = """

You are writing a public review note on the PR BEFORE any maintainer decision. Write `comment` as one to three
short sentences to the author: thank them for something specific, then say what you suggest and why. Never say
or imply the PR was merged, closed or changed, never say "I" did anything, and don't @-mention anyone.
Put the exact change in `fix`, not in `comment`."""

ACTED = re.compile(r"\b(merged|closing this|closed this|on merge|I'?m (adding|changing|commenting|closing|merging)|"
                   r"I (added|changed|commented|closed|merged|moved|fixed))\b", re.I)

VERDICT_WORDS = {"merge": "merge", "merge-with-fix": "merge with a small fix", "rework": "a few changes first",
                 "close": "close (kindly)", "hold": "a maintainer decision"}


# ---------- GitHub ----------

def gh_token() -> str:
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if tok:
        return tok
    return subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()


class GitHub:
    def __init__(self, repo: str, token: str | None = None, dry_run: bool = False):
        self.repo = repo
        self.dry_run = dry_run
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {token or gh_token()}",
                               "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})

    def get(self, path: str, **params):
        for attempt in range(4):
            r = self.s.get(f"{API}/repos/{self.repo}{path}", params=params, timeout=60)
            if r.status_code in (502, 503, 504) or (r.status_code == 403 and "rate limit" in r.text.lower()):
                time.sleep(10 * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json()
        r.raise_for_status()

    def paged(self, path: str, limit: int = 300, **params):
        out, page = [], 1
        while len(out) < limit:
            batch = self.get(path, per_page=100, page=page, **params)
            if not batch:
                break
            out.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return out[:limit]

    def write(self, method: str, path: str, body: dict | None = None):
        if self.dry_run:
            return {}
        r = self.s.request(method, f"{API}/repos/{self.repo}{path}", json=body, timeout=60)
        if r.status_code not in (200, 201, 204):
            raise RuntimeError(f"{method} {path}: HTTP {r.status_code} {r.text[:200]}")
        return r.json() if r.text else {}

    def file_text(self, path: str, ref: str) -> str | None:
        try:
            r = self.s.get(f"{API}/repos/{self.repo}/contents/{path}", params={"ref": ref},
                           headers={"Accept": "application/vnd.github.raw"}, timeout=60)
        except requests.RequestException:
            return None
        return r.text if r.status_code == 200 else None


# ---------- reading the PR ----------

def snapshot(gh: GitHub, n: int) -> dict:
    pr = gh.get(f"/pulls/{n}")
    files = []
    for f in gh.paged(f"/pulls/{n}/files", limit=300):
        files.append({"path": f["filename"], "status": f.get("status", "modified"),
                      "additions": int(f.get("additions") or 0), "deletions": int(f.get("deletions") or 0),
                      "patch": f.get("patch") or "", "binary": "patch" not in f and int(f.get("changes") or 0) > 0})
    return {"pr": n, "title": pr["title"], "author": pr["user"]["login"], "body": (pr.get("body") or "")[:4000],
            "created_at": pr["created_at"], "head_sha": pr["head"]["sha"], "base_ref": pr["base"]["ref"],
            "head_ref": pr["head"]["ref"],
            "own_branch": (pr["head"].get("repo") or {}).get("full_name") == pr["base"]["repo"]["full_name"],
            "default_branch": pr["base"]["repo"]["default_branch"], "draft": pr.get("draft", False),
            "state": pr["state"], "labels": [l["name"] for l in pr.get("labels") or []], "files": files}


def main_tree(gh: GitHub, branch: str) -> list[str]:
    t = gh.get(f"/git/trees/{branch}", recursive="1")
    return [e["path"] for e in t.get("tree", [])]


def repo_context(gh: GitHub, branch: str) -> dict:
    paths = main_tree(gh, branch)
    folders = {p.split("/")[1] for p in paths if p.startswith("examples/") and p.count("/") >= 2}
    locales = sum(1 for p in paths if re.match(r"^launcher/app/src/main/res/values-[^/]+/strings\.xml$", p))
    return {"list_folders": folders, "locale_count": locales}


def other_open_list_folders(gh: GitHub, snap: dict, my_folders: list[str], max_fetch: int = 12) -> dict:
    """{folder: [pr]} for other open PRs adding the same examples/ folders (title-similar ones only, to stay cheap)."""
    if not my_folders:
        return {}
    mine = set(retrieval.tokens(snap["title"] + " " + " ".join(f.replace("-", " ") for f in my_folders)))
    cands = []
    for p in gh.paged("/pulls", limit=300, state="open"):
        if p["number"] == snap["pr"]:
            continue
        t = set(retrieval.tokens(p["title"]))
        if mine and len(mine & t) >= 2:
            cands.append(p["number"])
    out: dict[str, list[int]] = {}
    for n in cands[:max_fetch]:
        for f in gh.paged(f"/pulls/{n}/files", limit=100):
            m = re.match(r"^examples/([^/]+)/", f["filename"])
            if m and m.group(1) in my_folders:
                out.setdefault(m.group(1), [])
                if n not in out[m.group(1)]:
                    out[m.group(1)].append(n)
    return out


# ---------- the sticky comment ----------

def find_sticky(gh: GitHub, n: int) -> tuple[int | None, str]:
    for c in gh.paged(f"/issues/{n}/comments", limit=300):
        if MARKER in (c.get("body") or ""):
            m = re.search(r"sha=([0-9a-f]{7,40})", c["body"])
            return c["id"], (m.group(1) if m else "")
    return None, ""


def _clean(text: str, limit: int = 500) -> str:
    """Model text going into a public comment: no pings, no HTML, no runaway length."""
    t = re.sub(r"<[^>]{0,200}>", "", text or "")
    t = re.sub(r"@(?=[A-Za-z0-9-])", "@​", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t if len(t) <= limit else t[: limit - 1].rsplit(" ", 1)[0] + "…"


def _opening(reason: str) -> str:
    t = _clean(reason)
    return t if t.lower().startswith(("thank", "thanks")) else ("Thanks for the PR! " + t).strip()


def checks(fx: dict, ptype: str) -> list[str]:
    ok, note = "OK", "Note"
    out = []
    if fx.get("list_folders"):
        if fx.get("duplicate_of_merged_folder"):
            out.append(f"**{note}**: the folder already exists on main: `{'`, `'.join(fx['duplicate_of_merged_folder'])}`")
        else:
            out.append(f"**{ok}**: new TV folder, not on main yet: `{'`, `'.join(fx['list_folders'][:3])}`")
        if fx.get("competing_open_prs"):
            refs = ", ".join(f"#{p}" for ps in fx["competing_open_prs"].values() for p in ps)
            out.append(f"**{note}**: another open PR adds the same folder: {refs}")
        out.append(f"**{note}**: disables protected packages: `{'`, `'.join(fx['protected_packages_disabled'])}`"
                   if fx.get("protected_packages_disabled") else f"**{ok}**: no protected packages disabled")
        out.append(f"**{note}**: disables remote-pairing or input packages: "
                   f"`{'`, `'.join(fx['pairing_or_input_packages_disabled'])}`"
                   if fx.get("pairing_or_input_packages_disabled") else f"**{ok}**: remote pairing and input left alone")
        out.append(f"**{note}**: uses `pm hide`/`pm block` without the matching undo in the header"
                   if fx.get("hide_without_undo") else f"**{ok}**: everything it changes can be undone")
    if fx.get("binary_files"):
        out.append(f"**{note}**: adds prebuilt binaries: `{'`, `'.join(fx['binary_files'][:3])}`")
    if fx.get("adds_internet_permission"):
        out.append(f"**{note}**: adds the INTERNET permission to the launcher")
    elif ptype == "launcher":
        out.append(f"**{ok}**: no INTERNET permission added")
    gap = facts_mod.strings_gap(fx)
    if gap:
        out.append(f"**{note}**: {gap}")
    if fx.get("sensitive_paths"):
        out.append(f"**{note}**: touches maintainer-only paths: `{'`, `'.join(fx['sensitive_paths'][:4])}`")
    out.append(f"Size: {fx['size']} (+{fx['additions']} -{fx['deletions']}, {fx['files']} files)")
    return out


def render(snap: dict, *, verdict: str, model_verdict: str, priority: str, reason: str, fix: str, why_held: str,
           fx: dict, ptype: str, cost: float) -> str:
    head = snap["head_sha"][:12]
    lines = [f"{MARKER} sha={head} v=1 -->"]
    if verdict == "hold":
        lines.append(f"**maintainer-bot review** · this one needs **a maintainer decision**")
        lines.append("")
        lines.append(_opening(reason))
        lines.append("")
        lines.append(f"Why it goes to a maintainer: {_clean(why_held, 240)}.")
        if model_verdict and model_verdict != "hold":
            lines.append(f"The bot's own suggestion would be: {VERDICT_WORDS.get(model_verdict, model_verdict)}.")
    else:
        lines.append(f"**maintainer-bot review** · suggests **{VERDICT_WORDS[verdict]}** ({priority})")
        lines.append("")
        lines.append(_opening(reason))
        if verdict == "merge-with-fix" and fix:
            lines += ["", f"**The small fix:** {_clean(fix, 400)}"]
        elif verdict == "rework" and fix:
            lines += ["", f"**What would help:** {_clean(fix, 400)}"]
    lines += ["", "<details><summary>Checks</summary>", ""]
    lines += [f"- {c}" for c in checks(fx, ptype)]
    lines += ["", "</details>", "",
              "This is a suggestion; a maintainer makes the final call. A maintainer can comment `/bot review` "
              "to run it again.", "", FOOTER]
    return "\n".join(lines)


def render_skip(snap: dict, paths: list[str]) -> str:
    return "\n".join([
        f"{MARKER} sha={snap['head_sha'][:12]} v=1 -->",
        "**maintainer-bot review** · this one needs **a maintainer**",
        "",
        "Thanks for the PR! It changes CI or review configuration "
        f"(`{'`, `'.join(paths[:4])}`), so the bot doesn't review it; a maintainer will take a look.",
        "", FOOTER])


def labels_for(ptype: str, verdict: str, priority: str, fx: dict, snap: dict) -> list[str]:
    out = set()
    if ptype in TYPE_LABELS:
        out.add(TYPE_LABELS[ptype])
    text = (snap["title"] + " " + " ".join(f["path"] for f in snap["files"])).lower()
    if re.search(r"google.?tv|setupwraith|launcherx", text):
        out.add("google-tv")
    out.add(VERDICT_LABELS.get(verdict, "needs-maintainer"))
    if priority in PRIORITY_LABELS:
        out.add(priority)
    return sorted(out & ALLOWED)


def sync_labels(gh: GitHub, n: int, current: list[str], wanted: list[str]) -> tuple[list[str], list[str]]:
    add = [l for l in wanted if l not in current]
    remove = [l for l in current if l in BOT_OWNED and l not in wanted]
    for l in remove:
        gh.write("DELETE", f"/issues/{n}/labels/{requests.utils.quote(l, safe='')}")
    if add:
        gh.write("POST", f"/issues/{n}/labels", {"labels": add})
    return add, remove


# ---------- the decision ----------

def load_precedents(text: str) -> tuple[list[dict], dict, dict]:
    rows, files, bodies = [], {}, {}
    for line in (text or "").splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        rows.append({"pr": e["pr"], "title": e["title"], "truth": e["truth"], "decided_at": e["decided_at"],
                     "maintainer_note": e.get("maintainer_note", ""), "fix": e.get("fix", "")})
        files[e["pr"]] = e.get("files") or []
        bodies[e["pr"]] = ""
    return rows, files, bodies


def review(repo: str, n: int, *, rules_md: str | None = None, precedents: str | None = None, dry_run: bool = False,
           force: bool = False, ledger_path: str = ".maintainer-bot/ledger.jsonl", daily_cap: float = 5.0,
           per_pr_cap: float = 0.5, model: str = "claude-opus-5.5", critic: str = "claude-opus-5.5",
           second: str = "glm-5.3-flash", threshold: float = 0.65, rules_path: str = ".github/maintainer/MAINTAINER.md",
           precedents_path: str = ".github/maintainer/precedents.jsonl", log=print) -> dict:
    gh = GitHub(repo, dry_run=dry_run)
    snap = snapshot(gh, n)
    result = {"pr": n, "title": snap["title"], "head": snap["head_sha"][:12]}
    if snap["state"] != "open" or snap["draft"]:
        return {**result, "skipped": "closed or draft"}
    if snap.get("own_branch") and snap.get("head_ref", "").startswith("bot/"):
        return {**result, "skipped": "the bot's own merge or counts PR"}
    sticky_id, sticky_sha = find_sticky(gh, n)
    if not force and sticky_sha and snap["head_sha"].startswith(sticky_sha):
        return {**result, "skipped": "already reviewed at this commit"}

    paths = [f["path"] for f in snap["files"]]
    skip = sorted({p for p in paths for s in SKIP_PATHS if p.startswith(s)})
    if skip:
        body = render_skip(snap, skip)
        labels = ["needs-maintainer"]
        _post(gh, n, sticky_id, body)
        add, rem = sync_labels(gh, n, snap["labels"], labels)
        return {**result, "verdict": "hold", "skipped_review": "config paths", "labels": labels, "comment": body,
                "labels_added": add, "labels_removed": rem}

    branch = snap["default_branch"]
    rules_md = rules_md if rules_md is not None else (gh.file_text(rules_path, branch) or "")
    precedents = precedents if precedents is not None else (gh.file_text(precedents_path, branch) or "")
    ctxinfo = repo_context(gh, branch)
    my_folders = sorted({m.group(1) for p in paths if (m := re.match(r"^examples/([^/]+)/", p))})
    fx = facts_mod.compute(snap, existing_list_folders=ctxinfo["list_folders"],
                           other_open_list_folders=other_open_list_folders(gh, snap, my_folders),
                           locale_count=ctxinfo["locale_count"])
    ptype = checklists.pr_type(paths, snap["title"])

    hist, files_by_pr, bodies = load_precedents(precedents)
    now = datetime.now(timezone.utc).isoformat()
    row = {"pr": n, "title": snap["title"], "decided_at": now, "truth": None, "family": "?", "split": "live",
           "type": ptype, "batch_dependent": False, "facts": fx, "top_dirs": fx["top_dirs"], "batch": {}}
    if fx.get("competing_open_prs"):
        row["batch"]["other_open_prs_adding_the_same_folder"] = fx["competing_open_prs"]
    files_by_pr[n] = paths
    bodies[n] = snap["body"]
    ctx = {"snaps": {n: snap}, "index": retrieval.Index(hist + [row], files_by_pr, bodies)}

    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = ledger_path.replace(".jsonl", f"-{day}.jsonl")
    day_ledger = Ledger(path, daily_cap)
    if day_ledger.spent >= daily_cap:
        return {**result, "skipped": f"daily cap reached (${day_ledger.spent:.2f} of ${daily_cap:.2f})"}
    start = day_ledger.spent
    L = Ledger(path, min(daily_cap, start + per_pr_cap))
    try:
        res = v3.judge(row, ctx, rules_md=rules_md, model=model, critic_model=critic, second_model=second, ledger=L,
                       system_extra=LIVE_SYSTEM)
    except BudgetExceeded as e:
        return {**result, "skipped": str(e)}
    verdict, why = v3.final(res, fx, threshold=threshold, use_critic=True, use_second=True)
    priority = res.get("priority") or "p2"
    reason = res.get("comment") or ""
    if not reason or ACTED.search(reason):  # the note must never claim something already happened
        reason = "; ".join(res.get("reasons") or []) or reason
    cost = L.spent - start
    fix = res.get("fix", "")
    if verdict == "rework" and res["verdict"] in v3.ACCEPT and why:
        fix = why  # a deterministic rule turned a merge into a rework: that rule is the ask
    body = render(snap, verdict=verdict, model_verdict=res["verdict"], priority=priority, reason=reason,
                  fix=fix, why_held=why, fx=fx, ptype=ptype, cost=cost)
    labels = labels_for(ptype, verdict, priority if verdict != "hold" else "", fx, snap)
    _post(gh, n, sticky_id, body)
    add, rem = sync_labels(gh, n, snap["labels"], labels)
    return {**result, "type": ptype, "verdict": verdict, "model_verdict": res["verdict"], "why_held": why,
            "reasons": res.get("reasons") or [], "fix": fix,
            "confidence": res.get("confidence"), "priority": priority, "labels": labels, "labels_added": add,
            "labels_removed": rem, "cost_usd": round(cost, 4), "comment": body}


def _post(gh: GitHub, n: int, sticky_id: int | None, body: str) -> None:
    if sticky_id:
        gh.write("PATCH", f"/issues/comments/{sticky_id}", {"body": body})
    else:
        gh.write("POST", f"/issues/{n}/comments", {"body": body})


def backfill(repo: str, **kw) -> list[dict]:
    """Every open, non-draft PR, oldest first, one at a time; stops when the daily cap is reached."""
    gh = GitHub(repo, dry_run=kw.get("dry_run", False))
    prs = sorted(p["number"] for p in gh.paged("/pulls", limit=500, state="open") if not p.get("draft"))
    out = []
    for n in prs:
        try:
            r = review(repo, n, **kw)
        except Exception as e:  # noqa: BLE001 - one bad PR must not stop the rest
            r = {"pr": n, "error": str(e)[:200]}
        out.append(r)
        kw.get("log", print)(json.dumps({k: v for k, v in r.items() if k != "comment"}))
        if str(r.get("skipped", "")).startswith("daily cap"):
            break
    return out
