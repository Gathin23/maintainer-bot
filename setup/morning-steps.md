# Switching phase 2 on (CleanYourTV)

Nothing below has happened yet: phase 2 is committed locally only.

1. Read `report/phase2-dryrun.md`. If it looks right, push maintainer-bot:
   `git -C ~/Arsenal/maintainer-bot push origin master`
2. Open `setup/create-app.html` in a browser → **Create the App on GitHub** → **Create GitHub App**. Copy the
   `code=` value from the address bar you land on and run `~/Arsenal/maintainer-bot/setup/finish-app.sh CODE`.
   It stores `MAINTAINER_BOT_CLIENT_ID` and `MAINTAINER_BOT_PRIVATE_KEY` as cleanyourtv secrets (the key is never
   printed or saved) and prints the install link.
3. Open that link → **Only select repositories → cleanyourtv** → Install.
4. Run `~/Arsenal/maintainer-bot/setup/open-workflow-pr.sh`, then merge the PR it opens. It pins both
   workflows to the pushed commit, adds the queue workflow and creates the `maintainer-queue` label.

The first queue issue appears at 09:17 IST, or straight away from Actions → maintainer-bot queue → Run workflow.
Then comment `/approve` on it (or `/approve except #a`, `/skip #n`, `/close #n reason`, `/rework #n ask`).
