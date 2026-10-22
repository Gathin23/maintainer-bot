"""Live review of one pull request: read it through the GitHub API, decide with the v4 policy on the 0G router,
and keep ONE sticky comment plus a few labels up to date. Phase 1 only suggests: it never merges, closes,
approves or pushes.

Re-review: every push (synchronize) is reviewed again. When the PR's own changes are the same as at the last
review (main moved, a rebase) or only Markdown changed on a PR whose substance is code or a list, the bot keeps
the model's earlier judgement and only re-runs the deterministic facts and the policy: no model call.

Safety model (see README): nothing here checks out or runs PR code. The PR is read as data through the API
(title, body, file list, patches). The rules and the precedent file are read from the base repo's default
branch, never from the PR, so a PR cannot rewrite its own rules.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import subprocess
import time
import zipfile
from datetime import datetime, timezone

import requests

from . import checklists, facts as facts_mod, retrieval, templates, v4
from .ledger import BudgetExceeded, Ledger
from .router import ToolCallFailed

API = os.environ.get("GITHUB_API_URL", "https://api.github.com")
MARKER = "<!-- maintainer-bot"
DATA_MARK = "<!-- mb-review "   # the model's judgement, kept for a re-review without a model call
FOOTER = "<sub>Reviewed by maintainer-bot · runs on [0G Private Computer](https://pc.0g.ai)</sub>"

# labels the bot may add or remove; it never touches any other label
TYPE_LABELS = {"tv-list": "tv-list", "launcher": "launcher", "tools": "scripts", "docs": "docs", "showcase": "docs",
               "theme": "launcher"}
VERDICT_LABELS = {"merge": "bot-suggests:merge", "merge-with-fix": "bot-suggests:merge-with-fix",
                  "rework": "bot-suggests:rework", "close": "bot-suggests:close",
                  "showcase": "bot-suggests:showcase", "addon": "bot-suggests:addon", "theme": "bot-suggests:theme",
                  "hold": "needs-maintainer"}
PRIORITY_LABELS = ("p0", "p1", "p2", "p3")
LEAN_LABELS = {"merge": "bot-leans:merge", "rework": "bot-leans:rework", "close": "bot-leans:close"}
BOT_OWNED = set(VERDICT_LABELS.values()) | set(PRIORITY_LABELS) | set(LEAN_LABELS.values())
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
                 "close": "close (kindly)", "showcase": "your own fork, with a row in SHOWCASE.md",
                 "addon": "an add-on under addons/", "theme": "a theme under themes/",
                 "hold": "a maintainer decision"}


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
            "state": pr["state"], "labels": [l["name"] for l in pr.get("labels") or []], "files": files,
            "mergeable": pr.get("mergeable"), "mergeable_state": pr.get("mergeable_state", "")}


def main_tree(gh: GitHub, branch: str) -> list[str]:
    t = gh.get(f"/git/trees/{branch}", recursive="1")
    return [e["path"] for e in t.get("tree", [])]


def repo_context(gh: GitHub, branch: str) -> dict:
    paths = main_tree(gh, branch)
    folders = {p.split("/")[1] for p in paths if p.startswith("examples/") and p.count("/") >= 2}
    locales = sorted({m.group(1) for p in paths
                      if (m := re.match(r"^launcher/app/src/main/res/values-([^/]+)/strings\.xml$", p))})
    return {"list_folders": folders, "locale_count": len(locales), "locales": locales,
            "themes": {p.split("/")[1] for p in paths if p.startswith("themes/") and p.count("/") >= 2},
            "addons": {p.split("/")[1] for p in paths if p.startswith("addons/") and p.count("/") >= 2},
            "examples_readme": gh.file_text("examples/README.md", branch) or ""}


def conflicts_with_main(gh: GitHub, snap: dict, ptype: str = "") -> bool | None:
    """From GitHub's mergeable flag (computed in the background, so it is retried once). Any conflict counts:
    the rule is a rebase ask, whatever the files (approved 22 Oct)."""
    m = snap.get("mergeable")
    if m is None and not getattr(gh, "dry_run", True):
        time.sleep(3)
        try:
            m = (gh.get(f"/pulls/{snap['pr']}") or {}).get("mergeable")
        except requests.RequestException:
            m = None
    if m is None:
        return None
    return not m


def conflict_files(gh: GitHub, snap: dict) -> list[str]:
    """The files both the PR and main changed since they parted: where the conflicts are (from two compares;
    nothing is checked out)."""
    try:
        cmp = gh.get(f"/compare/{snap['default_branch']}...{snap['head_sha']}") or {}
        base = (cmp.get("merge_base_commit") or {}).get("sha")
        if not base:
            return []
        main = gh.get(f"/compare/{base}...{snap['default_branch']}") or {}
    except requests.RequestException:
        return []
    theirs = {f["filename"] for f in main.get("files") or []}
    return sorted(f["path"] for f in snap["files"] if f["path"] in theirs)


def duplicate_context(gh: GitHub, snap: dict, max_fetch: int = 8) -> dict:
    """Earlier open PRs, PRs merged in the last 7 days and main's last 7 days that may already do what this
    PR does."""
    me = {"pr": snap["pr"], "title": snap["title"], "body": snap.get("body", ""), "created_at": snap["created_at"],
          "files": [f["path"] for f in snap["files"]], "file_patches": snap["files"]}
    refs, words = facts_mod.issue_refs(me), facts_mod.title_words(snap["title"])
    since = datetime.fromtimestamp(time.time() - 7 * 86400, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    others = []
    try:
        listed = [(p, False) for p in gh.paged("/pulls", limit=300, state="open")]
        listed += [(p, True) for p in gh.paged("/pulls", limit=100, state="closed", sort="updated", direction="desc")
                   if p.get("merged_at") and p["merged_at"] >= since]
        for p, merged in listed:
            if p["number"] == snap["pr"] or (not merged and p["created_at"] >= snap["created_at"]):
                continue
            o = {"pr": p["number"], "title": p["title"], "body": p.get("body") or "", "created_at": p["created_at"],
                 "merged": merged, "head": (p.get("head") or {}).get("sha", "")}
            ow = facts_mod.title_words(o["title"])
            jacc = len(words & ow) / len(words | ow) if words and ow else 0
            if (refs & facts_mod.issue_refs(o)) or jacc >= 0.3:
                others.append(o)
        others = others[:max_fetch]
        for o in others:
            files = gh.paged(f"/pulls/{o['pr']}/files", limit=100)
            o["files"] = [f["filename"] for f in files]
            o["added"] = facts_mod.added_lines_of([{"path": f["filename"], "patch": f.get("patch") or ""}
                                                   for f in files])
            if o["head"]:  # stacked on it: its commits are part of this PR
                st = (gh.get(f"/compare/{o['head']}...{snap['head_sha']}") or {}).get("status")
                o["contained"] = st in ("ahead", "identical")
        commits, texts = [], {}
        for path in [p for p in me["files"] if facts_mod._meaningful(p)][:5]:
            q = requests.utils.quote(path, safe="")
            for c in gh.get(f"/commits?sha={snap['default_branch']}&path={q}&since={since}&per_page=20") or []:
                commits.append({"sha": c["sha"], "message": c["commit"]["message"], "files": [path]})
            texts[path] = gh.file_text(path, snap["default_branch"])
    except requests.RequestException:
        return {}
    return facts_mod.duplicate_facts(me, [o for o in others if "files" in o], recent_commits=commits,
                                     main_texts=texts)


def ci_facts(gh: GitHub, sha: str, *, ignore: tuple[str, ...] = ("review",), apk_artifact: str = "") -> dict:
    """Finished checks that failed on the head commit and, optionally, the launcher APK size that CI saved as a
    small artifact (a text file with the byte count). Pending checks say nothing yet."""
    out: dict = {}
    try:
        runs = (gh.get(f"/commits/{sha}/check-runs", per_page=100) or {}).get("check_runs", [])
    except requests.RequestException:
        return out
    failed = sorted({r["name"] for r in runs if r.get("status") == "completed"
                     and r.get("conclusion") in ("failure", "timed_out") and r["name"] not in ignore})
    if failed:
        out["ci_failed"] = failed
    if apk_artifact:
        try:
            for run in (gh.get("/actions/runs", head_sha=sha, per_page=20) or {}).get("workflow_runs", []):
                arts = (gh.get(f"/actions/runs/{run['id']}/artifacts") or {}).get("artifacts", [])
                art = next((a for a in arts if a["name"] == apk_artifact and not a.get("expired")), None)
                if not art:
                    continue
                z = gh.s.get(art["archive_download_url"], timeout=60)
                with zipfile.ZipFile(io.BytesIO(z.content)) as zf:
                    text = zf.read(zf.namelist()[0]).decode()
                m = re.search(r"(\d{5,9})", text)
                g = re.search(r"gate\D{0,5}(\d{5,9})", text)
                if m:
                    out["apk_bytes"] = int(m.group(1))
                    if g:
                        out["apk_gate_bytes"] = int(g.group(1))
                break
        except (requests.RequestException, zipfile.BadZipFile, KeyError, IndexError, ValueError):
            pass
    return out


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

def find_sticky(gh: GitHub, n: int) -> tuple[int | None, str, dict]:
    """(comment id, reviewed sha, the stored judgement of a v2 review or {})."""
    for c in gh.paged(f"/issues/{n}/comments", limit=300):
        if MARKER in (c.get("body") or ""):
            m = re.search(r"sha=([0-9a-f]{7,40})", c["body"])
            return c["id"], (m.group(1) if m else ""), read_data(c["body"])
    return None, "", {}


def read_data(body: str) -> dict:
    i = (body or "").find(DATA_MARK)
    if i < 0:
        return {}
    j = body.find(" -->", i)
    try:
        return json.loads(body[i + len(DATA_MARK):j])
    except ValueError:
        return {}


def write_data(d: dict) -> str:
    """The stored judgement as one hidden line; "--" can't appear inside an HTML comment."""
    return DATA_MARK + json.dumps(d, separators=(",", ":"), ensure_ascii=True).replace("--", "\\u002d\\u002d") + " -->"


