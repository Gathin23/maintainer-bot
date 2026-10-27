"""Research only (not wired into the live bot): long-context reviews on 0GM and other router models.

The live bot sends the decision model about 6,000 characters of diff, the first 1,200 of the description and the
five most similar past decisions. A long-context model can read far more. This module builds the extra context in
named blocks, so each block can be switched on and off and measured on the v4 backtest set:

  D  the full diff (every file, every line) and the whole description
  F  the files around the change: modified files as they were on main, the closest existing list folders for a
     new TV list, the add-ons/themes index for an add-on or theme
  R  the repo's own rules as they were on main: CONTRIBUTING.md, PROMPT.md, AGENTS.md, tools/recovery.py
  P  thirty past decisions instead of five, with longer maintainer notes
  X  related work: the diffs of other PRs open on the same files, and what main merged on those files that week
  I  the issues and PRs the PR names (#N), with comments written before the decision

Everything is read as it was when the maintainer decided (main at the round's start, comments before decided_at).
0GM is called through the router's OpenAI-compatible endpoint: on the Anthropic endpoint its default thinking
ran past max_tokens and garbled tool arguments in the first probe.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from functools import lru_cache

import requests

from . import checklists, retrieval, v4
from .ledger import Ledger
from .router import ROUTER, ToolCallFailed, api_key, price

BLOCKS = "DFRPXI"
CHARS_PER_TOKEN = 3.6          # rough, for budgeting only; the router reports the real count
FULL_DIFF_CAP = 400_000        # characters; a 1,400-file PR is cut here, not at 6,000
FILE_CAP, FILES_CAP = 30_000, 90_000
RULE_FILES = ("CONTRIBUTING.md", "PROMPT.md", "AGENTS.md", "tools/recovery.py")
TABLE_FILES = v4.TABLE_FILES | {"README.it.md", "README.ja.md", "README.vi.md", "README.zh-TW.md", "README.nl.md"}


# ---------- the router, OpenAI format ----------

def call_tool_oa(*, model: str, system: str, user: str, tool: dict, ledger: Ledger, max_tokens: int = 4000,
                 thinking: str | None = None, tag: str = "", retries: int = 4, timeout: int = 600) -> tuple[dict, dict]:
    """One forced tool call on /v1/chat/completions. Returns (tool input, stats).

    thinking: None = off (0GM's chat template flag), or a reasoning_effort ("low" | "medium" | "high")."""
    body = {"model": model, "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "tools": [{"type": "function", "function": {"name": tool["name"], "description": tool["description"],
                                                         "parameters": tool["input_schema"]}}],
            "tool_choice": {"type": "function", "function": {"name": tool["name"]}}}
    if model.startswith("0gm"):
        if thinking:
            body["reasoning_effort"] = thinking
        else:
            body["chat_template_kwargs"] = {"enable_thinking": False}
    headers = {"Authorization": f"Bearer {api_key()}", "content-type": "application/json"}
    last = ""
    for attempt in range(retries):
        ledger.check()
        t0 = time.monotonic()
        try:
            r = requests.post(f"{ROUTER}/v1/chat/completions", headers=headers, data=json.dumps(body), timeout=timeout)
        except requests.RequestException as e:
            last = str(e)[:120]
            time.sleep(5 * (attempt + 1))
            continue
        secs = time.monotonic() - t0
        if r.status_code >= 500 or r.status_code == 429:
            last = f"HTTP {r.status_code}"
            time.sleep(20 + 20 * attempt)
            continue
        d = r.json()
        u = d.get("usage") or {}
        stats = {"in": int(u.get("prompt_tokens") or 0), "out": int(u.get("completion_tokens") or 0),
                 "reasoning": int(u.get("reasoning_tokens") or 0),
                 "cached": int(((u.get("prompt_tokens_details") or {}).get("cached_tokens")) or 0), "secs": round(secs, 1)}
        if u:
            stats["usd"] = ledger.record(model=model, input_tokens=stats["in"], output_tokens=stats["out"],
                                         price=price(model), tag=tag)
        if r.status_code != 200:
            raise ToolCallFailed(f"HTTP {r.status_code}: {str(d.get('error') or d)[:300]}")
        ch = (d.get("choices") or [{}])[0]
        for call in (ch.get("message") or {}).get("tool_calls") or []:
            fn = call.get("function") or {}
            if fn.get("name") == tool["name"]:
                try:
                    return json.loads(fn.get("arguments") or "{}"), stats
                except json.JSONDecodeError:
                    last = "tool arguments were not JSON"
                    break
        else:
            last = f"no tool call (finish_reason={ch.get('finish_reason')})"
        if ch.get("finish_reason") == "length":
            body["max_tokens"] = min(body["max_tokens"] * 2, 32000)
    raise ToolCallFailed(last or "unknown error")


