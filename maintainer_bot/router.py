"""A small client for the 0G Private Computer router (tool calls).

Claude, GLM and most routed models go through the Anthropic Messages endpoint (/v1/messages). 0GM goes through the
OpenAI endpoint (/v1/chat/completions): on the Anthropic endpoint its default thinking ran past max_tokens and
garbled the tool arguments (report/0gm-research.md, section 1). call_tool_any picks the right one.

The key is read from the environment (OG_PC_API_KEY) or an env file outside the repo; it is never logged.
"""
from __future__ import annotations

import json
import os
import time

import requests

from .ledger import Ledger, Price

ROUTER = os.environ.get("OG_PC_ROUTER", "https://router-api.0g.ai")
KEY_FILE = os.path.expanduser(os.environ.get("OG_PC_KEY_FILE", "~/.config/cleanyourtv-bot/0g.env"))


def api_key() -> str:
    key = os.environ.get("OG_PC_API_KEY")
    if key:
        return key
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, encoding="utf-8") as f:
            for line in f:
                name, _, value = line.strip().partition("=")
                if name == "OG_PC_API_KEY" and value:
                    return value.strip().strip("'\"")
    raise RuntimeError("OG_PC_API_KEY is not set (env var or key file)")


_PRICES: dict[str, Price] = {}


def price(model: str) -> Price:
    """Per-token price from the router's public model list (cached for the run)."""
    if not _PRICES:
        data = requests.get(f"{ROUTER}/v1/models", timeout=30).json()["data"]
        for m in data:
            p = m.get("pricing_usd") or {}
            try:
                _PRICES[m["id"]] = Price(float(p.get("prompt") or 0), float(p.get("completion") or 0))
            except (TypeError, ValueError):
                continue
    if model not in _PRICES:
        raise KeyError(f"model {model} is not on the 0G router")
    return _PRICES[model]


def model_info(model: str) -> dict:
    data = requests.get(f"{ROUTER}/v1/models", timeout=30).json()["data"]
    return next((m for m in data if m["id"] == model), {})


class ToolCallFailed(RuntimeError):
    pass


_INFO: dict[str, dict] = {}


def cache_prices(model: str) -> tuple[float, float]:
    """(cache write, cache read) per token. The router lists cache_write; a read is priced at a tenth of the
    prompt rate (Anthropic's ratio), since the router does not list it."""
    p = price(model)
    if model not in _INFO:
        _INFO[model] = model_info(model)
    info = _INFO[model].get("pricing_usd") or {}
    return float(info.get("cache_write") or p.prompt * 1.25), p.prompt / 10


def record_usage(ledger: Ledger, model: str, usage: dict, tag: str = "") -> float:
    """Log one call's cost, prompt-cache tokens included.

    The router caches long prompts by itself: a 70K-token prompt can come back as a few hundred input_tokens plus
    cache_creation_input_tokens and cache_read_input_tokens. Counting input_tokens alone undercounts the cost."""
    usd = ledger.record(model=model, input_tokens=int(usage.get("input_tokens", 0)),
                        output_tokens=int(usage.get("output_tokens", 0)), price=price(model), tag=tag)
    cw, cr = int(usage.get("cache_creation_input_tokens") or 0), int(usage.get("cache_read_input_tokens") or 0)
    if cw or cr:
        write, read = cache_prices(model)
        usd += ledger.record(model=model, input_tokens=cw + cr, output_tokens=0,
                             price=Price((cw * write + cr * read) / (cw + cr), 0), tag=tag + ":cache")
    return usd


def call_tool(*, model: str, system: str, user: str, tool: dict, ledger: Ledger, max_tokens: int = 4000,
              tag: str = "", retries: int = 3, timeout: int = 240, deadline_s: int = 900) -> dict:
    """Send one message and force a single tool call; returns the tool input. Costs go to the ledger.

    Paid retries are kept to a minimum: a refusal is final, an answer without the tool gets one more try,
    and the whole call gives up after deadline_s seconds."""
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
        "tools": [tool],
        "tool_choice": {"type": "tool", "name": tool["name"]},
    }
    headers = {"x-api-key": api_key(), "anthropic-version": "2023-06-01", "content-type": "application/json"}
    last = None
    started, answered_without_tool = time.monotonic(), 0
    for attempt in range(retries):
        if time.monotonic() - started > deadline_s:
            raise ToolCallFailed(f"gave up after {deadline_s}s ({last or 'no answer'})")
        ledger.check()
        try:
            r = requests.post(f"{ROUTER}/v1/messages", headers=headers, data=json.dumps(body), timeout=timeout)
        except requests.RequestException as e:  # network blip: wait and retry, never switch provider
            last = str(e)
            time.sleep(5 * (attempt + 1))
            continue
        if r.status_code >= 500 or r.status_code == 429:
            # "temporarily overloaded, retry in 30 seconds": back off, never switch to another provider
            last = f"HTTP {r.status_code}"
            time.sleep(30 + 15 * attempt)
            continue
        d = r.json()
        usage = d.get("usage") or {}
        if usage:
            record_usage(ledger, model, usage, tag)
        if r.status_code == 400 and "tool" in str(d).lower() and body["tool_choice"].get("type") != "auto":
            # some routed models (e.g. Claude on 0G PC) refuse a forced tool; ask for it instead
            body["tool_choice"] = {"type": "auto"}
            body["messages"][0]["content"] += f"\n\nAnswer only by calling the {tool['name']} tool."
            continue
        if r.status_code != 200:
            raise ToolCallFailed(f"HTTP {r.status_code}: {str(d.get('error') or d)[:300]}")
        for block in d.get("content") or []:
            if block.get("type") == "tool_use" and block.get("name") == tool["name"]:
                return block.get("input") or {}
        stop = d.get("stop_reason")
        last = f"no tool call (stop_reason={stop})"
        if stop == "refusal":  # asking again costs the same and gets the same answer
            raise ToolCallFailed("the model declined to review this one")
        if stop == "max_tokens":
            body["max_tokens"] = min(int(body["max_tokens"] * 2), 16000)
        else:
            answered_without_tool += 1
            if answered_without_tool > 1:
                raise ToolCallFailed(last)
    raise ToolCallFailed(last or "unknown error")


