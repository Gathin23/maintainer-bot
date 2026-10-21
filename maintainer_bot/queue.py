"""Render the daily queue issue, grouped the way the maintainer reviews rounds."""
from __future__ import annotations

from datetime import date

GROUPS = [
    ("merge", "✅ Merge"),
    ("merge-with-fix", "🔧 Merge with a small fix"),
    ("rework", "↩️ Ask for rework"),
    ("close", "❌ Close (kindly)"),
    ("hold", "🤔 Needs you"),
]

FOOTER = ("<sub>Proposed by maintainer-bot, running on 0G Private Computer ({model}). Nothing happens until a "
          "maintainer replies <code>/approve</code>. Commands: <code>/approve</code>, <code>/approve except #N</code>, "
          "<code>/merge #N</code>, <code>/close #N</code>, <code>/rework #N</code>, <code>/hold #N</code>.</sub>")


def render(decisions: list[dict], *, model: str, day: str | None = None, tee: bool = False) -> str:
    day = day or date.today().isoformat()
    lines = [f"## Today's queue · {day}", ""]
    counts = {k: sum(1 for d in decisions if d["verdict"] == k) for k, _ in GROUPS}
    lines.append(" · ".join(f"{label.split(' ', 1)[0]} {counts[k]}" for k, label in GROUPS) + "")
    lines.append("")
    for key, label in GROUPS:
        items = [d for d in decisions if d["verdict"] == key]
        if not items:
            continue
        lines.append(f"### {label} ({len(items)})")
        for d in sorted(items, key=lambda d: (d.get("priority", "p2"), d["pr"])):
            reason = (d.get("reasons") or [""])[0]
            extra = ""
            if key == "merge-with-fix" and d.get("fix"):
                extra = f"<br>fix: {d['fix']}"
            elif key == "rework" and d.get("fix"):
                extra = f"<br>ask: {d['fix']}"
            elif key == "hold":
                extra = f"<br>question: {d.get('question') or reason}"
            lines.append(f"- [ ] #{d['pr']} **{d.get('title', '')[:90]}** · {d.get('priority', 'p2')} · "
                         f"{d.get('type', '')}<br>{reason}{extra}")
        lines.append("")
    model_txt = f"{model}, sealed in a TEE" if tee else model
    lines.append(FOOTER.format(model=model_txt))
    return "\n".join(lines)
