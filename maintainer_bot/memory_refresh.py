"""Refresh the bot's memory from the maintainer's round notes.

The live bot reads two files from the reviewed repo's default branch: `.github/maintainer/precedents.jsonl` (past
decisions, for retrieval) and `.github/maintainer/MAINTAINER.md` (the rules). Both go stale between rounds: on
27 Oct the precedents stopped at 22 Oct while five rounds (more than 1,000 decisions) had happened since, and the
backtest showed that adding them cut the bot's wrong merge suggestions from 9 to 3 (report/0gm-research.md 4.2).

This module turns the round files (markdown written for and approved by the maintainer) into precedent lines:
- bucket tables: `## Merge as is` / `## Merge with a fix` / `## Ask` / `## Close` / `## Hold` sections with rows
  `| #N | title (@author) | what | (fix) | why |`;
- review tables with a verdict column (MERGE, MERGE+FIX, ASK, HOLD, CLOSE);
- "Applied" tables `| n | #N title | merge SHA | @author | fix folded in |` (merge, or merge-with-fix when a fix
  was folded in);
- bullets and drafted comments in ask/close/hold sections (`- #N: note`, `#N (@author, ..., ASK):` + the draft);
- round AA's summary bullets ("Merged N:", "Fold-ins").
Wait / carried / "ask already out" sections are not new decisions and are skipped.

Later rounds override earlier ones; a changed verdict keeps the earlier one in the note ("(earlier: rework)"), as
scripts/export_precedents_v4.py does. GitHub's own record (merged / closed, read-only) settles what really happened,
and with a cutoff (`until`) only events before it count, so a backtest's memory never knows the future.

It also extracts the policy material (the "least sure" calls, alarming findings, the round bar) into a candidates
file that a person curates into a short policy block for MAINTAINER.md; `apply_policy_block` puts that block into
MAINTAINER.md idempotently.
"""
from __future__ import annotations

import json
import os
import re
import subprocess

# (round, files in reading order, when its decisions were applied on main, UTC)
ROUNDS = [
    ("aa", ["round-aa.md"], "2026-10-25T17:31:35Z"),
    ("ab", ["round-ab-decisions.md"], "2026-10-25T18:21:03Z"),
    ("ac", ["round-ac-decisions.md"], "2026-10-26T04:29:27Z"),
    ("ad", ["round-ad.md"], "2026-10-26T17:16:39Z"),
    ("ae", ["round-ae.md"], "2026-10-27T02:26:15Z"),
    ("af", ["round-af.md"], "2026-10-27T13:50:58Z"),
    ("ag", ["round-ag/review-A.md", "round-ag/review-B.md", "round-ag/review-C.md", "round-ag.md"],
     "2026-10-28T02:24:55Z"),
    ("ag2", ["round-ag/review-D.md", "round-ag/review-E.md", "round-ag/review-F.md", "round-ag2.md"],
     "2026-10-28T02:53:36Z"),
]
# the moment a round's memory is frozen for a leak-free backtest: nothing GitHub did after it may count
CUTOFF = {"aa": "2026-10-25T18:00:00Z", "ab": "2026-10-26T00:00:00Z", "ac": "2026-10-26T12:00:00Z",
          "ad": "2026-10-26T21:00:00Z", "ae": "2026-10-27T08:00:00Z", "af": "2026-10-28T00:00:00Z",
          "ag": "2026-10-28T02:40:00Z", "ag2": "9999-12-31T00:00:00Z"}
ACCEPT = ("merge", "merge-with-fix")
NOTE_CAP, FIX_CAP = 700, 320

SKIP_HEADING = re.compile(r"\bwait\b|carried|already out|standing|thank|prepared branch|least[- ]sure|alarming|^files|"
                          r"counts|overlaps|open issues|release notes|what the script|^skipped|stale|gathin's call|"
                          r"^order|apply script|^output|^read first|^verdicts", re.I)
VERDICT_WORDS = {"merge": "merge", "merge+fix": "merge-with-fix", "merge + fix": "merge-with-fix",
                 "ask": "rework", "close": "close", "hold": "hold"}


def bucket_of(heading: str) -> str | None:
    """The decision a section's rows carry, or None (not a decision section)."""
    h = re.sub(r"^#+\s*", "", heading).strip().lower()
    if SKIP_HEADING.search(h):
        return None
    if h.startswith("applied"):
        return "applied"
    if re.search(r"merge (with a fix|\+ ?fix)", h):
        return "merge-with-fix"
    if h.startswith("merge as is"):
        return "merge"
    if re.search(r"\bclose", h) and not re.search(r"\basks? and closes\b", h):
        return "close"
    if re.search(r"\bask|changes \(drafted ask\)|asks? and closes", h):
        return "rework"
    if re.search(r"\bhold|\bheld\b", h):
        return "hold"
    return None


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _plain(s: str) -> str:
    s = re.sub(r"\*\*|`", "", s or "")
    return re.sub(r"\s+", " ", s).strip()