def call_tool_anthropic(*, model: str, system: str, user: str, tool: dict, ledger: Ledger, max_tokens: int = 3000,
                        tag: str = "", retries: int = 4, timeout: int = 900) -> tuple[dict, dict]:
    """Like router.call_tool, but the cost counts the prompt-cache tokens too.

    The router caches long prompts on its own: usage then reports most of the prompt as cache_creation_input_tokens
    and cache_read_input_tokens, and only a few hundred as input_tokens. router.call_tool (and so the live ledger)
    prices input_tokens and output_tokens only, which undercounts a long prompt. Cache writes are priced at the
    model's listed cache_write rate; cache reads at a tenth of the prompt rate (Anthropic's usual ratio, the router
    does not list it)."""
    body = {"model": model, "max_tokens": max_tokens, "system": system,
            "messages": [{"role": "user", "content": user + f"\n\nAnswer only by calling the {tool['name']} tool."}],
            "tools": [tool], "tool_choice": {"type": "auto"}}
    headers = {"x-api-key": api_key(), "anthropic-version": "2023-06-01", "content-type": "application/json"}
    info = _model_info(model)
    p = price(model)
    write = float((info.get("pricing_usd") or {}).get("cache_write") or p.prompt * 1.25)
    last = ""
    for attempt in range(retries):
        ledger.check()
        t0 = time.monotonic()
        try:
            r = requests.post(f"{ROUTER}/v1/messages", headers=headers, data=json.dumps(body), timeout=timeout)
        except requests.RequestException as e:
            last = str(e)[:120]
            time.sleep(5 * (attempt + 1))
            continue
        if r.status_code >= 500 or r.status_code == 429:
            last = f"HTTP {r.status_code}"
            time.sleep(30 + 15 * attempt)
            continue
        d = r.json()
        u = d.get("usage") or {}
        cw, cr = int(u.get("cache_creation_input_tokens") or 0), int(u.get("cache_read_input_tokens") or 0)
        stats = {"in": int(u.get("input_tokens") or 0) + cw + cr, "out": int(u.get("output_tokens") or 0),
                 "cache_write": cw, "cache_read": cr, "secs": round(time.monotonic() - t0, 1)}
        if u:
            usd = ledger.record(model=model, input_tokens=int(u.get("input_tokens") or 0), output_tokens=stats["out"],
                                price=p, tag=tag)
            from .ledger import Price
            usd += ledger.record(model=model, input_tokens=cw, output_tokens=0, price=Price(write, 0), tag=tag + ":cw")
            usd += ledger.record(model=model, input_tokens=cr, output_tokens=0, price=Price(p.prompt / 10, 0),
                                 tag=tag + ":cr")
            stats["usd"] = round(usd, 6)
        if r.status_code != 200:
            raise ToolCallFailed(f"HTTP {r.status_code}: {str(d.get('error') or d)[:300]}")
        for block in d.get("content") or []:
            if block.get("type") == "tool_use" and block.get("name") == tool["name"]:
                return block.get("input") or {}, stats
        last = f"no tool call (stop_reason={d.get('stop_reason')})"
        if d.get("stop_reason") == "refusal":
            raise ToolCallFailed("the model declined")
        if d.get("stop_reason") == "max_tokens":
            body["max_tokens"] = min(body["max_tokens"] * 2, 16000)
    raise ToolCallFailed(last or "unknown error")


