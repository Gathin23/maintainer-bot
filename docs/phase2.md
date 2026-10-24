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
| merge | Merge commit ("Merge PR #n: title") through the API when the PR is mergeable and its checks are green. If it no longer merges cleanly, or it still carries rows in the README tables (an older list PR; see "README tables" below), it takes the bot-branch path below without a fix. |
| merge-with-fix | The fix from the review comment becomes search/replace edits (0G router, edits only, never runs code): at most 30 changed lines, each search text unique, no edits to `.github/`, the bot's rules, the prompt's safety rules or the disable/restore scripts. Branch `bot/merge-<n>` = the PR head (+ main merged in, only if the two conflict) + the fix commit "On merge: …"; opened as a bot PR "Merge #n with fix: title" whose body says what changed; merged with a merge commit once its CI is green. The original PR is then marked merged by GitHub (its head is reachable from main); if not, it is closed with a link to the bot PR. The PR's own checks don't gate this path (they are often red for exactly what the fix repairs, like a missing README row); CI on the bot branch does. |
| rework | Kind comment with the ask, `needs-rework` label. PRs that already carry `needs-rework` are waiting for their author and are not queued again. |
| close | Kind comment with the reason, PR closed. |
| showcase | The showcase comment (thanks for something specific, the core stays small, add one row for your fork to SHOWCASE.md, a link to "Where does my idea go?"), PR closed. |
| addon | The add-on invite (resubmit under `addons/<name>/` as a module card that never touches `launcher/`), PR closed. |
| theme | The theme ask (move the look to `themes/<name>/` with a real-TV screenshot), `needs-rework` label; the PR stays open. |
| needs a maintainer | Never touched by `/approve`; only an explicit `/close #n` or `/rework #n` moves it. |

Every merged PR gets a short thank-you naming what changed on merge.

## Safety

- **The launch gate** (`maintainer_bot/phase2/gate.py`): `/approve` only acts on PRs whose every file is a TV list
  or note under `examples/`, a doc under `docs/`, a theme under `themes/`, `SHOWCASE.md`, table rows in
  `README.md`, or a launcher translation (`launcher/app/src/main/res/values-<locale>/strings.xml`, which CI lints
  and builds). Inside those folders only data files count (`.txt .md .json .png .jpg .jpeg .webp .gif`), so a
  `restore.sh` in an example folder stays out. Renames are checked on both names; a README patch the API doesn't
  show, or 300+ files, keeps the PR out. Everything else (launcher code, `addons/`, `tools/`, `PROMPT.md`,
  scripts, workflows) is listed in the queue under "For a maintainer: outside the wave's paths" without a
  checkbox; only `/close #n` or `/rework #n` moves those. The executor checks the gate again when it acts, and
  a fix's edits must stay inside it too.
- **Wave size**: one `/approve` acts on at most `max-wave` PRs (default 25; skips don't count). The rest are
  listed as over the cap, and the next `/approve` on the same issue picks them up.
- **main's CI around the wave**: the wave starts only once main's checks are green (it waits while they run, up
  to 40 minutes; red, a timeout or an unreadable state stops it before anything happens). After every
  `main-check-every` merges (default 5) and after the last merge it waits for main's CI again; red stops the wave
  and the audit says where. CleanYourTV's "README tables" check is left out: it is red from a list merge until
  the counts step regenerates the tables after the wave, by design. Every merge is a merge commit, so `git revert -m 1` undoes one PR.
- Never merges PRs labelled `needs-maintainer` or `on-hold` (or `launcher`, when the review is a v1 review that
  sent every launcher PR to the maintainer; a v2 review has passed the launcher gate), or PRs that change `.github/`,
  `.opencodereview/`, the bot's rules (`.github/maintainer/`), `tools/` (the counts step runs those scripts) or
  `PROMPT.md`, even if a command names them. An explicit
  `/close #n` or `/rework #n` from the owner still works on them (a comment, and for close, closing the PR).
  `on-hold` PRs are left out of the queue entirely.
- The head commit must be the one the bot reviewed (the sticky comment records it). If the author pushed since,
  the PR is skipped and re-reviewed instead of merged.
- Checks: every check run and status on the head must be finished and green. Pending (including a
  first-time contributor's run waiting for approval): skipped for today. Red: the batch stops at once and the
  issue says why. On the bot-branch path the gate is the bot PR's CI; red or 40 minutes without a result
  stops the batch and leaves the bot PR open.
- Conflicts on the bot-branch path are resolved by fixed rules, never by a model: `README.md` and
  `examples/README.md` take main's version (their tables, brand line and counts are regenerated after the
  batch), and so do `tools/readme_stats.py`, `docs/stats.png` and `docs/card.jpg`; in `SHOWCASE.md` a hunk
  where both sides are table rows keeps both; anything else stops that PR for a maintainer.
- Contributor code on a `bot/*` branch runs in the repo's CI the way a maintainer-approved PR run would. That is
  acceptable because only reviewed, owner-approved PRs get there, PRs touching `.github/` never do (and the App
  has no `workflows` permission, so it could not push them), and CleanYourTV's CI uses a read-only token and
  no secrets.
- Merges go through PRs only; the bot never pushes to the default branch. It writes only to `bot/*` branches.
- Spend cap: the fix model shares the review workflow's daily ledger and cap (`MAINTAINER_BOT_DAILY_CAP`, $25 for
  launch week; per-PR cap $0.50). The ledger is a per-run Actions cache, so runs that overlap don't see each
  other's spend: the per-PR cap is the hard brake. The queue itself makes no model calls.
