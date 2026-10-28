"""Spend ledger: every model call is logged with its token counts and dollar cost, and a hard cap stops the run.

The ledger is an append-only JSONL file, so a crashed or resumed run still knows what it has spent.
"""
from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass


class BudgetExceeded(RuntimeError):
    """Raised before a call that would start once the cap is reached."""


@dataclass(frozen=True)
class Price:
    """US dollars per token, as the router's /v1/models lists them (pricing_usd)."""
    prompt: float
    completion: float

    def cost(self, input_tokens: int, output_tokens: int) -> float:
        return input_tokens * self.prompt + output_tokens * self.completion


class Ledger:
    def __init__(self, path: str, cap_usd: float):
        self.path = path
        self.cap_usd = cap_usd
        self._lock = threading.Lock()
        self._spent = 0.0
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self._spent += float(json.loads(line).get("usd", 0.0))

    @property
    def spent(self) -> float:
        with self._lock:
            return self._spent

    def check(self) -> None:
        """Call before a request: refuse to start once the cap is reached."""
        if self.spent >= self.cap_usd:
            raise BudgetExceeded(f"spend cap reached: ${self.spent:.2f} of ${self.cap_usd:.2f}")

    def record(self, *, model: str, input_tokens: int, output_tokens: int, price: Price, tag: str = "") -> float:
        usd = price.cost(input_tokens, output_tokens)
        entry = {"ts": round(time.time(), 3), "model": model, "in": input_tokens, "out": output_tokens,
                 "usd": round(usd, 6), "tag": tag}
        with self._lock:
            self._spent += usd
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        return usd

    def summary(self) -> dict:
        """Totals per model: calls, tokens and dollars."""
        per: dict[str, dict] = {}
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    e = json.loads(line)
                    m = per.setdefault(e["model"], {"calls": 0, "in": 0, "out": 0, "usd": 0.0})
                    m["calls"] += 0 if str(e.get("tag", "")).endswith(":cache") else 1  # a call's cache line
                    m["in"] += e["in"]
                    m["out"] += e["out"]
                    m["usd"] += e["usd"]
        return per
