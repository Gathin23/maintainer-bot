#!/usr/bin/env bash
# Open the cleanyourtv PR that switches phase 2 on. Run it after maintainer-bot master is pushed.
# It pins both workflows to that commit, adds the queue workflow, and creates the two labels phase 2 uses.
set -euo pipefail
repo="Gathin23/cleanyourtv"
bot_dir="$(cd "$(dirname "$0")/.." && pwd)"
sha="$(git -C "$bot_dir" rev-parse HEAD)"
gh api "repos/Gathin23/maintainer-bot/commits/$sha" --jq .sha >/dev/null \
  || { echo "push maintainer-bot first: $sha is not on GitHub" >&2; exit 1; }
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
gh repo clone "$repo" "$tmp/repo" -- -q --depth 1
cd "$tmp/repo"
git checkout -q -b maintainer-bot-phase2
sed "s/PINNED_SHA/$sha/" "$bot_dir/examples/cleanyourtv/maintainer-bot-queue.yml" > .github/workflows/maintainer-bot-queue.yml
python3 - "$sha" <<'PY'
import re, sys
p = ".github/workflows/maintainer-bot.yml"
s = open(p).read()
s = re.sub(r"Gathin23/maintainer-bot@[0-9a-f]{40}", "Gathin23/maintainer-bot@" + sys.argv[1], s)
old = "(github.event_name == 'pull_request_target' && !github.event.pull_request.draft) ||"
new = ("(github.event_name == 'pull_request_target' && !github.event.pull_request.draft &&\n"
       "       !startsWith(github.event.pull_request.head.ref, 'bot/')) ||")
assert old in s, "phase-1 workflow changed; edit it by hand"
s = s.replace(old, new)
open(p, "w").write(s)
PY
gh label create maintainer-queue -R "$repo" --color 0e8a16 --description "The bot's daily queue issue" --force
gh label create needs-rework -R "$repo" --color fbca04 --description "Changes asked before merge" --force
git add .github/workflows
git commit -q -m "maintainer-bot phase 2: daily queue issue, /approve does the merges"
git push -q -u origin maintainer-bot-phase2
gh pr create -R "$repo" --head maintainer-bot-phase2 --title "maintainer-bot phase 2: /approve on the daily queue" \
  --body "Adds the daily queue issue (09:17 IST) and the /approve executor, pinned to maintainer-bot $sha. The phase-1 workflow is pinned to the same commit and no longer reviews the bot's own bot/* PRs. Needs the App secrets (MAINTAINER_BOT_CLIENT_ID, MAINTAINER_BOT_PRIVATE_KEY) or MAINTAINER_BOT_TOKEN. Design: https://github.com/Gathin23/maintainer-bot/blob/$sha/docs/phase2.md"
