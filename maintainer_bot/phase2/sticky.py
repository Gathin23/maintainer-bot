"""Read the phase-1 review back out of the sticky PR comment and the bot's labels (no model calls)."""
from __future__ import annotations

import re

from ..live import MARKER

LABEL_VERDICT = {"bot-suggests:merge": "merge", "bot-suggests:merge-with-fix": "merge-with-fix",
                 "bot-suggests:rework": "rework", "bot-suggests:close": "close", "needs-maintainer": "hold"}
PRIORITIES = ("p0", "p1", "p2", "p3")


def _between(body: str, start: str) -> str:
    """Text after a bold lead-in on its own paragraph, up to the next blank line."""
    m = re.search(re.escape(start) + r"\s*(.+?)(?:\n\s*\n|$)", body, re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def parse(body: str, labels: list[str]) -> dict | None:
    """{sha, verdict, priority, reason, fix, ask, question} or None when the PR has no bot review yet."""
    if not body or MARKER not in body:
        return None
    sha = (re.search(r"sha=([0-9a-f]{7,40})", body) or [None, ""])[1]
    verdict = next((LABEL_VERDICT[l] for l in labels if l in LABEL_VERDICT), None)
    if verdict is None:  # labels removed by hand: fall back to the comment's own words
        if "needs **a maintainer" in body:
            verdict = "hold"
        else:
            m = re.search(r"suggests \*\*(.+?)\*\*", body)
            words = (m.group(1) if m else "").lower()
            verdict = {"merge": "merge", "merge with a small fix": "merge-with-fix",
                       "a few changes first": "rework", "close (kindly)": "close", "close": "close"}.get(words, "hold")
    priority = next((l for l in labels if l in PRIORITIES), "")
    # the opening paragraph (the line after the heading) is the reason in the maintainer's voice
    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    reason = ""
    for p in paras[1:]:
        if not p.startswith(("**", "<details", "This is a suggestion", "<sub>", "Why it goes", "The bot's own")):
            reason = re.sub(r"\s+", " ", p)
            break
    fix = _between(body, "**The small fix:**")
    ask = _between(body, "**What would help:**")
    question = _between(body, "Why it goes to a maintainer:")
    return {"sha": sha, "verdict": verdict, "priority": priority, "reason": reason, "fix": fix, "ask": ask,
            "question": question.rstrip(".")}