def diff_hash(snap: dict) -> str:
    """The PR's own changes (paths and patches), so a rebase or a merge of main is recognised as the same PR."""
    h = hashlib.sha256()
    for f in sorted(snap["files"], key=lambda f: f["path"]):
        body = "\n".join(l for l in (f.get("patch") or "").splitlines() if l.startswith(("+", "-")))
        h.update(f"{f['path']}\0{body}\0".encode())
    return h.hexdigest()[:16]


def docs_only_since(gh: GitHub, old: str, new: str) -> bool:
    """True when every file changed between the reviewed commit and the new head is Markdown (not PROMPT.md)."""
    try:
        files = (gh.get(f"/compare/{old}...{new}") or {}).get("files") or []
    except requests.RequestException:
        return False
    return bool(files) and all(f["filename"].endswith(".md") and f["filename"] != "PROMPT.md"
                               and not f["filename"].startswith(".github/") for f in files)


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
        if fx.get("edits_existing_list"):
            out.append(f"**{note}**: edits a list already on main: `{'`, `'.join(fx['edits_existing_list'][:3])}`")
        else:
            out.append(f"**{ok}**: new TV folder, not on main yet: `{'`, `'.join(fx['list_folders'][:3])}`")
        if fx.get("same_product_on_main"):
            hits = sorted({f for fs in fx["same_product_on_main"].values() for f in fs})
            out.append(f"**{note}**: the same product or firmware is named in `{'`, `'.join(hits[:3])}` on main")
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
        if fx.get("uninstall_steps"):
            out.append(f"**{note}**: `pm uninstall` steps: `{'`, `'.join(fx['uninstall_steps'][:3])}`")
        if fx.get("private_dns_setup"):
            out.append(f"**{note}**: sets up Private DNS in `{'`, `'.join(fx['private_dns_setup'][:2])}`")
        if fx.get("list_folder_scripts"):
            out.append(f"**{note}**: the folder has its own scripts: `{'`, `'.join(fx['list_folder_scripts'][:3])}`")
        if fx.get("untested_entries"):
            out.append(f"**{note}**: entries marked untested: `{'`, `'.join(fx['untested_entries'][:3])}`")
        if fx.get("firmware_updater_disabled"):
            out.append(f"**{note}**: disables an updater: `{'`, `'.join(fx['firmware_updater_disabled'][:3])}`")
    if fx.get("core_lines_changed") is not None and (fx.get("core_lines_changed") or fx.get("core_files")):
        keys = fx.get("new_config_keys") or []
        out.append(f"Launcher: {fx['core_lines_changed']} lines changed in `launcher/` (tests not counted)"
                   + (", new keys: " + ", ".join(f"`{k['name']}` = `{k['default'] or 'empty'}`" for k in keys[:4])
                      if keys else ""))
        if fx.get("changed_config_defaults"):
            out.append(f"**{note}**: changes a default for every TV: " + ", ".join(
                f"`{c['name']}` {c['old'] or 'empty'} → {c['new'] or 'empty'}" for c in fx["changed_config_defaults"][:3]))
        if fx.get("new_strings"):
            miss = fx.get("locales_missing_new_strings")
            if miss:
                out.append(f"**{note}**: new strings missing in {len(miss)} of {fx.get('locales_on_main', '?')} "
                           f"locales ({', '.join(miss[:6])}{'…' if len(miss) > 6 else ''})")
            elif miss is not None:
                out.append(f"**{ok}**: new strings in every locale")
        perms = (fx.get("new_permissions") or []) + (fx.get("network_use") or [])
        out.append(f"**{note}**: new permission or network use: `{'`, `'.join(perms[:4])}`" if perms
                   else f"**{ok}**: no new permission, no network use")
        if fx.get("manifest_changes"):
            out.append(f"**{note}**: changes the manifest ({', '.join(fx['manifest_changes'])})")
        if fx.get("home_path_touched"):
            out.append(f"**{note}**: touches the Home/launch path: "
                       + ", ".join(f"`{x.rsplit('/', 1)[-1]}`" for x in fx["home_path_touched"][:3]))
        if fx.get("apk_bytes"):
            out.append(f"APK: {fx['apk_bytes']:,} B" + (f" (gate {fx['apk_gate_bytes']:,} B)" if fx.get("apk_gate_bytes") else ""))
    if fx.get("core_packages_disabled"):
        out.append(f"**{note}**: disables Android core packages (#884): `{'`, `'.join(fx['core_packages_disabled'][:4])}`")
    if fx.get("conflicts_with_main"):
        files = fx.get("conflict_files") or []
        out.append(f"**{note}**: conflicts with main" + (": `" + "`, `".join(files[:5]) + "`" if files else ""))
    for d in (fx.get("possible_duplicates") or [])[:3]:
        out.append(f"**{note}**: {'likely duplicate of' if d.get('strong') else 'may overlap'} #{d['pr']} ({_clean(d['why'], 140)})")
    if (fx.get("already_on_main_live") or {}).get("share", 0) >= 0.9:
        out.append(f"**{note}**: what it adds is already on main")
    ev = fx.get("evidence") or {}
    if ev:
        out.append("Found in the diff: " + "; ".join(f"{k.replace('_', ' ')}: `{_clean(v, 100)}`"
                                                      for k, v in list(ev.items())[:3]))
    if fx.get("ci_failed"):
        out.append(f"**{note}**: CI fails: {', '.join(fx['ci_failed'][:3])}")
    if fx.get("theme_missing_screenshot"):
        out.append(f"**{note}**: no real-TV screenshot for `themes/{fx['theme_missing_screenshot'][0]}/`")
    if fx.get("addon_touches_launcher"):
        out.append(f"**{note}**: an add-on that also changes `launcher/`")
    if fx.get("unlinked_images") or fx.get("stray_root_files"):
        out.append(f"**{note}**: files nothing links to: `{'`, `'.join(((fx.get('stray_root_files') or []) + (fx.get('unlinked_images') or []))[:3])}`")
    if fx.get("binary_files"):
        out.append(f"**{note}**: adds prebuilt binaries: `{'`, `'.join(fx['binary_files'][:3])}`")
    if fx.get("adds_internet_permission") and not fx.get("new_permissions"):
        out.append(f"**{note}**: adds the INTERNET permission to the launcher")
    if fx.get("sensitive_paths") or fx.get("always_maintainer_paths"):
        paths = sorted(set((fx.get("sensitive_paths") or []) + (fx.get("always_maintainer_paths") or [])))
        out.append(f"**{note}**: touches maintainer-only paths: `{'`, `'.join(paths[:4])}`")
    out.append(f"Size: {fx['size']} (+{fx['additions']} -{fx['deletions']}, {fx['files']} files)")
    return out


