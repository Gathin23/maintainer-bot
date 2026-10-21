"""Turn approved verdicts into concrete GitHub actions. Dry-run prints them; live mode is for the Action only.

Order matters and mirrors the manual rounds: merges go through one queue (rebase, re-test, push one at a time);
comments and labels follow; closes last. In live mode every merge waits for CI on the exact tested commit.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Action:
    kind: str          # merge | merge-with-fix | comment | label | close
    pr: int
    detail: str = ""


def plan(selected: dict[int, str], decisions: dict[int, dict], *, rework_label="needs-rework",
         hold_label="on-hold") -> list[Action]:
    actions: list[Action] = []
    for pr, verdict in sorted(selected.items()):
        d = decisions.get(pr, {})
        comment = d.get("comment") or ""
        if verdict == "merge":
            actions.append(Action("merge", pr, "--no-ff merge through the queue, after CI on the merged tree"))
            actions.append(Action("comment", pr, comment or "Merged, thank you!"))
        elif verdict == "merge-with-fix":
            actions.append(Action("merge-with-fix", pr, f"fix (job A, read/edit only) → test (job B, no secrets) → "
                                                        f"merge (job C): {d.get('fix', '')}"))
            actions.append(Action("comment", pr, comment or f"Merged, thank you! On merge: {d.get('fix', '')}"))
        elif verdict == "rework":
            actions.append(Action("label", pr, f"+{rework_label}"))
            actions.append(Action("comment", pr, comment or d.get("fix", "")))
        elif verdict == "close":
            actions.append(Action("comment", pr, comment))
            actions.append(Action("close", pr, ""))
        elif verdict == "hold":
            actions.append(Action("label", pr, f"+{hold_label}"))
    order = {"merge": 0, "merge-with-fix": 1, "label": 2, "comment": 3, "close": 4}
    return sorted(actions, key=lambda a: (order[a.kind], a.pr))


def dry_run(actions: list[Action]) -> str:
    return "\n".join(f"[dry-run] {a.kind:<15} #{a.pr}  {a.detail[:160]}" for a in actions)
