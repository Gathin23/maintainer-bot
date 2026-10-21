# maintainer-bot

A review bot for busy open-source repos. Every pull request gets one short comment that says what should
happen to it (merge, merge with a small fix, a few changes first, close, or a maintainer decision), why,
and which checks it ran, judged the way **your** maintainer judges: from your written rules and your own
past decisions on similar PRs. It runs on [0G Private Computer](https://pc.0g.ai): one API key, many models.

Built for [CleanYourTV](https://github.com/Gathin23/cleanyourtv), which got 500+ pull requests in its first
four days.

**Phase 1 only suggests.** It writes one comment and a few labels. It never merges, closes, approves, pushes
or requests changes. **Phase 2** (below) acts, but only on a maintainer's `/approve` on the daily queue issue.

## What a PR gets

- One sticky comment, edited in place when new commits arrive:
  - the suggestion and priority (p0–p3), and one line on why, in a kind, human tone
  - the exact small fix, or the one thing to change
  - the deterministic checks it ran (duplicate folder, protected packages, remote pairing and input
    packages, undo coverage, binaries, network permission, strings per locale, size)
  - "Reviewed by maintainer-bot · runs on 0G Private Computer"
- Labels from a fixed list only: `bot-suggests:merge`, `bot-suggests:merge-with-fix`,
  `bot-suggests:rework`, `bot-suggests:close`, `needs-maintainer`, `p0`–`p3`, and the repo's type labels.
  It removes only labels it owns.

## How it decides

```
1. Facts (no AI)        folders, size, duplicate list folders, competing open PRs, protected packages,
                        remote-pairing/input packages, pm hide without an undo, binaries, INTERNET
                        permission, strings missing in locales, maintainer-only paths
2. Decision (AI)        your rules (MAINTAINER.md) + a checklist for this kind of PR + your past decisions
                        on the most similar PRs, with the reasons you gave
3. Critic (AI)          for every merge: "what is the strongest rule-backed reason NOT to merge?"
4. Second opinion (AI)  a cheaper model; if it disagrees, the PR goes to the maintainer
5. Hard rules           deterministic rules always win and can only make a verdict more cautious
```

Some kinds of PR always go to the maintainer, whatever the model thinks: launcher/app code, CI and
workflows, and anything that edits the bot's own rules.

Backtested on CleanYourTV's real history (train on older rounds, test on newer ones): when the bot decides
on its own it agrees with the maintainer 96% of the time, and it decides alone on about 40% of PRs
(TV lists, docs, showcase entries); everything else is escalated. In a blind head-to-head on 61 new PRs it
caught three problems the human-style review missed.

## Install on your repo

1. Get a key at [pc.0g.ai](https://pc.0g.ai) and add it as a repository secret named `OG_PC_API_KEY`.
2. Add your rules as `.github/maintainer/MAINTAINER.md` (what you merge, what you never take, how you
   word comments). Optional: `.github/maintainer/precedents.jsonl`, your past decisions
   (`scripts/export_precedents.py` builds it from a backtest dataset).
3. Add the workflow (copy [`examples/cleanyourtv/maintainer-bot.yml`](examples/cleanyourtv/maintainer-bot.yml)
   to `.github/workflows/` and pin the action to a commit SHA).
4. Create the labels once:

```bash
for l in bot-suggests:merge bot-suggests:merge-with-fix bot-suggests:rework bot-suggests:close needs-maintainer p0 p1 p2 p3; do
  gh label create "$l" -R OWNER/NAME --force
done
```

It then reviews each PR when it is opened, updated or marked ready. A maintainer can comment `/bot review`
to run it again, and `workflow_dispatch` reviews every open PR, oldest first (a backfill).

## Safety model

- The workflow uses `pull_request_target` so it can comment on PRs from forks. It therefore **never checks
  out or runs the PR's code**: the PR is read through the API as data (title, body, file list, patches).
- Rules and precedents come from your default branch, never from the PR, so a PR cannot rewrite them.
- The PR text is untrusted: the model is told to ignore instructions inside it, it can only pick from fixed
  verdicts and labels, its text is cleaned before posting (no HTML, no @-pings, length-capped), and the
  deterministic rules override it.
- PRs touching `.github/` or `.opencodereview/` are not reviewed at all; they get a "needs a maintainer" note.
- The 0G key lives only in the repository secret and the job's environment; it is never written to disk or
  logged.

## Cost

About $0.05–0.10 per review with the defaults (decision and critic on `claude-opus-5.5`, second opinion on
`glm-5.3-flash`, both through the 0G router). Caps:

- `per-pr-cap-usd` (default $0.50): the most one review may spend
- `daily-cap-usd` (default $5): reviewing stops for the day once reached; the ledger is kept in the Actions
  cache, so the cap holds across runs (concurrent runs can overshoot it by a review or two)
- a commit that was already reviewed is skipped unless a maintainer asks again

## Run it locally

```bash
export OG_PC_API_KEY=...   # or a key file outside the repo, see maintainer_bot/router.py
python -m maintainer_bot review --repo OWNER/NAME --pr 123 --dry-run      # prints the comment and labels
python -m maintainer_bot backfill --repo OWNER/NAME --dry-run
python -m unittest discover -s tests
```

## Prove it before you trust it

`backtest` replays your repo's real history: every merged, closed, reworked and held PR, using only what
was known at the time and only earlier decisions as memory. It reports agreement per verdict, every case
where the bot would have merged something you closed or held, and the cost.

```bash
python -m maintainer_bot dataset  --repo OWNER/NAME --git-dir ../NAME --out data/NAME
python -m maintainer_bot backtest --data data/NAME --git-dir ../NAME --rules MAINTAINER.md --model glm-5.3 --sample 120
```

## Phase 2: `/approve` and the bot does the maintainer work

Built and tested, switched on per repo by adding a second workflow
([`examples/cleanyourtv/maintainer-bot-queue.yml`](examples/cleanyourtv/maintainer-bot-queue.yml)).
Full design: [docs/phase2.md](docs/phase2.md).

- Every morning one issue, **Today's queue YYYY-MM-DD**, built from the phase-1 reviews with no model calls:
  a checkbox per PR, grouped as merge, merge with a small fix (and the fix), a few changes first (and the ask),
  close (and why), and a list of PRs that need a maintainer (and the question).
- The repo owner (or someone on the allow-list) comments `/approve`, `/approve except #a #b`, `/approve #a #b`,
  `/skip #n`, `/close #n reason` or `/rework #n ask`. Anything else is kept as a note; nobody else is read.
- The bot then works through the batch one PR at a time: merge commits through the API; small fixes on a
  `bot/merge-<n>` branch (PR head + an "On merge: …" commit) that goes through CI as its own PR before merging,
  so the original PR shows as merged; rework comments with the `needs-rework` label; kind closes; a thank-you
  on every merged PR naming what changed on merge; and one "README counts after today's merges" PR at the end.
- It checks again at the moment of acting: the head commit must be the reviewed one, checks must be green
  (a red one stops the batch), and PRs labelled `needs-maintainer`, `launcher` or `on-hold`, or touching
  `.github/` or the bot's rules, are never merged. It never pushes to the default branch.
- Identity: a GitHub App (or a fine-grained token), because the workflow's own token cannot start CI on the
  bot's branches. `setup/create-app.html` creates the App in one click.

```bash
python -m maintainer_bot dry-run-approve --repo OWNER/NAME --out report/dryrun.md   # read-only: what /approve would do today
```

## Wording about 0G

Every comment says only "runs on 0G Private Computer", which is always accurate. The default decision model
is standard-routed on 0G PC, so the bot never calls itself "private", "sealed" or "TEE".

## Licence

MIT