def _title_cell(s: str) -> str:
    return re.sub(r"\s*\(@[^)]*\)\s*$", "", _plain(s))


def _verdict_word(s: str) -> str | None:
    return VERDICT_WORDS.get(_plain(s).lower())


def parse_round_text(text: str) -> dict[int, dict]:
    """{pr: {truth, maintainer_note, fix, title}} from one round file; a later line about the same PR wins."""
    out: dict[int, dict] = {}
    h2 = h3 = None
    bucket = None
    cols: list[str] | None = None
    in_code = False
    aa_mode = None            # round AA's summary bullets: "merged" or "foldins"
    skip_bullets = False
    pending: tuple[int, str] | None = None   # a drafted comment whose text is on the next lines
    lines = text.splitlines()

    def put(n: int, truth: str, note: str = "", fix: str = "", title: str = "") -> None:
        e = out.get(n, {})
        e.update(truth=truth)
        if note:
            e["maintainer_note"] = _plain(note)[:NOTE_CAP]
        else:
            e.setdefault("maintainer_note", "")
        if fix:
            e["fix"] = _plain(fix)[:FIX_CAP]
        else:
            e.setdefault("fix", "")
        if title:
            e["title"] = title
        out[n] = e

    for i, line in enumerate(lines):
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if pending:
            if line.strip():
                n, truth = pending
                put(n, truth, note=line)
                pending = None
                continue
        if line.startswith("## "):
            h2, h3 = line, None
            bucket, cols, aa_mode, skip_bullets = bucket_of(line), None, None, False
            continue
        if line.startswith("### "):
            h3 = line
            cols, skip_bullets = None, False
            continue
        if line.startswith("# "):
            continue
        s = line.strip()
        # ---- tables
        if s.startswith("|"):
            nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
            if re.match(r"^\|[\s:|-]+\|$", nxt) and not re.match(r"^\|[\s:|-]+\|$", s):
                cols = [c.lower() for c in _cells(s)]
                continue
            if re.match(r"^\|[\s:|-]+\|$", s) or not cols:
                continue
            c = _cells(s)
            m0 = re.match(r"^#(\d+)\b", c[0]) if c else None
            m1 = re.match(r"^#(\d+)\b\s*(.*)$", c[1]) if len(c) > 1 else None
            if "verdict" in cols and m0:
                v = _verdict_word(c[cols.index("verdict")])
                if not v:
                    continue
                rest = [c[k] for k, name in enumerate(cols) if k < len(c) and k != cols.index("verdict")
                        and not re.search(r"sha|author|^pr$", name)]
                put(int(m0.group(1)), v, note=" | ".join(x for x in rest if x and x != "-"))
            elif any("merge sha" in x for x in cols) and m1:
                fix = c[-1] if len(c) >= 5 else ""
                put(int(m1.group(1)), "merge-with-fix" if _plain(fix) else "merge", fix=fix,
                    title=_plain(m1.group(2)))
            elif m0 and bucket and bucket != "applied":
                title = _title_cell(c[1]) if len(c) > 1 else ""
                body = [x for x in c[2:] if x and x != "-"]
                fix = ""
                if bucket == "merge-with-fix":
                    for k, name in enumerate(cols):
                        if k < len(c) and re.search(r"fix|recommendation", name):
                            fix = c[k]
                put(int(m0.group(1)), bucket, note=" | ".join(body), fix=fix, title=title)
            continue
        cols = None
        # ---- round AA's summary bullets (before any section heading)
        if h2 is None:
            if re.match(r"^- \*\*Merged", s):
                aa_mode = "merged"
                continue
            if re.match(r"^- Fold-ins", s):
                aa_mode = "foldins"
                continue
            if line.startswith("- "):
                aa_mode = None
                continue
            if aa_mode and line.startswith("  "):
                if aa_mode == "foldins":
                    m = re.match(r"^\s*- #(\d+): (.*)$", line)
                    if m:
                        put(int(m.group(1)), "merge-with-fix", note=m.group(2), fix=m.group(2))
                else:
                    for m in re.finditer(r"#(\d+)(?: \(([^)]*)\))?", line):
                        n = int(m.group(1))
                        if n not in out:
                            put(n, "merge", note=m.group(2) or "")
            continue
        if bucket not in ("rework", "close", "hold"):
            continue
        # ---- drafted comments: "#N (@author, ..., ASK):" then the draft on the next line
        m = re.match(r"^#(\d+)\b(?: \(([^)]*)\))?:\s*(.*)$", s)
        if m:
            n, paren, rest = int(m.group(1)), m.group(2) or "", m.group(3)
            if re.search(r"no new comment|nothing new", rest, re.I):
                continue
            truth = "close" if re.search(r"\bCLOSE\b", paren) else "rework" if re.search(r"\bASK\b", paren) \
                else "hold" if re.search(r"\bHOLD\b", paren) else bucket
            if rest:
                put(n, truth, note=rest)
            else:
                pending = (n, truth)
            continue
        # ---- bullets in ask / close / hold sections
        if not s:
            continue
        bm = re.match(r"^(?:[-*]|\d+\.)\s+(?:\*\*)?#(\d+)\b(.*)$", s)
        if not bm:
            skip_bullets = bool(re.search(r"standing|carried|nothing new|untouched|wait", s, re.I))
            continue
        if skip_bullets:
            continue
        bold = re.match(r"^(?:[-*]|\d+\.)\s+\*\*(.*?)\*\*", s)
        head = bold.group(1) if bold else re.split(r":\s", bm.group(2), maxsplit=1)[0][:80]
        nums = [int(bm.group(1))] + [int(x) for x in re.findall(r"#(\d+)", head)]
        for n in dict.fromkeys(nums):
            put(n, bucket, note=re.sub(r"^(?:[-*]|\d+\.)\s+", "", s))
    return out


