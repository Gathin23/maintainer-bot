"""maintainer-bot command line.

    python -m maintainer_bot dataset   --repo OWNER/NAME --git-dir PATH --out data/NAME
    python -m maintainer_bot backtest  --data data/NAME --git-dir PATH --rules MAINTAINER.md --model glm-5.3 [--sample 120]
    python -m maintainer_bot report    --data data/NAME --runs runs --out report/backtest.md
    python -m maintainer_bot queue     --results runs/MODEL/results.jsonl --prs 543,544 --model glm-5.3
    python -m maintainer_bot approve   --results runs/MODEL/results.jsonl --comment "/approve except #512"
    python -m maintainer_bot review    --repo OWNER/NAME --pr 123 [--dry-run] [--force]
    python -m maintainer_bot backfill  --repo OWNER/NAME [--dry-run]
    python -m maintainer_bot refresh   --repo OWNER/NAME --event $GITHUB_EVENT_PATH   (after CI: facts only, no model)

Phase 2 (acts only on a maintainer's /approve; see docs/phase2.md):
    python -m maintainer_bot queue-issue     --repo OWNER/NAME [--allow USERS] [--dry-run]
    python -m maintainer_bot on-comment      --repo OWNER/NAME --event $GITHUB_EVENT_PATH [--workdir .] [--counts CMD]
    python -m maintainer_bot dry-run-approve --repo OWNER/NAME [--counts-check CMD --counts-dir PATH] [--out FILE]

Live actions only run inside the GitHub Action (see action.yml); dry-run-approve never writes.
"""
from __future__ import annotations

import argparse
import json
import os

from . import apply, backtest, commands, dataset, ledger, live, queue


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
    for name in ("review", "backfill", "refresh"):
        r = sub.add_parser(name)
        r.add_argument("--repo", required=True)
        if name == "review":
            r.add_argument("--pr", type=int, required=True)
        if name == "refresh":
            r.add_argument("--event", required=True, help="the workflow_run event JSON ($GITHUB_EVENT_PATH)")
        r.add_argument("--dry-run", action="store_true", help="print the comment and labels, write nothing")
        r.add_argument("--force", action="store_true", help="review again even if this commit was reviewed")
        r.add_argument("--rules", help="local MAINTAINER.md (default: read from the repo's default branch)")
        r.add_argument("--precedents", help="local precedents.jsonl (default: read from the repo)")
        r.add_argument("--ledger", default=os.environ.get("MB_LEDGER", ".maintainer-bot/ledger.jsonl"))
        r.add_argument("--daily-cap", type=float, default=float(os.environ.get("MB_DAILY_CAP", "5")))
        r.add_argument("--per-pr-cap", type=float, default=float(os.environ.get("MB_PER_PR_CAP", "0.5")))
        r.add_argument("--model", default=os.environ.get("MB_MODEL", "claude-opus-5.5"))
        r.add_argument("--second-model", default=os.environ.get("MB_SECOND_MODEL", "glm-5.3-flash"))
        r.add_argument("--critic-model", default=os.environ.get("MB_CRITIC_MODEL", "claude-sonnet-5"))
        r.add_argument("--apk-artifact", default=os.environ.get("MB_APK_ARTIFACT", ""),
                       help="name of a CI artifact holding the launcher APK size (optional APK-size fact)")
        r.add_argument("--json", action="store_true", help="print the result as JSON")
    qi = sub.add_parser("queue-issue")
    qi.add_argument("--repo", required=True)
    qi.add_argument("--allow", default=os.environ.get("MB_ALLOW_USERS", ""))
    qi.add_argument("--dry-run", action="store_true")
    oc = sub.add_parser("on-comment")
    oc.add_argument("--repo", required=True)
    oc.add_argument("--event", required=True, help="the issue_comment event JSON ($GITHUB_EVENT_PATH)")
    oc.add_argument("--allow", default=os.environ.get("MB_ALLOW_USERS", ""))
    oc.add_argument("--workdir", default="", help="checkout used for bot/* branches (empty: API merges only)")
    oc.add_argument("--counts", default=os.environ.get("MB_COUNTS_CMD", ""), help="README counts command")
    oc.add_argument("--ledger", default=os.environ.get("MB_LEDGER", ".maintainer-bot/ledger.jsonl"))
    oc.add_argument("--daily-cap", type=float, default=float(os.environ.get("MB_DAILY_CAP", "5")))
    oc.add_argument("--model", default=os.environ.get("MB_MODEL", "claude-opus-5.5"))
    dr = sub.add_parser("dry-run-approve")
    dr.add_argument("--repo", required=True)
    dr.add_argument("--counts-check", default="")
    dr.add_argument("--counts-dir", default="")
    dr.add_argument("--out", default="")
    args = ap.parse_args(argv)

    if args.cmd in ("queue-issue", "on-comment", "dry-run-approve"):
        from .phase2 import cli as p2
        if args.cmd == "queue-issue":
            print(json.dumps(p2.queue_issue(args.repo, allow=args.allow, dry_run=args.dry_run)))
        elif args.cmd == "on-comment":
            r = p2.on_comment(args.repo, args.event, allow=args.allow, workdir=args.workdir, counts_cmd=args.counts,
                              ledger_path=args.ledger, cap=args.daily_cap, model=args.model,
                              git_name=os.environ.get("MB_GIT_NAME", ""), git_email=os.environ.get("MB_GIT_EMAIL", ""))
            print(json.dumps({k: v for k, v in r.items() if k != "audit"}, default=str))
        else:
            print(p2.dry_run_approve(args.repo, counts_check=args.counts_check, counts_dir=args.counts_dir,
                                     out=args.out))
        return

    if args.cmd in ("review", "backfill", "refresh"):
        kw = dict(rules_md=open(args.rules, encoding="utf-8").read() if args.rules else None,
                  precedents=open(args.precedents, encoding="utf-8").read() if args.precedents else None,
                  dry_run=args.dry_run, force=args.force, ledger_path=args.ledger, daily_cap=args.daily_cap,
                  per_pr_cap=args.per_pr_cap, model=args.model, critic=args.critic_model, second=args.second_model,
                  apk_artifact=args.apk_artifact)
        if args.cmd == "review":
            r = live.review(args.repo, args.pr, **kw)
            if args.json:
                print(json.dumps(r, indent=1))
            else:
                print({k: v for k, v in r.items() if k != "comment"})
                if r.get("comment"):
                    print("\n" + r["comment"])
        elif args.cmd == "refresh":
            for r in live.refresh_after_ci(args.repo, args.event, **kw):
                print(json.dumps({k: v for k, v in r.items() if k != "comment"}))
        else:
            live.backfill(args.repo, **kw)
        return
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