@lru_cache(maxsize=64)
def _model_info(model: str) -> dict:
    data = requests.get(f"{ROUTER}/v1/models", timeout=30).json()["data"]
    return next((m for m in data if m["id"] == model), {})


# ---------- context blocks ----------

def _git(git_dir: str, *args: str) -> str:
    r = subprocess.run(["git", "-C", git_dir, *args], capture_output=True, text=True, errors="replace")
    return r.stdout if r.returncode == 0 else ""


@lru_cache(maxsize=8192)
def blob(git_dir: str, commit: str, path: str) -> str:
    return _git(git_dir, "show", f"{commit}:{path}") if commit else ""


def _cut(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n] + f"\n… ({len(s) - n} more chars cut)"


def full_diff(snap: dict, cap: int = FULL_DIFF_CAP) -> str:
    parts = []
    for f in snap["files"]:
        head = f"### {f['path']} ({f.get('status', 'modified')}, +{f.get('additions', 0)} -{f.get('deletions', 0)})"
        if f.get("binary"):
            parts.append(head + "\n(binary)")
        else:
            parts.append(head + "\n" + (f.get("patch") or "(no patch)"))
    return _cut("\n\n".join(parts), cap)


def block_files(r: dict, snap: dict, git_dir: str) -> str:
    main = r["facts"].get("main_at_review") or r.get("main_at") or ""
    out, used = [], 0
    for f in snap["files"]:
        p = f["path"]
        if f.get("status") != "modified" or f.get("binary") or p in TABLE_FILES or used > FILES_CAP:
            continue
        text = blob(git_dir, main, p)
        if text:
            piece = f"### {p} (on main before this PR)\n{_cut(text, FILE_CAP)}"
            out.append(piece)
            used += len(piece)
    # a new TV list: the existing folders closest to it, so "same product already on main" can be checked by reading
    new = sorted({p.split("/")[1] for p in (x["path"] for x in snap["files"])
                  if p.startswith("examples/") and p.count("/") >= 2})
    if new:
        tree = _git(git_dir, "ls-tree", "-d", "--name-only", f"{main}:examples").split()
        for folder in new[:2]:
            if folder in tree:
                continue
            toks = set(re.split(r"[-_]", folder.lower()))
            near = sorted((t for t in tree if t != folder),
                          key=lambda t: -len(toks & set(re.split(r"[-_]", t.lower()))))[:2]
            for n in near:
                if len(toks & set(re.split(r"[-_]", n.lower()))) < 2:
                    continue
                files = _git(git_dir, "ls-tree", "-r", "--name-only", main, f"examples/{n}").split()
                body = "\n".join(f"#### {x}\n{_cut(blob(git_dir, main, x), 6000)}" for x in files[:4]
                                 if not x.endswith((".png", ".jpg", ".jpeg", ".webp")))
                out.append(f"### Existing folder on main: examples/{n}\n{_cut(body, 14000)}")
    for idx in ("addons/README.md", "themes/README.md"):
        top = idx.split("/")[0] + "/"
        if any(x["path"].startswith(top) for x in snap["files"]):
            out.append(f"### {idx} (on main)\n{_cut(blob(git_dir, main, idx), 15000)}")
    return "\n\n".join(out)


def block_rules(r: dict, git_dir: str) -> str:
    main = r["facts"].get("main_at_review") or r.get("main_at") or ""
    out = []
    for p in RULE_FILES:
        text = blob(git_dir, main, p)
        if text:
            out.append(f"### {p}\n{_cut(text, 20000)}")
    return "\n\n".join(out)