def parse_rounds(launch_dir: str, until: str | None = None, rounds=ROUNDS) -> list[tuple[str, str, dict]]:
    """[(round, decided_at, {pr: decision})] in order, stopping after `until` (inclusive)."""
    out = []
    for key, files, when in rounds:
        merged: dict[int, dict] = {}
        for f in files:
            p = os.path.join(launch_dir, f)
            if not os.path.exists(p):
                continue
            for n, d in parse_round_text(_read(p)).items():
                e = merged.get(n, {})
                e.update({k: v for k, v in d.items() if v or k not in e})
                merged[n] = e
        out.append((key, when, merged))
        if until and key == until:
            break
    return out


def fold(base: list[dict], rounds: list[tuple[str, str, dict]]) -> dict[int, dict]:
    """The existing precedents, then each round in order. A changed verdict keeps the earlier one in the note."""
    entries: dict[int, dict] = {e["pr"]: dict(e) for e in base}
    for key, when, decisions in rounds:
        for n, d in decisions.items():
            before = entries.get(n)
            note = d.get("maintainer_note", "")
            if before and before["truth"] != d["truth"]:
                note = f"(earlier: {before['truth']}) {note}".strip()
            entries[n] = {"pr": n, "title": d.get("title") or (before or {}).get("title", ""),
                          "truth": d["truth"], "decided_at": when, "maintainer_note": note[:NOTE_CAP],
                          "fix": d.get("fix", ""), "files": (before or {}).get("files", []),
                          "round": key}
    return entries


GQL_FIELDS = "number title state merged mergedAt closedAt files(first: 40) { nodes { path } }"


def gh_graphql(query: str) -> dict:
    """Read-only GitHub GraphQL through the gh CLI. Unknown numbers (issues) come back null with an error."""
    r = subprocess.run(["gh", "api", "graphql", "-f", f"query={query}"], capture_output=True, text=True, timeout=120)
    try:
        return json.loads(r.stdout or "{}").get("data") or {}
    except json.JSONDecodeError:
        return {}


def fetch_prs(numbers: list[int], repo: str = "Gathin23/cleanyourtv", batch: int = 50, gql=gh_graphql) -> dict[int, dict]:
    owner, name = repo.split("/")
    out: dict[int, dict] = {}
    nums = sorted(set(numbers))
    for i in range(0, len(nums), batch):
        part = nums[i:i + batch]
        body = " ".join(f"p{n}: pullRequest(number: {n}) {{ {GQL_FIELDS} }}" for n in part)
        data = gql(f'query {{ repository(owner: "{owner}", name: "{name}") {{ {body} }} }}')
        repo_d = (data or {}).get("repository") or {}
        for n in part:
            p = repo_d.get(f"p{n}")
            if p:
                out[n] = {"title": p.get("title", ""), "state": p.get("state", ""), "merged": bool(p.get("merged")),
                          "merged_at": p.get("mergedAt") or "", "closed_at": p.get("closedAt") or "",
                          "files": [f["path"] for f in ((p.get("files") or {}).get("nodes") or [])][:40]}
    return out