def render(snap: dict, *, verdict: str, model_verdict: str, priority: str, reason: str, fix: str, why_held: str,
           fx: dict, ptype: str, cost: float, elsewhere: str = "", data: dict | None = None, note: str = "",
           leaning: tuple[str, float] | None = None) -> str:
    head = snap["head_sha"][:12]
    lines = [f"{MARKER} sha={head} v=2 -->"]
    if verdict == "hold":
        lean_txt = f" · Leans: {leaning[0]} ({leaning[1]:.0%})" if leaning else ""
        lines.append(f"**maintainer-bot review** · this one needs **a maintainer decision**{lean_txt}")
        lines.append("")
        lines.append(_opening(reason))
        lines.append("")
        lines.append(f"Why it goes to a maintainer: {_clean(why_held, 240)}.")
        if model_verdict and model_verdict != "hold":
            lines.append(f"The bot's own suggestion would be: {VERDICT_WORDS.get(model_verdict, model_verdict)}.")
    elif verdict in v4.ELSEWHERE:
        lines.append(f"**maintainer-bot review** · suggests **{VERDICT_WORDS[verdict]}** ({priority})")
        lines.append("")
        lines.append(elsewhere)
    else:
        lines.append(f"**maintainer-bot review** · suggests **{VERDICT_WORDS[verdict]}** ({priority})")
        lines.append("")
        lines.append(_opening(reason))
        if verdict == "merge-with-fix" and fix:
            lines += ["", f"**The small fix:** {_clean(fix, 500)}"]
        elif verdict == "rework" and fix:
            lines += ["", f"**What would help:** {_clean(fix, 400)}"]
    weak = [d for d in fx.get("possible_duplicates") or [] if not d.get("strong")]
    if weak and verdict != "hold":
        lines += ["", "Possibly related: " + "; ".join(f"#{d['pr']} ({_clean(d['why'], 120)})" for d in weak[:3])
                  + ". Worth a look before merging both."]
    if note:
        lines += ["", f"_{_clean(note, 200)}_"]
    lines += ["", "<details><summary>Checks</summary>", ""]
    lines += [f"- {c}" for c in checks(fx, ptype)]
    lines += ["", "</details>", "",
              "This is a suggestion; a maintainer makes the final call. A maintainer can comment `/bot review` "
              "to run it again.", "", FOOTER]
    if data:
        lines.append(write_data(data))
    return "\n".join(lines)