def block_related(r: dict, snaps: dict, git_dir: str, own_files: list[str]) -> str:
    out = []
    for o in (r.get("batch") or {}).get("other_open_prs_touching_the_same_files", [])[:6]:
        s = snaps.get(o["pr"])
        if s:
            out.append(f"### Open PR #{o['pr']}: {s['title'][:100]} (shares {', '.join(o['shared_files'][:3])})\n"
                       + _cut(full_diff(s), 5000))
    main = r["facts"].get("main_at_review") or r.get("main_at") or ""
    paths = [p for p in own_files if p not in TABLE_FILES and not p.startswith("examples/README")][:12]
    if main and paths:
        since = _git(git_dir, "log", "-1", "--format=%ct", main).strip()
        since = str(int(since) - 7 * 86400) if since else "0"
        log = _git(git_dir, "log", "--first-parent", f"--since={since}", "--format=%h %s", "-n", "8", main, "--", *paths)
        for line in log.splitlines()[:6]:
            sha = line.split()[0]
            diff = _git(git_dir, "show", "--format=%h %s", "-m", "--first-parent", sha, "--", *paths)
            out.append(f"### Merged on main that week: {line}\n{_cut(diff, 4000)}")
    return "\n\n".join(out)


ISSUE_CACHE: dict[str, dict] = {}


def load_issue_cache(path: str) -> None:
    if os.path.exists(path):
        ISSUE_CACHE.update(json.load(open(path)))


def save_issue_cache(path: str) -> None:
    json.dump(ISSUE_CACHE, open(path, "w"))


def _issue(repo: str, n: int) -> dict:
    key = f"{repo}#{n}"
    if key not in ISSUE_CACHE:
        try:
            i = json.loads(subprocess.run(["gh", "api", f"repos/{repo}/issues/{n}"], capture_output=True,
                                          text=True, timeout=60).stdout or "{}")
            c = json.loads(subprocess.run(["gh", "api", f"repos/{repo}/issues/{n}/comments?per_page=100"],
                                          capture_output=True, text=True, timeout=60).stdout or "[]")
        except Exception:  # noqa: BLE001 - a missing issue is just no context
            i, c = {}, []
        ISSUE_CACHE[key] = {"title": i.get("title", ""), "body": (i.get("body") or "")[:6000],
                            "is_pr": "pull_request" in i, "created_at": i.get("created_at", ""),
                            "comments": [{"at": x.get("created_at", ""), "by": (x.get("user") or {}).get("login", ""),
                                          "body": (x.get("body") or "")[:1500]} for x in c if isinstance(x, dict)]}
    return ISSUE_CACHE[key]


def block_issues(r: dict, snap: dict, repo: str = "Gathin23/cleanyourtv") -> str:
    text = f"{snap['title']}\n{snap.get('body') or ''}"
    nums = []
    for m in re.finditer(r"(?<![\w/])#(\d{1,5})\b", text):
        n = int(m.group(1))
        if n != r["pr"] and n < r["pr"] + 50 and n not in nums:
            nums.append(n)
    out = []
    for n in nums[:3]:
        i = _issue(repo, n)
        if not i.get("title") or i.get("created_at", "") > r["decided_at"]:
            continue
        cs = [c for c in i["comments"] if c["at"] < r["decided_at"] and "maintainer-bot" not in c["body"]][:8]
        body = "\n".join(f"- @{c['by']}: {re.sub(r'\s+', ' ', c['body'])[:600]}" for c in cs)
        out.append(f"### {'PR' if i['is_pr'] else 'Issue'} #{n}: {i['title'][:120]}\n{_cut(i['body'], 3000)}"
                   + (f"\nComments before this decision:\n{body}" if body else ""))
    return "\n\n".join(out)


LONG_NOTE = """

You have more context than a usual review: the full diff, and, when present, the files around the change, the
repo's own rules files, more past decisions, related open and merged work, and the issues the PR names. Use them:
check the actual lines (not only the summary facts), check whether main or another PR already does this, and
quote the rule you rely on."""


