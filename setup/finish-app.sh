#!/usr/bin/env bash
# Turn the one-hour code from the App manifest flow into the two repository secrets, without printing the key.
# Usage: setup/finish-app.sh CODE [OWNER/REPO]
set -euo pipefail
code="${1:?usage: finish-app.sh CODE [OWNER/REPO]}"
repo="${2:-Gathin23/cleanyourtv}"
gh api -X POST "/app-manifests/${code}/conversions" | python3 -c '
import json, subprocess, sys
repo = sys.argv[1]
app = json.load(sys.stdin)
for name, value in (("MAINTAINER_BOT_CLIENT_ID", app["client_id"]), ("MAINTAINER_BOT_PRIVATE_KEY", app["pem"])):
    subprocess.run(["gh", "secret", "set", name, "-R", repo], input=value, text=True, check=True)
print("App created:", app["html_url"])
print("Install it on", repo, "only: https://github.com/apps/%s/installations/new" % app["slug"])
' "$repo"
