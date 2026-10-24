# Switching phase 2 on (CleanYourTV)

Nothing below has happened yet. The code is on the local branch `phase2-launch` (unpushed). Before you start, read
`report/phase2-launch-dryrun.md`: it lists what today's `/approve` would do. Every step is one command or one click.

1. **Push the bot.** The workflows pin this commit, so it must be on GitHub first:
   `git -C ~/Arsenal/maintainer-bot push origin phase2-launch:master`
   (a fast-forward of master; keep `~/Arsenal/maintainer-bot` on `phase2-launch` until step 4 is done).
2. **Create the App.** Open `~/Arsenal/maintainer-bot/setup/create-app.html` in a browser → **Create the App on
   GitHub** → **Create GitHub App**. Copy the `code=` value from the address bar you land on, then run
   `~/Arsenal/maintainer-bot/setup/finish-app.sh CODE`
   It stores `MAINTAINER_BOT_CLIENT_ID` and `MAINTAINER_BOT_PRIVATE_KEY` as cleanyourtv secrets (the key is never
   printed or saved) and prints an install link. The code works for one hour.
3. **Install it on cleanyourtv only.** Open the printed link → **Only select repositories → cleanyourtv** → Install.
4. **Open and merge the workflow PR.** Run `~/Arsenal/maintainer-bot/setup/open-workflow-pr.sh`, then merge the PR
   it opens. It pins both workflows to the step-1 commit, adds the queue workflow, sets the review workflow's daily
   cap to $25 and creates the `maintainer-queue` and `needs-rework` labels.
   (The same commit, made from today's main, is ready to read in a local worktree: see "Prepared PR" below.)

Phase 2 is on after step 4. The first queue issue appears at 09:17 IST, or straight away from **Actions →
maintainer-bot queue → Run workflow**.

## The first wave

- Check the 0G PC balance that morning (fix calls are about $0.09 each).
- Read the queue issue, then comment on it, for example `/approve except #1353` (#1353's own CI is red, which
  would stop the wave there). Other commands: `/approve #a #b`, `/skip #n`, `/close #n reason`, `/rework #n ask`.
- The wave: only lists, docs, themes, SHOWCASE.md, README table rows and the brand line, and translations; at most
  25 PRs; it waits for main's CI before starting, every 5 merges and after the last merge, and red stops it. Then
  a job with no secrets redraws the README counts and a second job opens and merges "README counts after today's
  merges". The audit is the last comment on the queue issue.
- Launcher, add-on, tools, test and workflow PRs are listed under "For a maintainer: outside the wave's paths":
  merge those by hand as before.

## Settings (optional, Settings → Secrets and variables → Actions → Variables)

| Variable | Default | What it does |
|---|---|---|
| `MAINTAINER_BOT_DAILY_CAP` | 25 | Daily model spend cap in dollars, reviews and fixes together |
| `MAINTAINER_BOT_MAX_WAVE` | 25 | Most PRs one `/approve` acts on; the next `/approve` picks up the rest |
| `MAINTAINER_BOT_MAIN_CHECK_EVERY` | 5 | Wait for main's CI after this many merges |
| `MAINTAINER_BOT_ALLOW_USERS` | (empty) | Logins besides the owner whose commands are read |

## Undo

- Stop phase 2 at once: `gh workflow disable "maintainer-bot queue" -R Gathin23/cleanyourtv` (reviews go on).
- Undo one merge: `git revert -m 1 <merge commit>` in a PR, as for any merge.
- Remove the App: GitHub → Settings → Applications → cleanyourtv-maintainer-bot → Uninstall.

## Prepared PR

The workflow PR's content is committed in a local cleanyourtv worktree (branch `maintainer-bot-phase2`, not
pushed), made with `setup/open-workflow-pr.sh --local DIR` from origin/main. Step 4 makes the same commit again
from main as it is then, so nothing there needs pushing by hand.
