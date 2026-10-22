# Phase 2: `/approve` and the bot does the maintainer work

Phase 1 reviews every PR and suggests a verdict. Phase 2 lets the maintainer approve those suggestions in one
comment, and the bot then does the work a human maintainer would: merges (with small fixes folded in), thank-you
comments, rework asks, kind closes, and the README counts after the batch. Nothing happens without an
approval from an allowed maintainer.

## The loop

```
09:17 IST (schedule)          the bot opens/updates ONE issue "Today's queue YYYY-MM-DD"
                              (built from the phase-1 sticky comments and labels, no model calls)
maintainer comments           /approve            everything except "needs a maintainer"
                              /approve except #a #b
                              /approve #a #b      only these
                              /skip #n            leave this one today
                              /close #n reason    close with this reason (overrides the verdict)
                              /rework #n ask      ask for changes with this text (overrides the verdict)
                              anything else       kept as a note for the next run, never an action
executor (one at a time)      acts PR by PR, ticks the checkbox, appends an audit log to the issue
after the batch               one bot PR "README counts after today's merges" (only if something changed)
```

## Who may command it

Only comments whose `author_association` is `OWNER`, or whose author is in the `allowed-users` input, are read.
Everyone else is ignored silently (no reply, so nobody can make the bot talk). Comments on any other issue are
ignored: the issue must carry the `maintainer-queue` label and have been opened by the bot.

## What the executor does per PR

| Verdict | Action |
|---|---|
| merge | Merge commit ("Merge PR #n: title") through the API when the PR is mergeable and its checks are green. If it no longer merges cleanly (another PR in the batch added a neighbouring table row), it takes the bot-branch path below without a fix. |
| merge-with-fix | The fix from the review comment becomes search/replace edits (0G router, edits only, never runs code): at most 30 changed lines, each search text unique, no edits to `.github/`, the bot's rules, the prompt's safety rules or the disable/restore scripts. Branch `bot/merge-<n>` = the PR head (+ main merged in, only if the two conflict) + the fix commit "On merge: …"; opened as a bot PR "Merge #n with fix: title" whose body says what changed; merged with a merge commit once its CI is green. The original PR is then marked merged by GitHub (its head is reachable from main); if not, it is closed with a link to the bot PR. The PR's own checks don't gate this path (they are often red for exactly what the fix repairs, like a missing README row); CI on the bot branch does. |
| rework | Kind comment with the ask, `needs-rework` label. PRs that already carry `needs-rework` are waiting for their author and are not queued again. |
| close | Kind comment with the reason, PR closed. |
| showcase | The showcase comment (thanks for something specific, the core stays small, add one row for your fork to SHOWCASE.md, a link to "Where does my idea go?"), PR closed. |
| addon | The add-on invite (resubmit under `addons/<name>/` as a module card that never touches `launcher/`), PR closed. |
| theme | The theme ask (move the look to `themes/<name>/` with a real-TV screenshot), `needs-rework` label; the PR stays open. |
| needs a maintainer | Never touched by `/approve`; only an explicit `/close #n` or `/rework #n` moves it. |

Every merged PR gets a short thank-you naming what changed on merge.

## Safety

- Never merges PRs labelled `needs-maintainer` or `on-hold` (or `launcher`, when the review is a v1 review that
  sent every launcher PR to the maintainer; a v2 review has passed the launcher gate), or PRs that change `.github/`,
  `.opencodereview/` or the bot's rules (`.github/maintainer/`), even if a command names them. An explicit
  `/close #n` or `/rework #n` from the owner still works on them (a comment, and for close, closing the PR).
  `on-hold` PRs are left out of the queue entirely.
- The head commit must be the one the bot reviewed (the sticky comment records it). If the author pushed since,
  the PR is skipped and re-reviewed instead of merged.
- Checks: every check run and status on the head must be finished and green. Pending (including a
  first-time contributor's run waiting for approval): skipped for today. Red: the batch stops at once and the
  issue says why. On the bot-branch path the gate is the bot PR's CI; red or 40 minutes without a result
  stops the batch and leaves the bot PR open.
- Conflicts on the bot-branch path are resolved by fixed rules, never by a model: a hunk where both sides are
  markdown table rows keeps both; the lines the counts step regenerates (card alt text, brand line, languages
  row, `tools/readme_stats.py`, `docs/stats.png`, `docs/card.jpg`) take main's version; anything else stops
  that PR for a maintainer.
- Contributor code on a `bot/*` branch runs in the repo's CI the way a maintainer-approved PR run would. That is
  acceptable because only reviewed, owner-approved PRs get there, PRs touching `.github/` never do (and the App
  has no `workflows` permission, so it could not push them), and CleanYourTV's CI uses a read-only token and
  no secrets.
- Merges go through PRs only; the bot never pushes to the default branch. It writes only to `bot/*` branches.
- Spend cap for the fix model (daily ledger, as in phase 1). The queue itself makes no model calls.
- The bot's own `bot/*` PRs are skipped by the phase-1 review and left out of the queue.
- Full audit log on the queue issue: each action with links, skips with reasons, and the spend.

## Identity

`GITHUB_TOKEN` cannot trigger CI on the branches it pushes, so the executor uses either:
- a GitHub App (preferred): secrets `MAINTAINER_BOT_CLIENT_ID` and `MAINTAINER_BOT_PRIVATE_KEY`, token from
  `actions/create-github-app-token` (pinned); permissions contents write, pull requests write, issues write,
  checks read, metadata read; no webhook; or
- a fine-grained personal access token in `MAINTAINER_BOT_TOKEN` with the same repository permissions.

`setup/` has the App manifest, a one-click creation page (`create-app.html`), `finish-app.sh` (turns the
manifest code into the two secrets without printing the key) and `open-workflow-pr.sh` (pins the workflows to a
pushed commit and opens the PR that switches phase 2 on).

## README counts (cleanyourtv)

`examples/cleanyourtv/update_counts.py` runs on a fresh checkout of main after the batch. It counts TV models
(folders in `examples/`), brands (folder prefix mapped to the names already on the README brand line) and
languages (`values-*/strings.xml` + English), and rewrites the card alt text, the brand line (only when a count
or brand changed), the languages row and `tools/readme_stats.py`, then redraws `docs/stats.png` and
`docs/card.jpg` with the repo's own tools and Fredoka (checksum-pinned). On today's main it reproduces every
number, the brand line and both images exactly. A folder whose brand is not on the line yet takes the first word
of its TV cell in `examples/README.md`; the counts PR lists such new brands so the spelling can be checked.

## Tests

- `tests/test_phase2.py`: command parsing, who may command, queue rendering and size limit, executor
  decisions (head moved, suggestion changed, red CI stops, pending skips, maintainer-only PRs never merged,
  `/close` on a held PR, dry run writes nothing), fix limits, conflict rules, messages.
- `tests/test_phase2_e2e.py`: a bare git repo plays GitHub (a hook rejects any push to main that isn't a
  merge) and a fake API merges for real. One `/approve` batch: 3 merges (one through a bot branch after a table
  conflict), 1 merge with a fix (its own CI red until the fix), 1 rework, 1 close, 1 held PR untouched, then the
  counts PR; and a second run where the bot branch's CI is red and the batch stops.
- `python -m maintainer_bot dry-run-approve --repo OWNER/NAME`: read-only report of what `/approve` would do
  today on the real repo.
