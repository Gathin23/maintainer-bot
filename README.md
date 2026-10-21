# maintainer-bot

A maintainer bot for busy open-source repos. It reads every pull request, decides what should happen to it
the way **your** maintainer would, posts one daily queue, and does the work after you reply `/approve`.
It runs on [0G Private Computer](https://pc.0g.ai): one API key, many models.

Built for [CleanYourTV](https://github.com/Gathin23/cleanyourtv), which got 500+ pull requests in four days.

## How it works

```
PR opened / updated
  1. Facts (no AI)        folder and size labels, duplicate list folders, protected packages, binaries,
                          sensitive paths, strings missing in locales
  2. Decision (AI)        your rules (MAINTAINER.md) + your past decisions on similar PRs →
                          merge · merge-with-fix · rework · close · hold, priority p0–p3, reason, fix, comment
  3. Hard overrides       deterministic rules beat the model (e.g. binaries or workflow edits → hold)
Daily queue issue         grouped like a maintainer's review round
Maintainer replies        /approve · /approve except #512 · /merge #N · /close #N · /rework #N · /hold #N
  4. Do it                merge queue (one PR at a time, re-tested), small fixes, labels, kind comments
```

Nothing merges, closes or comments until a maintainer approves the queue. A PR that edits workflows, the
bot's rules or other sensitive paths always goes to the maintainer.

## Merge with a small fix, safely

| Job | Does | Model key | Repo write | Runs PR code |
|---|---|---|---|---|
| A. Fix | proposes search/replace edits (validated: unique match, ≤30 lines, no sensitive paths) | yes | no | no |
| B. Test | applies merge + edits, runs the repo's own tests | no | no | yes (like normal CI) |
| C. Merge | pushes the exact tested commit, only after `/approve` | no | yes | no |

## Prove it before you trust it

`backtest` replays your repo's real history: every merged, closed, reworked and held PR, using only what
was known at the time and only earlier decisions as memory. It reports agreement per verdict, every
"safety miss" (the bot would merge something you closed or held) and the cost.

```bash
python -m maintainer_bot dataset  --repo OWNER/NAME --git-dir ../NAME --out data/NAME
python -m maintainer_bot backtest --data data/NAME --git-dir ../NAME --rules MAINTAINER.md --model glm-5.3 --sample 120
```

The 0G key is read from `OG_PC_API_KEY` (or a key file outside the repo) and never written anywhere.
A spend ledger enforces a hard cap (`--cap`, default $25).

## Rollout

1. Backtest on your history and read the disagreements.
2. Shadow week: the bot posts its queue, you keep deciding as usual, and you compare.
3. `/approve` mode.
4. Only classes that matched you on ≥98% of 50+ cases may act on their own (for example exact duplicates
   or stale rework). Code that changes behaviour, safety rules and workflows never do.

## Wording about 0G

Every comment and queue says only "runs on 0G Private Computer", which is always accurate. The default
decision model (Claude Opus 5.5 via the 0G router) is standard-routed, so the bot never calls itself
"private", "sealed" or "TEE". If you switch to a TeeML model (for example `glm-5.3`, `0gm-1.0-35b-a3b`)
you may say "private inference" in your own posts; the footer stays the same.

## Licence

MIT