def render_skip(snap: dict, paths: list[str]) -> str:
    return "\n".join([
        f"{MARKER} sha={snap['head_sha'][:12]} v=2 -->",
        "**maintainer-bot review** · this one needs **a maintainer**",
        "",
        "Thanks for the PR! It changes CI or review configuration "
        f"(`{'`, `'.join(paths[:4])}`), so the bot doesn't review it; a maintainer will take a look.",
        "", FOOTER])


def render_unreviewed(snap: dict, fx: dict, ptype: str) -> str:
    return "\n".join([f"{MARKER} sha={snap['head_sha'][:12]} v=2 -->",
                      "**maintainer-bot review** · this one needs **a maintainer decision**", "",
                      "Thanks for the PR! Couldn't review this one automatically; it goes to the maintainer.", "",
                      "<details><summary>Checks</summary>", ""] + [f"- {c}" for c in checks(fx, ptype)] +
                     ["", "</details>", "", FOOTER])


def labels_for(ptype: str, verdict: str, priority: str, fx: dict, snap: dict,
               lean: tuple[str, float] | None = None) -> list[str]:
    out = set()
    if ptype in TYPE_LABELS:
        out.add(TYPE_LABELS[ptype])
    text = (snap["title"] + " " + " ".join(f["path"] for f in snap["files"])).lower()
    if re.search(r"google.?tv|setupwraith|launcherx", text):
        out.add("google-tv")
    out.add(VERDICT_LABELS.get(verdict, "needs-maintainer"))
    if verdict == "hold" and lean and lean[0] in LEAN_LABELS:
        out.add(LEAN_LABELS[lean[0]])
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
           per_pr_cap: float = 0.5, model: str = "claude-opus-5.5", critic: str = "claude-sonnet-5",
           second: str = "glm-5.3-flash", policy: dict | None = None,
           rules_path: str = ".github/maintainer/MAINTAINER.md",
           precedents_path: str = ".github/maintainer/precedents.jsonl", apk_artifact: str = "", refresh: bool = False,
           log=print) -> dict:
    """One review. refresh=True (after CI finished): re-run only the facts and the policy on the stored judgement,
    even at a commit that was already reviewed; it never calls a model."""
    gh = GitHub(repo, dry_run=dry_run)
    snap = snapshot(gh, n)
    result = {"pr": n, "title": snap["title"], "head": snap["head_sha"][:12]}
    if snap["state"] != "open" or snap["draft"]:
        return {**result, "skipped": "closed or draft"}
    if snap.get("own_branch") and snap.get("head_ref", "").startswith("bot/"):
        return {**result, "skipped": "the bot's own merge or counts PR"}
    sticky_id, sticky_sha, before = find_sticky(gh, n)
    same_commit = bool(sticky_sha) and snap["head_sha"].startswith(sticky_sha)
    if refresh and not before.get("m"):
        return {**result, "skipped": "no stored review to refresh"}
    if not force and not refresh and same_commit and before.get("m"):
        return {**result, "skipped": "already reviewed at this commit"}
    # a review from v1 (no stored judgement) is done again once, so the queue only holds v4 reviews

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
    ctxinfo = repo_context(gh, branch)
    ptype = checklists.pr_type(paths, snap["title"])
    my_folders = sorted({m.group(1) for p in paths if (m := re.match(r"^examples/([^/]+)/", p))})
    extra = ci_facts(gh, snap["head_sha"], apk_artifact=apk_artifact) if ptype != "docs" else {}
    fx = facts_mod.compute_v4(snap, existing_list_folders=ctxinfo["list_folders"],
                              other_open_list_folders=other_open_list_folders(gh, snap, my_folders),
                              main_locales=ctxinfo.get("locales") or [],
                              examples_readme=ctxinfo.get("examples_readme", ""),
                              theme_folders_on_main=ctxinfo.get("themes"), addon_folders_on_main=ctxinfo.get("addons"),
                              conflicts_with_main=conflicts_with_main(gh, snap, ptype),
                              ci_failed=extra.get("ci_failed"), apk_bytes=extra.get("apk_bytes"),
                              apk_gate_bytes=extra.get("apk_gate_bytes"))
    if fx.get("conflicts_with_main"):
        fx["conflict_files"] = conflict_files(gh, snap)
    fx.update(duplicate_context(gh, snap))
    dh = diff_hash(snap)

    # re-review without a model call: same changes as last time, or only Markdown on a code/list PR
    note, cost, res = "", 0.0, None
    if before.get("m") and not force:
        if refresh and same_commit:
            note = "Re-checked after CI finished on this commit."
        elif before.get("diff") == dh:
            note = "Re-checked at this commit: the PR's own changes are the same as at the last review."
        elif ptype not in ("docs", "showcase") and sticky_sha and docs_only_since(gh, sticky_sha, snap["head_sha"]):
            note = "Re-checked at this commit: only Markdown changed since the last review."
        if note:
            res = {"verdict": before["m"], "confidence": float(before.get("c") or 0),
                   "critic": {"blocker": bool(before.get("crit"))}, "second": {"verdict": before.get("sec")},
                   "comment": before.get("reason", ""), "reasons": [], "fix": before.get("fix", ""),
                   "specific": before.get("specific", ""), "priority": before.get("p", "p2")}

    if res is None:
        rules_md = rules_md if rules_md is not None else (gh.file_text(rules_path, branch) or "")
        precedents = precedents if precedents is not None else (gh.file_text(precedents_path, branch) or "")
        hist, files_by_pr, bodies = load_precedents(precedents)
        now = datetime.now(timezone.utc).isoformat()
        row = {"pr": n, "title": snap["title"], "decided_at": now, "truth": None, "type": ptype, "facts": fx,
               "batch": {}}
        if fx.get("competing_open_prs"):
            row["batch"]["other_open_prs_adding_the_same_folder"] = fx["competing_open_prs"]
        files_by_pr[n] = paths
        bodies[n] = snap["body"]
        index = retrieval.Index(hist + [row], files_by_pr, bodies)

        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path = ledger_path.replace(".jsonl", f"-{day}.jsonl")
        day_ledger = Ledger(path, daily_cap)
        if day_ledger.spent >= daily_cap:
            return {**result, "skipped": f"daily cap reached (${day_ledger.spent:.2f} of ${daily_cap:.2f})"}
        start = day_ledger.spent
        L = Ledger(path, min(daily_cap, start + per_pr_cap))
        try:
            res = v4.judge(row, snap, index, rules_md=rules_md, model=model, critic_model=critic,
                           second_model=second, ledger=L, system_extra=LIVE_SYSTEM)
        except BudgetExceeded as e:
            return {**result, "skipped": str(e)}
        except ToolCallFailed as e:
            # a refusal or no answer (#753, #830): never leave the PR silent
            body = render_unreviewed(snap, fx, ptype)
            _post(gh, n, sticky_id, body)
            add, rem = sync_labels(gh, n, snap["labels"], labels_for(ptype, "hold", "", fx, snap))
            return {**result, "type": ptype, "verdict": "hold", "unreviewed": str(e)[:160], "comment": body,
                    "labels_added": add, "labels_removed": rem, "cost_usd": round(L.spent - start, 4)}
        cost = L.spent - start

    verdict, why, policy_fix = v4.final(res, fx, policy)
    priority = res.get("priority") or "p2"
    reason = res.get("comment") or ""
    if not reason or ACTED.search(reason):  # the note must never claim something already happened
        reason = "; ".join(res.get("reasons") or []) or reason
    if verdict != res["verdict"] and verdict != "hold":
        # a rule changed the model's verdict (merge -> rework or merge-with-fix): its words ("ready to merge as it
        # is") would contradict the suggestion, so open with the thanks only
        spec = templates._specific(res.get("specific", ""))
        reason = f"Thank you for this, {spec}!" if spec else "Thanks for the PR!"
    fix = res.get("fix", "") if verdict in ("merge-with-fix", "rework") and res["verdict"] == verdict else ""
    if verdict == "rework" and why:
        # a deterministic rule made it a rework (rebase, core packages, …): that rule is the ask, with the
        # model's own ask after it when it also wanted changes
        own = res.get("fix", "") if res["verdict"] == "rework" else ""
        fix = why + (f". Also: {own}" if own and own.strip() not in why else "")
    if verdict == "merge-with-fix" and policy_fix:
        fix = "; ".join(x for x in (fix, policy_fix) if x)
    elsewhere = ""
    if verdict in v4.ELSEWHERE:
        elsewhere = templates.render(verdict, specific=res.get("specific", ""), name=res.get("fix", ""),
                                     link=templates.where_link(repo, branch))
    data = {"m": res["verdict"], "c": round(float(res.get("confidence") or 0), 2),
            "crit": int(bool((res.get("critic") or {}).get("blocker"))), "sec": (res.get("second") or {}).get("verdict"),
            "diff": dh, "p": priority, "reason": _clean(res.get("comment") or reason, 400),
            "fix": _clean(res.get("fix", ""), 300),
            "specific": _clean(res.get("specific", ""), 140), "final": verdict}
    leaning = v4.lean(res) if verdict == "hold" else None
    data["lean"] = leaning[0] if leaning else None
    body = render(snap, verdict=verdict, model_verdict=res["verdict"], priority=priority, reason=reason,
                  fix=fix, why_held=why, fx=fx, ptype=ptype, cost=cost, elsewhere=elsewhere, data=data, note=note,
                  leaning=leaning)
    labels = labels_for(ptype, verdict, priority if verdict != "hold" else "", fx, snap, lean=leaning)
    _post(gh, n, sticky_id, body)
    add, rem = sync_labels(gh, n, snap["labels"], labels)
    return {**result, "type": ptype, "verdict": verdict, "model_verdict": res["verdict"], "why_held": why,
            "reasons": res.get("reasons") or [], "fix": fix, "re_review": bool(note),
            "confidence": res.get("confidence"), "priority": priority, "labels": labels, "labels_added": add,
            "labels_removed": rem, "cost_usd": round(cost, 4), "comment": body}


