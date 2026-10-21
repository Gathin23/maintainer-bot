"""Maintainer commands in a queue-issue comment.

    /approve                     run every proposed action except "needs you"
    /approve except #512 #530    run all but those
    /approve #512 #530           run only those
    /hold #512                   don't act on these today
    /merge #512  /close #512  /rework #512   override the bot's verdict for a PR
Free text after the commands is kept as the maintainer's answer on the "needs you" items (e.g. "merge 481, hold 490").
Only the repo owner/maintainers may issue commands; the caller checks author_association.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

ALLOWED_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}


@dataclass
class Approval:
    approve_all: bool = False
    only: set = field(default_factory=set)
    excluded: set = field(default_factory=set)
    held: set = field(default_factory=set)
    overrides: dict = field(default_factory=dict)  # pr -> verdict
    notes: str = ""

    def selected(self, proposed: dict[int, str]) -> dict[int, str]:
        """Which PRs to act on, and with which verdict. proposed = {pr: verdict} from the queue."""
        out = {}
        for pr, verdict in proposed.items():
            if pr in self.held or pr in self.excluded:
                continue
            if pr in self.overrides:
                out[pr] = self.overrides[pr]
                continue
            if verdict == "hold":
                continue  # "needs you" items only move with an explicit override
            if self.only:
                if pr in self.only:
                    out[pr] = verdict
            elif self.approve_all:
                out[pr] = verdict
        for pr, verdict in self.overrides.items():
            if pr not in out and pr not in self.held:
                out[pr] = verdict
        return out


def _nums(text: str) -> set[int]:
    return {int(n) for n in re.findall(r"#?(\d+)", text)}


VERB = {"merge": "merge", "close": "close", "rework": "rework", "hold": "hold", "fix": "merge-with-fix"}


def parse(comment: str, author_association: str = "OWNER") -> Approval | None:
    """Parse a queue comment. Returns None when the author may not command the bot or there is no command."""
    if author_association not in ALLOWED_ASSOCIATIONS:
        return None
    a = Approval()
    found = False
    rest = []
    for raw in comment.splitlines():
        line = raw.strip()
        m = re.match(r"^/approve\b(.*)$", line, re.I)
        if m:
            found = True
            tail = m.group(1).strip()
            if tail.lower().startswith("except"):
                a.approve_all = True
                a.excluded |= _nums(tail)
            elif _nums(tail):
                a.only |= _nums(tail)
            else:
                a.approve_all = True
            continue
        m = re.match(r"^/(merge|close|rework|hold|fix)\b(.*)$", line, re.I)
        if m:
            found = True
            verb = VERB[m.group(1).lower()]
            for n in _nums(m.group(2)):
                if verb == "hold":
                    a.held.add(n)
                else:
                    a.overrides[n] = verb
            continue
        # plain-language answers: "merge 481, hold 490"
        for verb, nums in re.findall(r"\b(merge|close|rework|hold)\s+((?:#?\d+[\s,and]*)+)", line, re.I):
            found = True
            v = VERB[verb.lower()]
            for n in _nums(nums):
                if v == "hold":
                    a.held.add(n)
                else:
                    a.overrides[n] = v
        if line:
            rest.append(line)
    a.notes = "\n".join(rest)
    return a if found else None
