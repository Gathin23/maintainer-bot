"""Write the backtest report (markdown) from one or more runs."""
from __future__ import annotations

import json
import os

from . import backtest

LABELS = ["merge", "merge-with-fix", "rework", "close", "hold"]


def load_results(path: str) -> list[dict]:
    out = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    e = json.loads(line)
                    if "verdict" in e or e["pr"] not in out:
                        out[e["pr"]] = e
    return list(out.values())


def pct(x) -> str:
    return "–" if x is None else f"{100 * x:.0f}%"


def confusion_md(m: dict) -> str:
    head = "| truth ↓ / bot → | " + " | ".join(LABELS) + " | n |\n|---|" + "---|" * (len(LABELS) + 1)
    rows = []
    for t in LABELS:
        c = m["confusion"].get(t, {})
        rows.append(f"| **{t}** | " + " | ".join(str(c.get(b, 0)) for b in LABELS) + f" | {sum(c.values())} |")
    return head + "\n" + "\n".join(rows)


def section(name: str, results: list[dict], spend: float) -> str:
    m = backtest.metrics(results)
    ok = m["n"]
    lines = [f"### {name}", "",
             f"- PRs judged: **{ok}** ({m['errors']} failed calls not counted)",
             f"- Exact agreement with the maintainer: **{pct(m['exact_agreement'])}**",
             f"- Agreement treating merge and merge-with-fix as one: **{pct(m['merge_family_agreement'])}**",
             f"- The bot decided on its own in {pct(m['bot_decides_share'])} of PRs; when it did, it agreed "
             f"**{pct(m['agreement_when_bot_decides'])}** (merge family). The rest went to the maintainer as 'hold'.",
             f"- Model alone, before the deterministic overrides: {pct(m['model_only_agreement'])} (merge family)",
             f"- Safety misses (bot says merge, maintainer closed/reworked/held): **{len(m['safety_misses'])}**",
             f"- Spend: ${spend:.2f} total, ${spend / ok if ok else 0:.3f} per PR", "",
             confusion_md(m), "",
             "| class | n | recall | precision |", "|---|---|---|---|"]
    for c in LABELS:
        pc = m["per_class"][c]
        lines.append(f"| {c} | {pc['n']} | {pct(pc['recall'])} | {pct(pc['precision'])} |")
    lines.append("")
    if m["safety_misses"]:
        lines.append("Safety misses:")
        for r in sorted(m["safety_misses"], key=lambda r: r["pr"]):
            lines.append(f"- #{r['pr']} ({r['truth']} → bot {r['verdict']}, conf {r.get('confidence')}): "
                         f"{r.get('title', '')[:80]} — bot's reason: {(r.get('reasons') or [''])[0][:160]}")
        lines.append("")
    return "\n".join(lines)
