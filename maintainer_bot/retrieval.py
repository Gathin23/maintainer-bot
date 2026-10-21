"""Similar past PRs, with the maintainer's own reasons, as precedent for the decision (local TF-IDF, no AI).

Leakage rule: only decisions made strictly before the PR being judged, and never the PR itself.
"""
from __future__ import annotations

import math
import re
from collections import Counter

STOP = set("""a an the and or of to for in on with by from is are be this that it its as at add adds added
update updates new list lists launcher examples tv pr fix fixes support""".split())


def tokens(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9][a-z0-9_.-]{1,}", (text or "").lower()) if w not in STOP and len(w) > 2]


def doc_text(row: dict, files: list[str]) -> str:
    folders = " ".join(sorted({p.split("/")[1] for p in files if p.startswith("examples/") and p.count("/") >= 2}))
    dirs = " ".join(sorted({p.split("/")[0] for p in files}))
    paths = " ".join(p.replace("/", " ") for p in files[:40])
    # title and folders count more than the long tail of paths
    return " ".join([row.get("title", "")] * 3 + [folders] * 2 + [dirs, paths, (row.get("body") or "")[:1500]])


class Index:
    def __init__(self, rows: list[dict], files_by_pr: dict[int, list[str]], bodies: dict[int, str]):
        self.rows = rows
        self.vecs = {}
        df = Counter()
        toks = {}
        for r in rows:
            t = tokens(doc_text({**r, "body": bodies.get(r["pr"], "")}, files_by_pr.get(r["pr"], [])))
            toks[r["pr"]] = Counter(t)
            df.update(set(t))
        n = len(rows)
        self.idf = {w: math.log((n + 1) / (c + 1)) + 1 for w, c in df.items()}
        for pr, tf in toks.items():
            v = {w: (1 + math.log(c)) * self.idf[w] for w, c in tf.items()}
            norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
            self.vecs[pr] = {w: x / norm for w, x in v.items()}

    def similar(self, target: dict, k: int = 6, min_non_accept: int = 2) -> list[dict]:
        tv = self.vecs.get(target["pr"], {})
        pool = [r for r in self.rows if r["pr"] != target["pr"] and r["decided_at"] < target["decided_at"]]

        def cos(r):
            v = self.vecs.get(r["pr"], {})
            return sum(x * v.get(w, 0.0) for w, x in tv.items())

        ranked = sorted(pool, key=cos, reverse=True)
        picked = ranked[:k]
        if sum(1 for r in picked if r["truth"] not in ("merge", "merge-with-fix")) < min_non_accept:
            extra = [r for r in ranked[k:k * 5] if r["truth"] not in ("merge", "merge-with-fix")]
            need = min_non_accept - sum(1 for r in picked if r["truth"] not in ("merge", "merge-with-fix"))
            if extra[:need]:
                picked = picked[: k - len(extra[:need])] + extra[:need]
        return picked


def render(examples: list[dict]) -> str:
    lines = []
    for h in examples:
        why = (h.get("maintainer_note") or h.get("fix") or "").strip()
        why = re.sub(r"\s+", " ", why)[:320]
        lines.append(f"- #{h['pr']} → **{h['truth']}**: {h['title'][:110]}" + (f"\n  Maintainer: {why}" if why else ""))
    return "\n".join(lines)
