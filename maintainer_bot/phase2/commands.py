"""Maintainer commands on the bot's queue issue.

    /approve                   every proposed action except "needs a maintainer"
    /approve except #a #b      all but those
    /approve #a #b             only those
    /skip #n                   leave this one today
    /close #n <reason>         close with this reason (works on any PR in the queue, including "needs a maintainer")
    /rework #n <ask>           ask for changes with this text (same)

Anything else in the comment is kept as a note for the next run and is never turned into an action.
Only OWNER comments, or comments by users on the allow-list, are read; everyone else is ignored.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


def allowed(author: str, association: str, allow_users: set[str] | None = None) -> bool:
    if association == "OWNER":
        return True
    return bool(allow_users) and author.lower() in {u.lower() for u in allow_users}


@dataclass
class Commands:
    approve_all: bool = False
    only: set[int] = field(default_factory=set)
    excluded: set[int] = field(default_factory=set)
    skipped: set[int] = field(default_factory=set)
    closes: dict[int, str] = field(default_factory=dict)
    reworks: dict[int, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not (self.approve_all or self.only or self.closes or self.reworks or self.skipped)

    def plan(self, queue: dict[int, dict]) -> dict[int, dict]:
        """queue = {pr: {"verdict": ..., ...}} → {pr: {"action": verdict, "text": reason/ask, "source": ...}}.

        Explicit /close and /rework win over everything; "hold" items and items outside the wave's paths move only
        through those."""
        out: dict[int, dict] = {}
        for pr, item in queue.items():
            if pr in self.skipped:
                continue
            if pr in self.closes:
                out[pr] = {"action": "close", "text": self.closes[pr] or item.get("reason", ""), "source": "command"}
                continue
            if pr in self.reworks:
                out[pr] = {"action": "rework", "text": self.reworks[pr] or item.get("ask", ""), "source": "command"}
                continue
            v = item["verdict"]
            if v == "hold" or item.get("outside"):  # outside the wave's paths: only /close and /rework move it
                continue
            chosen = (pr in self.only) if self.only else (self.approve_all and pr not in self.excluded)
            if chosen:
                text = item.get("fix") if v == "merge-with-fix" else item.get("ask") if v == "rework" else \
                    item.get("specific", "") if v in ("showcase", "addon", "theme") else item.get("reason", "")
                out[pr] = {"action": v, "text": text or "", "source": "approve"}
        return out


def _nums(text: str) -> list[int]:
    return [int(n) for n in re.findall(r"#(\d+)", text)] or [int(n) for n in re.findall(r"\b(\d{1,6})\b", text)]


def parse(comment: str) -> Commands:
    c = Commands()
    for raw in (comment or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"^/approve\b(.*)$", line, re.I)
        if m:
            tail = m.group(1).strip()
            if tail.lower().startswith("except"):
                c.approve_all = True
                c.excluded.update(_nums(tail))
            elif re.search(r"#?\d", tail):
                c.only.update(_nums(tail))
            else:
                c.approve_all = True
            continue
        m = re.match(r"^/skip\b(.*)$", line, re.I)
        if m:
            c.skipped.update(_nums(m.group(1)))
            continue
        m = re.match(r"^/(close|rework)\s+#?(\d+)\s*(.*)$", line, re.I)
        if m:
            target = c.closes if m.group(1).lower() == "close" else c.reworks
            target[int(m.group(2))] = m.group(3).strip()
            continue
        c.notes.append(line)
    return c
