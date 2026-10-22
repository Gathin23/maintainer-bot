"""A small client for the 0G Private Computer router (Anthropic Messages API, tool calls).

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
            ledger.record(model=model, input_tokens=int(usage.get("input_tokens", 0)),
                          output_tokens=int(usage.get("output_tokens", 0)), price=price(model), tag=tag)
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