def _post(gh: GitHub, n: int, sticky_id: int | None, body: str) -> None:
    if sticky_id:
        gh.write("PATCH", f"/issues/comments/{sticky_id}", {"body": body})
    else:
        gh.write("POST", f"/issues/{n}/comments", {"body": body})


def prs_for_workflow_run(gh: GitHub, event: dict) -> list[int]:
    """Open PRs whose head is the commit a finished CI run tested. A fork PR's workflow_run carries no
    pull_requests list, so it is looked up by the head repository's owner and branch."""
    run = event.get("workflow_run") or {}
    found = [p["number"] for p in run.get("pull_requests") or []]
    if not found and run.get("head_branch") and (run.get("head_repository") or {}).get("owner"):
        owner = run["head_repository"]["owner"]["login"]
        found = [p["number"] for p in gh.paged("/pulls", limit=10, state="open", head=f"{owner}:{run['head_branch']}")
                 if p["head"]["sha"] == run.get("head_sha")]
    return found


def refresh_after_ci(repo: str, event_path: str, **kw) -> list[dict]:
    event = json.load(open(event_path, encoding="utf-8"))
    gh = GitHub(repo, dry_run=kw.get("dry_run", False))
    return [review(repo, n, refresh=True, **kw) for n in prs_for_workflow_run(gh, event)]


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