# ---------- the OpenAI endpoint (0GM) ----------

OPENAI_PREFIXES = ("0gm",)


def is_openai_model(model: str) -> bool:
    return (model or "").startswith(OPENAI_PREFIXES)


def record_openai_usage(ledger: Ledger, model: str, usage: dict, tag: str = "") -> float:
    """Log one OpenAI-format call. prompt_tokens already includes the cached tokens
    (prompt_tokens_details.cached_tokens) and completion_tokens includes the reasoning tokens, so pricing both at
    the listed rates leaves nothing out (cached tokens are counted at the full prompt rate: a slight overcount,
    the safe side for a cap)."""
    return ledger.record(model=model, input_tokens=int(usage.get("prompt_tokens") or 0),
                         output_tokens=int(usage.get("completion_tokens") or 0), price=price(model), tag=tag)


def call_tool_openai(*, model: str, system: str, user: str, tool: dict, ledger: Ledger, max_tokens: int = 4000,
                     thinking: str | None = None, tag: str = "", retries: int = 3, timeout: int = 240,
                     deadline_s: int = 900) -> dict:
    """One forced tool call on /v1/chat/completions; returns the tool input. Costs go to the ledger.

    thinking: None = off (0GM's chat-template flag enable_thinking=false), or a reasoning_effort
    ("low" | "medium" | "high")."""
    body = {"model": model, "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "tools": [{"type": "function", "function": {"name": tool["name"], "description": tool["description"],
                                                         "parameters": tool["input_schema"]}}],
            "tool_choice": {"type": "function", "function": {"name": tool["name"]}}}
    if is_openai_model(model):
        if thinking:
            body["reasoning_effort"] = thinking
        else:
            body["chat_template_kwargs"] = {"enable_thinking": False}
    headers = {"Authorization": f"Bearer {api_key()}", "content-type": "application/json"}
    last, started, bad_answers = None, time.monotonic(), 0
    for attempt in range(retries):
        if time.monotonic() - started > deadline_s:
            raise ToolCallFailed(f"gave up after {deadline_s}s ({last or 'no answer'})")
        ledger.check()
        try:
            r = requests.post(f"{ROUTER}/v1/chat/completions", headers=headers, data=json.dumps(body),
                              timeout=timeout)
        except requests.RequestException as e:
            last = str(e)[:160]
            time.sleep(5 * (attempt + 1))
            continue
        if r.status_code >= 500 or r.status_code == 429:
            last = f"HTTP {r.status_code}"
            time.sleep(20 + 15 * attempt)
            continue
        d = r.json()
        if d.get("usage"):
            record_openai_usage(ledger, model, d["usage"], tag)
        if r.status_code != 200:
            raise ToolCallFailed(f"HTTP {r.status_code}: {str(d.get('error') or d)[:300]}")
        ch = (d.get("choices") or [{}])[0]
        for call in (ch.get("message") or {}).get("tool_calls") or []:
            fn = call.get("function") or {}
            if fn.get("name") == tool["name"]:
                try:
                    out = json.loads(fn.get("arguments") or "{}")
                    if isinstance(out, dict):
                        return out
                except json.JSONDecodeError:
                    pass
                last = "tool arguments were not a JSON object"
                break
        else:
            last = f"no tool call (finish_reason={ch.get('finish_reason')})"
        if ch.get("finish_reason") == "length":
            body["max_tokens"] = min(int(body["max_tokens"] * 2), 32000)
        else:
            bad_answers += 1
            if bad_answers > 1:
                raise ToolCallFailed(last)
    raise ToolCallFailed(last or "unknown error")


def call_tool_any(*, model: str, thinking: str | None = None, **kw) -> dict:
    """call_tool on the endpoint that suits the model: OpenAI for 0GM, Anthropic for the rest."""
    if is_openai_model(model):
        return call_tool_openai(model=model, thinking=thinking, **kw)
    return call_tool(model=model, **kw)
