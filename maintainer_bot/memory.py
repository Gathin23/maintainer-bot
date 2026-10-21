"""Past decisions as examples for the model ("what did the maintainer do with PRs like this?").

Leakage rule: only decisions made strictly before the PR being judged, never the PR itself.
"""
from __future__ import annotations

import re

STOP = set("a an the and or of to for in on with by from is are add adds added list lists launcher examples tv".split())


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(w) > 2 and w not in STOP}


def similar(target: dict, history: list[dict], k: int = 8, min_non_merge: int = 3) -> list[dict]:
    """Pick up to k earlier decisions most like the target, keeping some non-merge examples in the mix."""
    cutoff = target["decided_at"]
    pool = [h for h in history if h["pr"] != target["pr"] and h["decided_at"] < cutoff]
    tw = _words(target["title"])
    tdirs = set(target.get("top_dirs") or [])

    def score(h: dict) -> float:
        hw = _words(h["title"])
        s = len(tw & hw) / (len(tw | hw) or 1)
        s += 0.5 * len(tdirs & set(h.get("top_dirs") or [])) / (len(tdirs | set(h.get("top_dirs") or [])) or 1)
        return s

    ranked = sorted(pool, key=score, reverse=True)
    picked = ranked[:k]
    non_merge = [h for h in picked if h["truth"] not in ("merge",)]
    if len(non_merge) < min_non_merge:
        extra = [h for h in ranked[k:k * 6] if h["truth"] not in ("merge",)][: min_non_merge - len(non_merge)]
        picked = picked[: k - len(extra)] + extra
    return picked


def render(examples: list[dict]) -> str:
    lines = []
    for h in examples:
        why = (h.get("fix") or h.get("maintainer_note") or "").strip().replace("\n", " ")
        why = re.sub(r"\s+", " ", why)[:260]
        lines.append(f"- #{h['pr']} [{h['truth']}] {h['title'][:110]}" + (f" — {why}" if why else ""))
    return "\n".join(lines)