ADDENDUM = ""   # set by a research run: extra policy text appended to the rules when the block set has "M"


def build_user(r: dict, snap: dict, *, blocks: str, index, snaps: dict, git_dir: str, rules_md: str) -> str:
    if "M" in blocks and ADDENDUM:
        rules_md = rules_md + "\n\n" + ADDENDUM
    k = 30 if "P" in blocks else 5
    ex = index.similar(r, k=k)
    if "P" in blocks:
        examples = "\n".join(
            f"- #{h['pr']} → **{h['truth']}**: {h['title'][:110]}"
            + (f"\n  Maintainer: {re.sub(chr(10), ' ', (h.get('maintainer_note') or h.get('fix') or '').strip())[:700]}"
               if (h.get("maintainer_note") or h.get("fix")) else "") for h in ex)
    else:
        examples = retrieval.render(ex)
    base = v4.prompt(r, snap, rules_md, examples)
    if "D" in blocks:
        cut_at = base.index("Description:\n")
        base = base[:cut_at] + "Description:\n" + (snap.get("body") or "").strip()[:4000] + "\n\n## Diff (full)\n" \
            + full_diff(snap) + "\n"
    extra = []
    if "F" in blocks:
        f = block_files(r, snap, git_dir)
        if f:
            extra.append("## Files around the change (as they were on main)\n" + f)
    if "R" in blocks:
        extra.append("## The repo's own rules files (as they were on main)\n" + block_rules(r, git_dir))
    if "X" in blocks:
        x = block_related(r, snaps, git_dir, [f["path"] for f in snap["files"]])
        if x:
            extra.append("## Related work: other open PRs on the same files, and main's merges on them that week\n" + x)
    if "I" in blocks:
        i = block_issues(r, snap)
        if i:
            extra.append("## Issues and PRs this PR names\n" + i)
    return base + ("\n" + "\n\n".join(extra) if extra else "")


def judge(r: dict, snap: dict, *, model: str, blocks: str, thinking: str | None, index, snaps: dict, git_dir: str,
          rules_md: str, ledger: Ledger, max_prompt_tokens: int = 200_000) -> dict:
    """The decision call only (no critic, no second opinion), so arms compare like for like."""
    user = build_user(r, snap, blocks=blocks, index=index, snaps=snaps, git_dir=git_dir, rules_md=rules_md)
    cap = int(max_prompt_tokens * CHARS_PER_TOKEN)
    if len(user) > cap:
        user = user[:cap] + "\n… (context cut to fit the window)"
    system = v4.SYSTEM + (LONG_NOTE if blocks else "")
    out = {"pr": r["pr"], "type": r["type"], "blocks": blocks, "model": model, "thinking": thinking or "off",
           "prompt_chars": len(user)}
    if v4.always_maintainer(r["facts"]):
        out.update(verdict="hold", confidence=0.0, reasons=[], fix="", comment="", skipped_model="always the maintainer")
        return out
    if model.startswith("claude"):
        d, stats = call_tool_anthropic(model=model, system=system, user=user, tool=v4.TOOL, ledger=ledger,
                                       max_tokens=3000, tag=f"lc:{blocks}:{r['pr']}")
    else:
        d, stats = call_tool_oa(model=model, system=system, user=user, tool=v4.TOOL, ledger=ledger,
                                max_tokens=6000 if thinking else 2500, thinking=thinking, tag=f"lc:{blocks}:{r['pr']}")
    out.update(verdict=d.get("verdict") if d.get("verdict") in v4.FAMILY else "hold",
               confidence=float(d.get("confidence") or 0), reasons=d.get("reasons") or [], fix=d.get("fix", ""),
               comment=d.get("comment", ""), specific=d.get("specific", ""), precedent=d.get("precedent", ""),
               priority=d.get("priority", ""), stats=stats)
    return out
