"""Phase 2 entry points (python -m maintainer_bot queue-issue | on-comment | counts-pr | dry-run-approve)."""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
from datetime import datetime, timedelta, timezone

from .. import fix as fix_mod, templates
from ..ledger import Ledger
from . import commands, queue as queue_mod
from .api import Api
from .executor import Config, Executor
from .gitops import Git

IST = timezone(timedelta(hours=5, minutes=30))


def today() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d")


def allow_list(raw: str | None) -> set[str]:
    return {u.strip().lstrip("@") for u in (raw or "").replace(",", " ").split() if u.strip()}


def counts_runner(cmd: str):
    """counts(git) runs the repo's counts command in the fresh checkout; its last stdout line is JSON."""
    def run(git: Git) -> dict:
        r = subprocess.run(shlex.split(os.path.expandvars(cmd)), cwd=git.dir, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError((r.stderr or r.stdout).strip()[-300:])
        return json.loads(r.stdout.strip().splitlines()[-1])
    return run


def daily_ledger(path: str, cap: float) -> Ledger:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return Ledger(path.replace(".jsonl", f"-{day}.jsonl"), cap)


def queue_issue(repo: str, *, allow: str = "", dry_run: bool = False) -> dict:
    api = Api(repo, token=os.environ.get("MB_WRITE_TOKEN") or None, dry_run=dry_run)
    return queue_mod.upsert(api, today(), allow_list(allow))


def on_comment(repo: str, event_path: str, *, allow: str = "", workdir: str = "", counts_cmd: str = "",
               ledger_path: str = ".maintainer-bot/ledger.jsonl", cap: float = 5.0, model: str = "claude-opus-5.5",
               git_name: str = "", git_email: str = "", max_wave: int = 25, main_every: int = 5,
               counts_note: str = "") -> dict:
    with open(event_path, encoding="utf-8") as f:
        ev = json.load(f)
    issue, comment = ev.get("issue") or {}, ev.get("comment") or {}
    labels = [l["name"] for l in issue.get("labels") or []]
    if queue_mod.LABEL not in labels or issue.get("pull_request"):
        return {"ignored": "not a queue issue"}
    author, assoc = comment.get("user", {}).get("login", ""), comment.get("author_association", "")
    if comment.get("user", {}).get("type") == "Bot" or not commands.allowed(author, assoc, allow_list(allow)):
        return {"ignored": "not an allowed commenter"}  # silent on purpose: nobody else can make the bot talk
    cmds = commands.parse(comment.get("body", ""))
    if cmds.empty:
        return {"notes": cmds.notes}
    api = Api(repo, token=os.environ.get("MB_WRITE_TOKEN") or None)
    git = None
    if workdir:
        git = Git(workdir, base=os.environ.get("MB_BASE", "main"),
                  author=(git_name or "maintainer-bot", git_email or "maintainer-bot@users.noreply.github.com"))
    cfg = Config(approver=author, model=model, ledger=daily_ledger(ledger_path, cap), propose=fix_mod.propose,
                 git=git, counts=counts_runner(counts_cmd) if counts_cmd else None,
                 where_link=templates.where_link(repo), max_wave=max_wave, main_every=main_every,
                 counts_note=counts_note)
    return Executor(api, cfg).run(issue["number"], cmds)


# what a counts patch may change (the generated TV tables are in the two READMEs), and in tools/readme_stats.py
# only the STATS line
COUNTS_OUTPUTS = ("README.md", "examples/README.md", "tools/readme_stats.py", "docs/stats.png", "docs/card.jpg")


def check_counts_patch(patch: str) -> str:
    """'' when a counts patch only touches the counts outputs, else what it touches."""
    current = ""
    for line in patch.splitlines():
        m = re.match(r"^diff --git a/(\S+) b/(\S+)$", line)
        if m:
            current = m.group(2)
            if m.group(1) != current or current not in COUNTS_OUTPUTS:
                return f"the counts patch touches {m.group(1)}"
            continue
        if current == "tools/readme_stats.py" and line[:1] in ("+", "-") and not line.startswith(("+++", "---")) \
                and not line[1:].startswith("STATS = "):
            return "the counts patch changes tools/readme_stats.py beyond the STATS line"
    return ""


def counts_pr(repo: str, workdir: str, counts_dir: str, merged: list[int], *, git_name: str = "",
              git_email: str = "", api=None, cfg: dict | None = None) -> dict:
    """The README counts PR, from a patch a job without secrets made by running the repo's tools.

    This job runs no repo code: it checks the patch's paths, applies it to a fresh main, opens the PR, waits
    for CI and merges, the same way the executor's counts step does."""
    patch_path = os.path.abspath(os.path.join(counts_dir, "counts.patch"))
    with open(os.path.join(counts_dir, "counts.json"), encoding="utf-8") as f:
        summary = json.load(f)
    with open(patch_path, encoding="utf-8", errors="replace") as f:
        bad = check_counts_patch(f.read())
    if bad:
        return {"status": "refused", "detail": bad}

    def apply(git: Git) -> dict:
        if os.path.getsize(patch_path):
            git.run("apply", "--binary", patch_path)
        return summary

    git = Git(workdir, base=os.environ.get("MB_BASE", "main"),
              author=(git_name or "maintainer-bot", git_email or "maintainer-bot@users.noreply.github.com"))
    ex = Executor(api or Api(repo, token=os.environ.get("MB_WRITE_TOKEN") or None),
                  Config(git=git, counts=apply, **(cfg or {})))
    ex.merged = list(merged)
    return ex.counts_step() or {"status": "skipped"}


def dry_run_approve(repo: str, *, counts_check: str = "", counts_dir: str = "", out: str = "",
                    max_wave: int = 25) -> str:
    """Read-only: build today's queue from the live labels and say exactly what `/approve` would do.

    counts_check: a command that prints the counts JSON without writing (e.g. update_counts.py . --check),
    run in counts_dir (a checkout of main)."""
    api = Api(repo, dry_run=True)  # every write is a no-op
    items, stats = queue_mod.collect(api)
    body = queue_mod.render(today(), items, dict(stats))

    class Snapshot:  # the executor reads the queue from an issue; hand it today's body without creating one
        def __getattr__(self, name):
            return getattr(api, name)

        def issue(self, n):
            return {"number": 0, "title": "", "body": body, "state": "open", "labels": [], "author": ""}

    cfg = Config(approver="(dry run)", git=None, dry_run=True, log=lambda s: None, max_wave=max_wave)
    ex = Executor(Snapshot(), cfg)
    res = ex.run(0, commands.parse("/approve"))
    counts = None
    if counts_check and counts_dir:
        try:
            counts = counts_runner(counts_check)(Git(counts_dir))
        except Exception as e:  # noqa: BLE001
            counts = {"error": str(e)[:200]}
    report = render_report(repo, items, stats, res, counts, main_state=ex.main_state, max_wave=max_wave)
    if out:
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        open(out, "w", encoding="utf-8").write(report)
    return report


def render_report(repo: str, items: dict, stats: dict, res: dict, counts: dict | None, *, main_state: str = "",
                  max_wave: int = 0) -> str:
    by_status: dict[str, list] = {}
    for o in res["outcomes"]:
        by_status.setdefault(o["status"], []).append(o)
    verdicts: dict[str, int] = {}
    for it in items.values():
        verdicts[it["verdict"]] = verdicts.get(it["verdict"], 0) + 1
    outside = {n: it for n, it in items.items() if it.get("outside")}
    lines = [f"# Phase 2 dry run: what `/approve` would do on {repo}", "",
             f"Built {datetime.now(IST).strftime('%Y-%m-%d %H:%M IST')} from the live labels and sticky reviews. "
             "Read-only: no comment, label, merge or push was made.", "",
             f"- Open non-draft PRs: {stats['open']}; with a review at their latest commit: {len(items)}; "
             f"new commits since the review: {len(stats['stale'])}; not reviewed yet: {stats['unreviewed']}",
             "- Queue by suggestion: " + ", ".join(f"{k} {v}" for k, v in sorted(verdicts.items())),
             f"- Outside the wave's paths (left for a maintainer): {len(outside)}",
             f"- main's CI now: {main_state or 'not read'}; wave size cap: {max_wave}",
             f"- `/approve` would act on: {len(res['outcomes'])} PRs "
             f"({len(by_status.get('would', []))} would go ahead, {len(by_status.get('skipped', []))} skipped"
             + (f", stopped at {res['stopped']}" if res["stopped"] else "") + ")", ""]
    if counts:
        lines += [f"- README counts on main now: {json.dumps(counts)}", ""]
    for status, heading in (("would", "Would do"), ("skipped", "Would skip"), ("stopped", "Would stop the batch")):
        group = by_status.get(status, [])
        if not group:
            continue
        lines += [f"## {heading} ({len(group)})", ""]
        for o in group:
            t = items.get(o["pr"], {}).get("title", "")
            lines.append(f"- #{o['pr']} **{o['action']}** {t[:80]}: {o['detail']}")
        lines.append("")
    if outside:
        lines += [f"## Outside the wave's paths ({len(outside)})", ""]
        for n in sorted(outside):
            it = outside[n]
            lines.append(f"- #{n} suggests {it['verdict']}: {it['title'][:70]}: {it['outside']}")
        lines.append("")
    lines += ["## The queue issue body it would post", "", "````markdown",
              queue_mod.render(today(), items, dict(stats)), "````", ""]
    return "\n".join(lines)
