#!/usr/bin/env bash
# Open the cleanyourtv PR that switches phase 2 on. Run it after this maintainer-bot commit is pushed.
# It pins both workflows to that commit, adds the queue workflow, sets the review workflow's daily cap to
# MAINTAINER_BOT_DAILY_CAP (default $25), and creates the two labels phase 2 uses.
#
#   setup/open-workflow-pr.sh                 fresh clone of cleanyourtv main, commit, push, open the PR
#   setup/open-workflow-pr.sh --local DIR     only make the commit in DIR (a cleanyourtv checkout); push nothing
set -euo pipefail
repo="Gathin23/cleanyourtv"
bot_dir="$(cd "$(dirname "$0")/.." && pwd)"
sha="$(git -C "$bot_dir" rev-parse HEAD)"
local_dir=""
[ "${1:-}" = "--local" ] && local_dir="${2:?usage: open-workflow-pr.sh --local DIR}"

if [ -n "$local_dir" ]; then
  cd "$local_dir"
  git checkout -q -B maintainer-bot-phase2
else
  gh api "repos/Gathin23/maintainer-bot/commits/$sha" --jq .sha >/dev/null \
    || { echo "push maintainer-bot first: $sha is not on GitHub" >&2; exit 1; }
  tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
  gh repo clone "$repo" "$tmp/repo" -- -q --depth 1
  cd "$tmp/repo"
  git checkout -q -b maintainer-bot-phase2
fi
sed "s/PINNED_SHA/$sha/" "$bot_dir/examples/cleanyourtv/maintainer-bot-queue.yml" > .github/workflows/maintainer-bot-queue.yml
python3 - "$sha" <<'PY'
import re, sys
p = ".github/workflows/maintainer-bot.yml"
s = open(p).read()
s = re.sub(r"Gathin23/maintainer-bot@[0-9a-f]{40}( # [^\n]*)?", "Gathin23/maintainer-bot@" + sys.argv[1]
           + " # maintainer-bot phase2-launch, pinned", s)
old = "(github.event_name == 'pull_request_target' && !github.event.pull_request.draft) ||"
new = ("(github.event_name == 'pull_request_target' && !github.event.pull_request.draft &&\n"
       "       !startsWith(github.event.pull_request.head.ref, 'bot/')) ||")
assert old in s, "phase-1 workflow changed; edit it by hand"
s = s.replace(old, new)
cap = re.compile(r'daily-cap-usd: "\d+"')
assert cap.search(s), "phase-1 workflow has no daily-cap-usd; edit it by hand"
s = cap.sub("daily-cap-usd: ${{ vars.MAINTAINER_BOT_DAILY_CAP || '25' }}", s)
open(p, "w").write(s)
PY
git add .github/workflows
git commit -q -m "maintainer-bot phase 2: daily queue issue, /approve does the merges

A wave acts only on lists, docs, themes, SHOWCASE.md, README table rows and launcher translations, at most
25 PRs, and only while main's CI is green. The README counts run in a job with no secrets. Both workflows are
pinned to maintainer-bot $sha; the daily model cap is MAINTAINER_BOT_DAILY_CAP (default \$25)."
if [ -n "$local_dir" ]; then
  echo "committed on maintainer-bot-phase2 in $local_dir (not pushed), pinned to $sha"
  exit 0
fi
gh label create maintainer-queue -R "$repo" --color 0e8a16 --description "The bot's daily queue issue" --force
gh label create needs-rework -R "$repo" --color fbca04 --description "Changes asked before merge" --force
git push -q -u origin maintainer-bot-phase2
gh pr create -R "$repo" --head maintainer-bot-phase2 --title "maintainer-bot phase 2: /approve on the daily queue" \
  --body "Adds the daily queue issue (09:17 IST) and the /approve executor, pinned to maintainer-bot $sha. A wave acts only on lists, docs, themes, SHOWCASE.md, README table rows and launcher translations (everything else stays for the owner), at most 25 PRs (MAINTAINER_BOT_MAX_WAVE), and only while main's CI is green; it re-checks main every 5 merges. The README counts run in their own job with no secrets. The phase-1 workflow is pinned to the same commit, no longer reviews the bot's own bot/* PRs, and its daily cap is MAINTAINER_BOT_DAILY_CAP (default \$25). Needs the App secrets (MAINTAINER_BOT_CLIENT_ID, MAINTAINER_BOT_PRIVATE_KEY) or MAINTAINER_BOT_TOKEN. Design: https://github.com/Gathin23/maintainer-bot/blob/$sha/docs/phase2.md"
