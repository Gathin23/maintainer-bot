"""The daily queue issue: built from the phase-1 sticky comments and labels, no model calls.

The body has one checkbox per PR, grouped by the suggested action, and a hidden JSON line with the reviewed
commit and verdict of each item. /approve acts on exactly that snapshot: if a PR was re-reviewed or got new
commits after the queue was built, the executor skips it.
"""
from __future__ import annotations

import json
import re

from ..live import MARKER, _clean
from . import commands, gate, sticky

LABEL = "maintainer-queue"
DATA_MARK = "<!-- mb-queue "
TITLE = "Today's queue {date}"
MAX_BODY = 60000
SECTIONS = [("merge", "Merge"), ("merge-with-fix", "Merge with a small fix"), ("rework", "A few changes first"),
            ("theme", "Move to themes/"), ("addon", "Close, and invite it as an add-on"),
            ("showcase", "Close, and offer a SHOWCASE row for the fork"), ("close", "Close (kindly)"),
            ("outside", "For a maintainer: outside the wave's paths"), ("hold", "Needs a maintainer")]
PRIO = {"p0": 0, "p1": 1, "p2": 2, "p3": 3, "": 4}
BOT_LABELS = set(sticky.LABEL_VERDICT)
HOLD_LABEL = "on-hold"          # the maintainer's own hold: never queued
REWORK_LABEL = "needs-rework"   # already asked: waiting for the author, not asked again

FOOTER = "<sub>Built by maintainer-bot from its reviews · runs on [0G Private Computer](https://pc.0g.ai)</sub>"


def collect(api) -> tuple[dict[int, dict], dict]:
    """({pr: item}, stats) for open, non-draft PRs that carry a bot review."""
    items, stats = {}, {"open": 0, "unreviewed": 0, "stale": [], "on_hold": [], "waiting": []}
    for p in api.open_prs():
        if p["draft"] or (p.get("own_branch") and p.get("head_ref", "").startswith("bot/")):
            continue
        stats["open"] += 1
        if not BOT_LABELS & set(p["labels"]):
            stats["unreviewed"] += 1
            continue
        if HOLD_LABEL in p["labels"]:
            stats["on_hold"].append(p["number"])
            continue
        s = sticky.parse(api.sticky(p["number"], MARKER), p["labels"])
        if not s:
            stats["unreviewed"] += 1
            continue
        if not s["sha"] or not p["head_sha"].startswith(s["sha"]):
            stats["stale"].append(p["number"])  # new commits since the review; phase 1 re-reviews on push
            continue
        if s["verdict"] in ("rework", "theme") and REWORK_LABEL in p["labels"]:
            stats["waiting"].append(p["number"])
            continue
        it = {"title": p["title"], "author": p["author"], **s}
        if s["verdict"] != "hold":
            # the launch gate: only lists, docs, themes, SHOWCASE, README table rows and translations go in a wave
            it["outside"] = gate.check(api.pr_files(p["number"]))
        items[p["number"]] = it
    return items, stats


def _line(n: int, it: dict, box: bool) -> str:
    title = _clean(it["title"], 90).replace("[", "(").replace("]", ")")
    who = re.sub(r"[^A-Za-z0-9-]", "", it["author"])  # no @: the queue must not ping authors
    extra = {"merge": it.get("reason"), "merge-with-fix": it.get("fix"), "rework": it.get("ask"),
             "close": it.get("reason"), "showcase": it.get("specific"), "addon": it.get("name") or it.get("specific"),
             "theme": it.get("name") or it.get("specific"), "hold": it.get("question")}[it["verdict"]]
    lead = {"merge-with-fix": "fix: ", "rework": "ask: ", "close": "why: ", "hold": "question: ",
            "addon": "addons/", "theme": "themes/"}.get(it["verdict"], "")
    tail = f" · {lead}{_clean(extra, 200)}" if extra else ""
    if it.get("outside"):
        tail = f" · suggests {it['verdict']} · {_clean(it['outside'], 120)}"
    prio = f" · {it['priority']}" if it.get("priority") else ""
    return f"{'- [ ] ' if box else '- '}#{n} {title} (by {who}){prio}{tail}"


def render(date: str, items: dict[int, dict], stats: dict, notes: list[str] | None = None) -> str:
    order = sorted(items, key=lambda n: (PRIO.get(items[n].get("priority", ""), 4), n))
    while True:
        body = _render(date, {n: items[n] for n in order}, stats, notes or [])
        if len(body) <= MAX_BODY or not order:
            return body
        dropped = order.pop()  # lowest priority, newest first: it comes back tomorrow
        stats.setdefault("deferred", []).append(dropped)