def cross_check(entries: dict[int, dict], gh: dict[int, dict], cutoff: str = "9999-12-31T00:00:00Z",
                only: set[int] | None = None) -> dict:
    """GitHub's record settles what happened (only events before `cutoff` count). Returns override counts."""
    stats = {"merged_override": 0, "closed_override": 0, "accept_not_merged": 0, "titles": 0, "files": 0}
    for n, e in entries.items():
        if only is not None and n not in only:
            continue
        g = gh.get(n)
        if not g:
            continue
        if g["title"] and e.get("title") != g["title"]:
            e["title"] = g["title"]
            stats["titles"] += 1
        if g["files"] and not e.get("files"):
            e["files"] = g["files"]
            stats["files"] += 1
        merged = g["merged"] and g["merged_at"] and g["merged_at"] <= cutoff
        closed = g["state"] == "CLOSED" and not g["merged"] and g["closed_at"] and g["closed_at"] <= cutoff
        if merged:
            if e["truth"] not in ACCEPT:
                e["maintainer_note"] = f"(earlier: {e['truth']}) merged later. {e['maintainer_note']}".strip()[:NOTE_CAP]
                e["truth"] = "merge"
                e["decided_at"] = max(e["decided_at"], g["merged_at"])
                stats["merged_override"] += 1
        elif closed:
            if e["truth"] != "close":
                e["maintainer_note"] = (f"(earlier: {e['truth']}) closed without merging. "
                                        f"{e['maintainer_note']}").strip()[:NOTE_CAP]
                e["truth"] = "close"
                e["decided_at"] = max(e["decided_at"], g["closed_at"])
                stats["closed_override"] += 1
        elif e["truth"] in ACCEPT:
            # the round said merge, but it never merged (skipped at apply, back to draft, a new push): a hold
            e["maintainer_note"] = (f"(round said {e['truth']}; not merged at apply) "
                                    f"{e['maintainer_note']}").strip()[:NOTE_CAP]
            e["truth"] = "hold"
            stats["accept_not_merged"] += 1
    return stats


KEYS = ("pr", "title", "truth", "decided_at", "maintainer_note", "fix", "files")


def to_jsonl(entries: dict[int, dict]) -> str:
    rows = sorted(entries.values(), key=lambda e: e["decided_at"])   # stable: the existing lines keep their order
    return "".join(json.dumps({k: e.get(k, "" if k != "files" else []) for k in KEYS}, ensure_ascii=False) + "\n"
                   for e in rows)


# ---------- policy material ----------

POLICY_SECTIONS = re.compile(r"least[- ]sure|alarming|^## verdicts", re.I)
DRAFT_LINE = re.compile(r"^\s*(?:- \*\*#\d+\*\*: )?(merged,|thanks|thank you|[-+]#|[-+]\s)", re.I)
RULE_LINE = re.compile(r"\b(rule|the bar|same bar|policy|no new|never|always|lean to|only takes|the line)\b", re.I)


def policy_candidates(launch_dir: str, until: str | None = None, extra_files: tuple[str, ...] = ()) -> str:
    """The raw policy material, in round order: every "least sure" and "alarming" section, plus intro lines that
    state a rule (the round bar). A person curates this into the short block in MAINTAINER.md."""
    out = []
    files = []
    for key, fs, _ in ROUNDS:
        files += [(key, f) for f in fs]
        if until and key == until:
            break
    files += [("brief", f) for f in extra_files]
    for key, f in files:
        p = os.path.join(launch_dir, f)
        if not os.path.exists(p):
            continue
        text = _read(p)
        keep, section = [], None
        for line in text.splitlines():
            if line.startswith("## "):
                section = line if POLICY_SECTIONS.search(line) else None
                if section:
                    keep.append(line)
                continue
            if section:
                if line.strip():
                    keep.append(line)
            elif RULE_LINE.search(line) and not line.startswith(("|", "#")) and not DRAFT_LINE.match(line) \
                    and len(line) < 1200:
                keep.append(line)
        if keep:
            out.append(f"# {key}: {f}\n" + "\n".join(keep))
    return "\n\n".join(out) + "\n"


def apply_policy_block(rules_md: str, block: str) -> str:
    """Put the block at the end of MAINTAINER.md, replacing an earlier copy (same first heading line)."""
    block = block.strip() + "\n"
    head = block.splitlines()[0]
    if head in rules_md:
        start = rules_md.index(head)
        nxt = re.search(r"^## ", rules_md[start + len(head):], re.M)
        end = start + len(head) + nxt.start() if nxt else len(rules_md)
        return rules_md[:start] + block + ("\n" + rules_md[end:] if nxt else "")
    return rules_md.rstrip("\n") + "\n\n" + block