- The bot's own `bot/*` PRs are skipped by the phase-1 review and left out of the queue.
- Full audit log on the queue issue: each action with links, skips with reasons, and the spend.

## Identity

`GITHUB_TOKEN` cannot trigger CI on the branches it pushes, so the executor uses either:
- a GitHub App (preferred): secrets `MAINTAINER_BOT_CLIENT_ID` and `MAINTAINER_BOT_PRIVATE_KEY`, token from
  `actions/create-github-app-token` (pinned); permissions contents write, pull requests write, issues write,
  checks read, commit statuses read (the CI gate reads both), metadata read; no webhook; or
- a fine-grained personal access token in `MAINTAINER_BOT_TOKEN` with the same repository permissions.

`setup/` has the App manifest, a one-click creation page (`create-app.html`), `finish-app.sh` (turns the
manifest code into the two secrets without printing the key) and `open-workflow-pr.sh` (pins the workflows to a
pushed commit and opens the PR that switches phase 2 on).

## README tables and counts (cleanyourtv)

CleanYourTV generates its TV tables (`README.md` and `examples/README.md`), the brand line and the counts from
each list's `examples/<folder>/tv.json` with `tools/gen_tables.py`, so a list PR adds only its folder.

- **On merge** (the `act` job, which runs no repo code): a PR that still carries rows in the two READMEs, a list
  PR from before the tables were generated, goes through a bot branch. `phase2/tables.py` keeps main's two
  README files and turns the PR's rows into its `tv.json`: tv, os and notes from its `examples/README.md` row,
  `readme_os` from its README row when the OS differs, the brand from a known brand the folder name starts with
  (else the TV cell's first word). A PR that edited an existing row has it applied to that folder's `tv.json`
  only if main has not changed the row since; otherwise the PR stops for a maintainer. It is a port of
  `tools/gen_tables.py --adopt`, not a call to it. README edits outside the tables also stop the PR.
- **After the batch**: the counts run the repo's own scripts, so on CleanYourTV they never share a job with a
  secret. The workflow has three jobs after a comment: `act` (App token and 0G key: API calls, git merges and
  the fix model), then `counts` (no secrets, no token, checkout without credentials: runs
  `examples/cleanyourtv/update_counts.py`, which runs the repo's `tools/gen_tables.py --font Fredoka.ttf` and
  prints a JSON summary, then uploads `counts.patch` + `counts.json`), then `counts-pr` (an App token cut down
  to contents and pull requests write, checks and statuses read; runs no repo code: refuses a patch that
  touches anything but `README.md`, `examples/README.md`, `docs/stats.png`, `docs/card.jpg` and the `STATS`
  line of `tools/readme_stats.py`, applies it to main, opens "README counts after today's merges", waits for
  its CI and merges it). The summary lists brands that are new on the brand line, so the counts PR asks for
  their spelling to be checked.

## Tests

- `tests/test_phase2.py`: command parsing, who may command, queue rendering and size limit, executor
  decisions (head moved, suggestion changed, red CI stops, pending skips, maintainer-only PRs never merged,
  `/close` on a held PR, dry run writes nothing), fix limits, conflict rules, messages.
- `tests/test_phase2_e2e.py`: a bare git repo plays GitHub (a hook rejects any push to main that isn't a
  merge) and a fake API merges for real, with a copy of CleanYourTV's `tools/gen_tables.py`. One `/approve`
  batch: 3 merges (two lists that add only their folder, one older list PR whose README rows move into its
  `tv.json` on a bot branch), 1 merge with a fix (its own CI red until the fix adds the `tv.json`), 1 rework,
  1 close, 1 held PR untouched, then the counts PR with the tables regenerated; and a second run where the bot
  branch's CI is red and the batch stops.
- `tests/test_gate.py`: the launch gate (inside and outside paths, README rows, renames, translations, fix
  edits), outside items in the queue, the wave size cap, main's CI before, during and after a wave, and the
  counts patch check.
- `python -m maintainer_bot dry-run-approve --repo OWNER/NAME [--max-wave 25]`: read-only report of what
  `/approve` would do today on the real repo, with the gate's exclusions and main's CI state.
