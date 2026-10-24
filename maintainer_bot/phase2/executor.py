"""Carries out an approved queue, one PR at a time (the workflow runs it in the `merge-queue` concurrency group).

Order: closes and rework asks first (no CI involved), then merges by priority, then merges with a fix, then one
README counts PR. Safety checks run again for every PR at the moment of acting, whatever the queue said.

A wave only starts when main's CI is green, acts on at most `max_wave` PRs, only on PRs inside the launch gate
(gate.py), and waits for main's CI again after every `main_every` merges and after the last one: red stops it.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from ..ledger import BudgetExceeded
from ..live import MARKER, SKIP_PATHS
from . import fixer, gate, messages, queue as queue_mod, sticky
from .commands import Commands
from .gitops import Git, GitError

NEVER_MERGE_LABELS = ("needs-maintainer", queue_mod.HOLD_LABEL)
# a v1 review sent every launcher PR to the maintainer; a v2 review passed the launcher gate, so only v1 blocks
V1_ONLY_LABELS = ("launcher",)
# tools/ holds the scripts the counts step runs; PROMPT.md is the agents' safety prompt
NEVER_MERGE_PATHS = SKIP_PATHS + (".github/maintainer/", "tools/", "PROMPT.md")
REWORK_LABEL = queue_mod.REWORK_LABEL


class StopBatch(RuntimeError):
    pass


@dataclass
class Config:
    approver: str = "the maintainer"
    model: str = "claude-opus-5.5"
    ledger: object = None
    propose: Callable | None = None           # fix.propose; tests pass a fake
    git: Git | None = None                    # None: the bot-branch path is unavailable (skips with a reason)
    counts: Callable | None = None            # counts(git) -> summary dict with "changed", or None to skip
    ci_timeout: float = 40 * 60
    poll: float = 30
    sleep: Callable[[float], None] = time.sleep
    ignore_checks: tuple[str, ...] = ("review",)
    where_link: str = ""                      # the repo's "Where does my idea go?" table, for showcase/addon/theme
    max_fix_lines: int = fixer.MAX_CHANGED_LINES
    max_wave: int = 25                        # most PRs one /approve acts on; the next /approve picks up the rest
    main_every: int = 5                       # wait for main's CI after this many merges (0: only before and after)
    base: str = "main"
    counts_note: str = ""                     # audit line when the README counts run in a separate job
    dry_run: bool = False                     # decide everything, write nothing (the read-only report)
    log: Callable[[str], None] = print
    today: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d"))


@dataclass
class Outcome:
    pr: int
    action: str
    status: str          # done | skipped | stopped | would
    detail: str = ""
    link: str = ""


def order(plan: dict[int, dict], items: dict[int, dict]) -> list[int]:
    rank = {"close": 0, "showcase": 0, "addon": 0, "rework": 1, "theme": 1, "merge": 2, "merge-with-fix": 3}
    return sorted(plan, key=lambda n: (rank[plan[n]["action"]],
                                       queue_mod.PRIO.get(items.get(n, {}).get("priority", ""), 4), n))


def wait_checks(api, sha: str, cfg: Config) -> dict:
    waited = 0.0
    while True:
        c = api.checks(sha, ignore=cfg.ignore_checks)
        if c["state"] in ("success", "failure"):
            return c
        if waited >= cfg.ci_timeout:
            return {**c, "state": "timeout"}
        cfg.sleep(cfg.poll)
        waited += cfg.poll


def _is_list(paths: list[str]) -> bool:
    return any(p.startswith("examples/") for p in paths)


class Executor:
    def __init__(self, api, cfg: Config):
        self.api, self.cfg = api, cfg
        self.merged: list[int] = []
        self.outcomes: list[Outcome] = []
        self.main_state = ""                  # main's CI before the wave, for the report

    # ---- entry point ----
    def run(self, issue_n: int, cmds: Commands) -> dict:
        issue = self.api.issue(issue_n)
        data = queue_mod.read_data(issue["body"])
        if not data:
            return {"error": "not a queue issue"}
        items = {int(k): {"sha": v["sha"], "verdict": v["v"], "outside": bool(v.get("o"))}
                 for k, v in data["items"].items()}
        plan = cmds.plan(items)
        body = issue["body"]
        stopped = self.main_red("before the wave") if plan else ""
        acted, checked = 0, 0
        for n in ([] if stopped and not self.cfg.dry_run else order(plan, items)):
            if acted >= self.cfg.max_wave:
                self.outcomes.append(Outcome(n, plan[n]["action"], "skipped",
                                             f"over the wave size cap ({self.cfg.max_wave}): the next /approve"))
                continue
            try:
                o = self.one(n, plan[n], items[n])
            except StopBatch as e:
                o = Outcome(n, plan[n]["action"], "stopped", str(e))
                stopped = stopped or f"#{n}: {e}"
            except Exception as e:  # noqa: BLE001 - one PR's API error must not leave a half-done batch silent
                o = Outcome(n, plan[n]["action"], "stopped", f"error: {str(e)[:200]}")
                stopped = stopped or f"#{n}: error"
            self.outcomes.append(o)
            self.cfg.log(f"#{n} {o.action}: {o.status} {o.detail}")
            acted += o.status in ("done", "would")
            if o.status == "done":
                body = queue_mod.tick(body, n, o.detail.split(";")[0])
                if not self.cfg.dry_run:
                    self.api.update_issue(issue_n, body=body)
            if stopped and not self.cfg.dry_run:  # a dry run lists every PR, and where a real batch would stop
                break
            if self.cfg.main_every and len(self.merged) - checked >= self.cfg.main_every:
                checked = len(self.merged)
                stopped = self.main_red(f"after {checked} merges")
                if stopped:
                    break
        if len(self.merged) > checked:  # the last merges: main must end the wave green
            why = self.main_red(f"after the wave's {len(self.merged)} merges")
            stopped = f"{stopped}; {why}" if stopped and why else stopped or why
        counts = self.counts_step() if self.merged else None
        audit = self.audit(cmds, stopped, counts)
        if not self.cfg.dry_run:
            self.api.comment(issue_n, audit)
        return {"outcomes": [o.__dict__ for o in self.outcomes], "stopped": stopped, "counts": counts,
                "audit": audit, "merged": self.merged}

    # ---- main's CI ----
    def main_red(self, when: str) -> str:
        """'' when main's CI is green (waiting while it runs), else why the wave must not go on."""
        try:
            sha = self.api.branch_sha(self.cfg.base)
            if self.cfg.dry_run:  # read once, never wait
                c = self.api.checks(sha, ignore=self.cfg.ignore_checks)
                self.main_state = c["state"]
                return f"main's CI is failing {when}: {', '.join(c['failed'][:3])}" if c["state"] == "failure" else ""
            c = wait_checks(self.api, sha, self.cfg)
        except Exception as e:  # noqa: BLE001 - unknown is not green
            self.main_state = "unknown"
            return f"main's CI could not be read {when}: {str(e)[:120]}"
        self.main_state = c["state"]
        if c["state"] == "success":
            return ""
        detail = "timed out" if c["state"] == "timeout" else "failing: " + ", ".join(c["failed"][:3])
        return f"main's CI {detail} {when} (main at {sha[:7]})"

    # ---- one PR ----
    def one(self, n: int, step: dict, item: dict) -> Outcome:
        action = step["action"]
        pr = self.api.pr(n)
        if pr["state"] != "open":
            return Outcome(n, action, "skipped", "already merged" if pr["merged"] else "already closed")
        if not pr["head_sha"].startswith(item["sha"]):
            return Outcome(n, action, "skipped", "new commits since the review; the bot re-reviews on push")
        review = sticky.parse(self.api.sticky(n, MARKER), pr["labels"])
        if not review or not pr["head_sha"].startswith(review["sha"] or "-"):
            return Outcome(n, action, "skipped", "the review changed since the queue was built")
        if step["source"] == "approve" and queue_mod.HOLD_LABEL in pr["labels"]:
            return Outcome(n, action, "skipped", "labelled on-hold")
        if step["source"] == "approve" and action in ("rework", "theme") and REWORK_LABEL in pr["labels"]:
            return Outcome(n, action, "skipped", "changes were already asked")
        if step["source"] == "approve" and review["verdict"] != item["verdict"]:
            return Outcome(n, action, "skipped", f"the suggestion is now {review['verdict']}, not {item['verdict']}")
        if step["source"] == "approve":
            why = gate.check(self.api.pr_files(n))
            if why:
                return Outcome(n, action, "skipped", f"outside the wave's paths ({why}): for a maintainer")
        text = step["text"] if step["source"] == "command" else \
            {"merge-with-fix": review["fix"], "rework": review["ask"]}.get(action, review["reason"])
        if action == "close":
            return self.close(n, text)
        if action == "rework":
            return self.rework(n, text)
        if action in ("showcase", "addon", "theme"):
            return self.elsewhere(n, action, review)
        return self.merge(n, pr, action, review)

    def elsewhere(self, n: int, kind: str, review: dict) -> Outcome:
        what = {"showcase": "close with a SHOWCASE offer", "addon": "close with an add-on invite",
                "theme": f"ask to move it to themes/ and label {REWORK_LABEL}"}[kind]
        if self.cfg.dry_run:
            return Outcome(n, kind, "would", what)
        self.api.comment(n, messages.elsewhere(n, kind, specific=review.get("specific", ""),
                                               name=review.get("name", ""), link=self.cfg.where_link))
        if kind == "theme":
            self.api.add_labels(n, [REWORK_LABEL])
            return Outcome(n, kind, "done", "asked to move it to themes/")
        self.api.close_pr(n)
        return Outcome(n, kind, "done", "closed, " + ("SHOWCASE offered" if kind == "showcase" else "add-on invited"))

    def close(self, n: int, reason: str) -> Outcome:
        if self.cfg.dry_run:
            return Outcome(n, "close", "would", f"comment and close: {reason[:120]}")
        self.api.comment(n, messages.close(n, reason))
        self.api.close_pr(n)
        return Outcome(n, "close", "done", "closed")

    def rework(self, n: int, ask: str) -> Outcome:
        if self.cfg.dry_run:
            return Outcome(n, "rework", "would", f"comment and label {REWORK_LABEL}: {ask[:120]}")
        self.api.comment(n, messages.rework(n, ask))
        self.api.add_labels(n, [REWORK_LABEL])
        return Outcome(n, "rework", "done", "asked for changes")

    def merge(self, n: int, pr: dict, action: str, review: dict) -> Outcome:
        bad = [l for l in pr["labels"] if l in NEVER_MERGE_LABELS or (l in V1_ONLY_LABELS and review.get("v", 1) < 2)]
        if bad:
            return Outcome(n, action, "skipped", f"labelled {', '.join(bad)}: maintainer only")
        paths = self.api.pr_paths(n)
        touchy = [p for p in paths if p.startswith(NEVER_MERGE_PATHS)]
        if touchy:
            return Outcome(n, action, "skipped", f"changes {touchy[0]}: maintainer only")
        if action == "merge-with-fix":
            # its own CI is often red for exactly the thing the fix repairs (a missing README row);
            # the gate is CI on the bot branch, which runs on PR head + fix before anything merges
            return self.bot_branch(n, pr, paths, fix_text=review["fix"], reason="")
        c = self.api.checks(pr["head_sha"], ignore=self.cfg.ignore_checks)
        if c["state"] == "pending":
            return Outcome(n, action, "skipped", "checks still running or waiting for approval: "
                           + ", ".join(c["pending"][:3]))
        if c["state"] == "none":
            return Outcome(n, action, "skipped", "no CI ran on this commit")
        if c["state"] == "failure":
            raise StopBatch(f"checks failing on #{n}: {', '.join(c['failed'][:3])}")
        p = self.api.wait_mergeable(n)
        if p["mergeable"]:
            if self.cfg.dry_run:
                return Outcome(n, action, "would", "merge commit through the API")
            r = self.api.merge(n, pr["head_sha"], f"Merge PR #{n}: {pr['title']}")
            self.merged.append(n)
            self.api.comment(n, messages.thanks(n, pr["title"], is_list=_is_list(paths)))
            return Outcome(n, action, "done", f"merged {str(r.get('sha', ''))[:7]}".strip())
        return self.bot_branch(n, pr, paths, fix_text="", reason="no longer merges cleanly")

    # ---- the bot-branch path: PR head (+ main) (+ fix) -> bot PR -> CI -> merge ----
    def bot_branch(self, n: int, pr: dict, paths: list[str], *, fix_text: str, reason: str) -> Outcome:
        action = "merge-with-fix" if fix_text else "merge"
        git = self.cfg.git
        if git is None:
            what = "would build bot/merge-%d" % n + (f" with the fix: {fix_text[:100]}" if fix_text else f" ({reason})")
            return Outcome(n, action, "would" if self.cfg.dry_run else "skipped",
                           what if self.cfg.dry_run else "no git checkout for the bot-branch path")
        try:
            prep = git.prepare(n, pr["head_sha"], pr["title"])
        except GitError as e:
            return Outcome(n, action, "skipped", f"needs a maintainer: {e}")
        fx = {"edits": [], "summary": ""}
        if fix_text:
            if self.cfg.propose is None:
                return Outcome(n, action, "skipped", "no fix model configured")
            try:
                fx = fixer.make(pr=n, title=pr["title"], fix_text=fix_text, paths=paths,
                                diff=self.api.pr_patches(n), read=git.read, propose=self.cfg.propose,
                                model=self.cfg.model, ledger=self.cfg.ledger, max_lines=self.cfg.max_fix_lines)
            except BudgetExceeded as e:
                return Outcome(n, action, "skipped", f"fix model: {e}")
            if fx["problems"]:
                return Outcome(n, action, "skipped", "the fix needs a maintainer: " + "; ".join(fx["problems"][:2]))
            why = gate.edits_reason(fx["edits"])
            if why:
                return Outcome(n, action, "skipped", f"the fix leaves the wave's paths ({why}): for a maintainer")
            git.apply_edits(fx["edits"], f"On merge: {fx['summary']}")
        if self.cfg.dry_run:
            return Outcome(n, action, "would", f"bot PR from {prep['branch']}"
                           + (f" with the fix: {fx['summary']}" if fx["summary"] else ""))
        sha = git.push(prep["branch"])
        title = (f"Merge #{n} with fix: " if fx["summary"] else f"Merge #{n}: ") + pr["title"]
        body = messages.bot_pr_body(n, pr["title"], fix_summary=fx["summary"], edits=fx["edits"],
                                    merged_main=prep["merged_main"], resolved=prep["resolved"],
                                    approver=self.cfg.approver)
        bp = self.api.find_pr_for_branch(prep["branch"]) or self.api.create_pr(prep["branch"], git.base, title, body)
        c = wait_checks(self.api, sha, self.cfg)
        if c["state"] != "success":
            detail = "timed out" if c["state"] == "timeout" else "failing: " + ", ".join(c["failed"][:3])
            raise StopBatch(f"CI on bot PR #{bp['number']} {detail}")
        self.api.wait_mergeable(bp["number"])
        self.api.merge(bp["number"], sha, f"Merge PR #{n}: {pr['title']}",
                       f"On merge: {fx['summary']}" if fx["summary"] else "")
        self.merged.append(n)
        orig = self.api.pr(n)
        for _ in range(6):
            if orig["merged"] or orig["state"] != "open":
                break
            self.cfg.sleep(5)
            orig = self.api.pr(n)
        if not orig["merged"]:
            self.api.comment(n, messages.not_marked_merged(n, bp["number"]))
            if orig["state"] == "open":
                self.api.close_pr(n)
        self.api.delete_branch(prep["branch"])
        self.api.comment(n, messages.thanks(n, pr["title"], is_list=_is_list(paths), fix_summary=fx["summary"],
                                            bot_pr=bp["number"]))
        return Outcome(n, action, "done", f"merged through #{bp['number']}", bp.get("url", ""))

    # ---- after the batch ----
    def counts_step(self) -> dict | None:
        git, counts = self.cfg.git, self.cfg.counts
        if git is None or counts is None:
            return None
        branch = f"bot/counts-{self.cfg.today}"
        try:
            git.fresh_base(branch)
            summary = counts(git)
        except Exception as e:  # noqa: BLE001
            return {"status": "failed", "detail": str(e)[:200]}
        if not git.dirty():
            return {"status": "unchanged", **summary}
        if self.cfg.dry_run:
            return {"status": "would", **summary}
        git.commit_all("README counts after today's merges")
        sha = git.push(branch)
        bp = self.api.find_pr_for_branch(branch) or self.api.create_pr(
            branch, git.base, "README counts after today's merges", messages.counts_body(summary, self.merged))
        c = wait_checks(self.api, sha, self.cfg)
        if c["state"] != "success":
            return {"status": f"open, CI {c['state']}", "pr": bp["number"], **summary}
        self.api.wait_mergeable(bp["number"])
        self.api.merge(bp["number"], sha, "README counts after today's merges")
        self.api.delete_branch(branch)
        return {"status": "merged", "pr": bp["number"], **summary}

    def audit(self, cmds: Commands, stopped: str, counts: dict | None) -> str:
        verbs = {"done": "", "skipped": "skipped: ", "stopped": "stopped: ", "would": "would: "}
        lines = [f"{messages.ACTION_MARK} audit -->",
                 f"**Batch {'(dry run) ' if self.cfg.dry_run else ''}for {self.cfg.approver}'s approval** · "
                 f"{len(self.merged)} merged", ""]
        for o in self.outcomes:
            lines.append(f"- #{o.pr} {o.action}: {verbs[o.status]}{o.detail}" + (f" ({o.link})" if o.link else ""))
        if stopped:
            where = f"at {stopped}" if stopped.startswith("#") else f"because {stopped}"
            lines += ["", f"**Stopped {where}.** The rest waits for the next `/approve`."]
        if counts is None and self.merged and self.cfg.counts_note:
            lines += ["", self.cfg.counts_note]
        if counts:
            c = counts
            what = f"#{c['pr']} " if c.get("pr") else ""
            lines += ["", f"README counts: {what}{c['status']}"
                      + (f" ({c['tv_models']} TV models · {c['brands']} brands · {c['languages']} languages)"
                         if "tv_models" in c else f" ({c.get('detail', '')})")]
        led = self.cfg.ledger
        if led is not None:
            lines += ["", f"Fix model spend today: ${led.spent:.2f} of ${led.cap_usd:.2f}"]
        if cmds.notes:
            lines += ["", "Notes kept for the next queue: " + " / ".join(f"“{x[:120]}”" for x in cmds.notes)]
        lines += ["", messages.FOOTER]
        return "\n".join(lines)