def _render(date: str, items: dict[int, dict], stats: dict, notes: list[str]) -> str:
    section = {n: "outside" if it.get("outside") else it["verdict"] for n, it in items.items()}
    n_act = sum(1 for v in section.values() if v not in ("hold", "outside"))
    out = [f"**Today's queue · {date}** · {len(items)} PRs with a review at their latest commit, "
           f"{n_act} with a proposed action.", "",
           "Comment here to act (only the repo owner and the allow-list are read):",
           "`/approve` everything with a checkbox · `/approve except #a #b` · `/approve #a #b` only those · "
           "`/skip #n` · `/close #n reason` · `/rework #n ask`. Anything else is kept as a note, never an action.",
           ""]
    for key, heading in SECTIONS:
        group = [n for n in items if section[n] == key]
        if not group:
            continue
        out.append(f"### {heading} ({len(group)})")
        if key in ("hold", "outside"):
            out.append("_Not part of `/approve`; only `/close #n` or `/rework #n` moves these._")
        out += [_line(n, items[n], box=key not in ("hold", "outside")) for n in group]
        out.append("")
    extra = []
    if stats.get("stale"):
        extra.append(f"New commits since the review (re-reviewed on push, back tomorrow): "
                     + ", ".join(f"#{n}" for n in sorted(stats["stale"])))
    if stats.get("waiting"):
        extra.append("Changes already asked, waiting for the author: "
                     + ", ".join(f"#{n}" for n in sorted(stats["waiting"])))
    if stats.get("on_hold"):
        extra.append("Labelled on-hold: " + ", ".join(f"#{n}" for n in sorted(stats["on_hold"])))
    if stats.get("unreviewed"):
        extra.append(f"Not reviewed yet: {stats['unreviewed']}")
    if stats.get("deferred"):
        extra.append(f"Deferred to tomorrow (queue size): " + ", ".join(f"#{n}" for n in sorted(stats["deferred"])))
    if extra:
        out += ["<details><summary>Not in today's queue</summary>", ""] + [f"- {e}" for e in extra] + \
               ["", "</details>", ""]
    if notes:
        out += ["**Notes from the last queue**", ""] + [f"> {_clean(x, 300)}" for x in notes] + [""]
    data = {"date": date, "items": {str(n): {"sha": it["sha"], "v": it["verdict"],
                                             **({"o": 1} if it.get("outside") else {})} for n, it in items.items()}}
    out += [FOOTER, "", DATA_MARK + json.dumps(data, separators=(",", ":")) + " -->"]
    return "\n".join(out)


def read_data(body: str) -> dict | None:
    i = (body or "").find(DATA_MARK)
    if i < 0:
        return None
    j = body.find(" -->", i)
    try:
        return json.loads(body[i + len(DATA_MARK):j])
    except ValueError:
        return None


def tick(body: str, n: int, note: str = "") -> str:
    """Tick #n's checkbox and add the outcome at the end of its line."""
    def rep(m):
        line = m.group(0).replace("- [ ] ", "- [x] ", 1)
        return line + (f" · **{note}**" if note else "")
    return re.sub(rf"^- \[ \] #{n} .*$", rep, body, count=1, flags=re.M)


def notes_from(api, issue_n: int, allow_users: set[str]) -> list[str]:
    out = []
    for c in api.issue_comments(issue_n):
        if commands.allowed(c["author"], c["association"], allow_users):
            out += commands.parse(c["body"]).notes
    return out


def upsert(api, date: str, allow_users: set[str] | None = None) -> dict:
    """Open today's issue (or refresh it while nothing has been done yet) and close older queue issues."""
    title = TITLE.format(date=date)
    existing = api.queue_issues(LABEL)
    today = next((i for i in existing if i["title"] == title and read_data(i["body"])), None)
    older = [i for i in existing if i is not today and read_data(i["body"])]
    notes = []
    for i in older:
        notes += notes_from(api, i["number"], allow_users or set())
    items, stats = collect(api)
    body = render(date, items, stats, notes)
    if today:
        if "- [x] " in today["body"]:
            return {"issue": today["number"], "action": "kept (work already started today)", "items": len(items)}
        api.update_issue(today["number"], body=body)
        out = {"issue": today["number"], "action": "updated", "items": len(items)}
    else:
        r = api.create_issue(title, body, [LABEL])
        out = {"issue": r.get("number"), "action": "created", "items": len(items), "url": r.get("url", "")}
    for i in older:
        api.comment(i["number"], f"Replaced by #{out['issue']}.")
        api.update_issue(i["number"], state="closed")
    return out
