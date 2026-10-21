"""maintainer-bot command line.

    python -m maintainer_bot dataset   --repo OWNER/NAME --git-dir PATH --out data/NAME
    python -m maintainer_bot backtest  --data data/NAME --git-dir PATH --rules MAINTAINER.md --model glm-5.3 [--sample 120]
    python -m maintainer_bot report    --data data/NAME --runs runs --out report/backtest.md
    python -m maintainer_bot queue     --results runs/MODEL/results.jsonl --prs 543,544 --model glm-5.3
    python -m maintainer_bot approve   --results runs/MODEL/results.jsonl --comment "/approve except #512"

Everything here is read-only against GitHub. Live actions only run inside the GitHub Action (see action.yml).
"""
from __future__ import annotations

import argparse
import json

from . import apply, backtest, commands, dataset, ledger, queue


def _results(path: str) -> dict[int, dict]:
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                e = json.loads(line)
                if "verdict" in e:
                    out[e["pr"]] = e
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="maintainer-bot")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dataset")
    d.add_argument("--repo", required=True)
    d.add_argument("--git-dir", required=True)
    d.add_argument("--out", required=True)
    b = sub.add_parser("backtest")
    b.add_argument("--data", required=True)
    b.add_argument("--git-dir", required=True)
    b.add_argument("--rules", required=True)
    b.add_argument("--model", required=True)
    b.add_argument("--sample", type=int, default=0)
    b.add_argument("--cap", type=float, default=25.0)
    b.add_argument("--workers", type=int, default=6)
    q = sub.add_parser("queue")
    q.add_argument("--results", required=True)
    q.add_argument("--prs", default="")
    q.add_argument("--model", required=True)
    a = sub.add_parser("approve")
    a.add_argument("--results", required=True)
    a.add_argument("--prs", default="")
    a.add_argument("--comment", required=True)
    args = ap.parse_args(argv)

    if args.cmd == "dataset":
        rows = dataset.build(args.repo, args.git_dir, args.out)
        print(f"{len(rows)} decided PRs written to {args.out}")
    elif args.cmd == "backtest":
        rows = backtest.prepare(args.data, args.git_dir)
        if args.sample:
            rows = backtest.stratified_sample(rows, args.sample)
        L = ledger.Ledger("runs/ledger.jsonl", args.cap)
        res = backtest.run(rows, data_dir=args.data, run_dir=f"runs/{args.model}", model=args.model,
                           rules_md=open(args.rules, encoding="utf-8").read(), ledger=L, workers=args.workers)
        m = backtest.metrics(res)
        print(json.dumps({k: v for k, v in m.items() if k != "safety_misses"}, indent=1), f"\nspent ${L.spent:.2f}")
    elif args.cmd in ("queue", "approve"):
        res = _results(args.results)
        if args.prs:
            keep = {int(x) for x in args.prs.split(",") if x.strip()}
            res = {k: v for k, v in res.items() if k in keep}
        if args.cmd == "queue":
            print(queue.render(list(res.values()), model=args.model))
        else:
            approval = commands.parse(args.comment)
            if not approval:
                print("no command found")
                return
            selected = approval.selected({k: v["verdict"] for k, v in res.items()})
            print(apply.dry_run(apply.plan(selected, res)))


if __name__ == "__main__":
    main()
