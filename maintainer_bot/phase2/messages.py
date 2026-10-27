"""What the bot says on PRs and on the queue issue, in the maintainer's voice (short, warm, specific)."""
from __future__ import annotations

import re

from .. import templates
from ..live import _clean

# a different marker from the phase-1 review ("<!-- maintainer-bot"), so the sticky lookup never finds these
ACTION_MARK = "<!-- mb-action"
FOOTER = ("<sub>maintainer-bot, with a maintainer's approval · runs on "
          "[0G Private Computer](https://pc.0g.ai/?utm_source=cleanyourtv&utm_medium=github&utm_campaign=pr-bot-message)</sub>")
OPENERS = ("Merged, thank you!", "Merged, thanks!", "Merged, thanks for adding this!")


def _subject(title: str) -> str:
    """'Add TCL 50C647 debloat list' -> 'TCL 50C647'; '' when the title isn't that shape."""
    m = re.match(r"^\s*(?:add|adds|added)\s+(?:a\s+|the\s+)?(.+?)(?:\s+(?:debloat\s+)?list)?(?:\s*\(.*\))?\s*$",
                 title or "", re.I)
    s = m.group(1).strip() if m else ""
    return s if 0 < len(s) <= 60 and not s.lower().startswith(("support", "option", "feature")) else ""


def _sentence(text: str) -> str:
    t = _clean(text, 400).strip()
    t = re.sub(r"^on merge:?\s*", "", t, flags=re.I)
    if t and t[0].islower():
        t = t[0].upper() + t[1:]
    return t if not t or t.endswith((".", "!", "?")) else t + "."


def _drop_thanks(text: str) -> str:
    """The review's reason often opens with its own thanks; the action comment already says it."""
    return re.sub(r"^(thanks|thank you)[^.!?]*[.!?]\s*", "", _clean(text, 500), flags=re.I)


def thanks(pr: int, title: str, *, is_list: bool, fix_summary: str = "", bot_pr: int | None = None) -> str:
    lines = [f"{ACTION_MARK} merged pr={pr} -->"]
    first = OPENERS[pr % len(OPENERS)]
    subject = _subject(title) if is_list else ""
    if subject:
        first += f" Great to have the {_clean(subject, 60)} on the list."
    lines.append(first)
    if fix_summary:
        lines += ["", f"On merge: {_sentence(fix_summary)}"
                  + (f" (through #{bot_pr})" if bot_pr else "")]
    elif bot_pr:
        lines += ["", f"It went in through #{bot_pr}, which lined it up with the other lists merged today."]
    if is_list:
        lines += ["", "The README counts and card update with today's batch."]
    lines += ["", FOOTER]
    return "\n".join(lines)


def rework(pr: int, ask: str) -> str:
    ask = _sentence(_drop_thanks(ask)) or "A few small changes are needed before this can go in."
    return "\n".join([f"{ACTION_MARK} rework pr={pr} -->",
                      f"Thanks for the PR! One thing before we merge: {ask}",
                      "", "Push to this branch when it's ready and the bot will take another look.", "", FOOTER])


def close(pr: int, reason: str) -> str:
    reason = _sentence(_drop_thanks(reason))
    body = f"Thanks for taking the time on this! {reason}".strip()
    return "\n".join([f"{ACTION_MARK} close pr={pr} -->", body, "",
                      "Closing it for now. If something here is off, reply and a maintainer will reopen it.",
                      "", FOOTER])


def elsewhere(pr: int, kind: str, *, specific: str, name: str, link: str) -> str:
    """showcase / addon: a kind close that says where the idea lives instead; theme: a move to themes/."""
    tail = ("Push the move to this branch when it's ready and the bot will take another look." if kind == "theme"
            else "Closing this one here, with thanks. If something here is off, reply and a maintainer will reopen it.")
    return "\n".join([f"{ACTION_MARK} {kind} pr={pr} -->", templates.render(kind, specific=specific, name=name, link=link),
                      "", tail, "", FOOTER])


def not_marked_merged(pr: int, bot_pr: int) -> str:
    return "\n".join([f"{ACTION_MARK} superseded pr={pr} -->",
                      f"Your commits went in through #{bot_pr} (the same commits plus the small fix), so this one "
                      "can close. Thank you!", "", FOOTER])


def bot_pr_body(pr: int, title: str, *, fix_summary: str, edits: list[dict], merged_main: bool,
                resolved: list[str], approver: str) -> str:
    lines = [f"{ACTION_MARK} bot-merge pr={pr} -->",
             f"Merges #{pr} ({_clean(title, 120)}) as approved by {approver} on the daily queue."]
    if merged_main:
        lines += ["", "Main moved since the PR was opened, so this branch merges main into it first."]
        if resolved:
            lines.append("Conflicts resolved: " + "; ".join(resolved) + ".")
    if fix_summary:
        lines += ["", f"**The small fix:** {_sentence(fix_summary)}", ""]
        lines += [f"- `{e['path']}`" for e in edits]
    lines += ["", "When CI is green the bot merges this with a merge commit; the original PR is then marked merged.",
              "", FOOTER]
    return "\n".join(lines)


def counts_body(summary: dict, merged: list[int]) -> str:
    s = summary
    lines = [f"{ACTION_MARK} counts -->",
             f"README counts after today's merges ({', '.join(f'#{n}' for n in merged)}): "
             f"{s['tv_models']} TV models · {s['brands']} brands · {s['languages']} languages.",
             "", "Updated: " + ", ".join(f"`{p}`" for p in s.get("changed", [])) + "."]
    if s.get("new_brands"):
        lines += ["", "New brands on the brand line (please check the spelling): "
                  + ", ".join(s["new_brands"]) + "."]
    lines += ["", FOOTER]
    return "\n".join(lines)
