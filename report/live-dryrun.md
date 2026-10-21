# Live mode dry-run (phase 1: suggest only)

21 Oct 2026. `python -m maintainer_bot review --repo Gathin23/cleanyourtv --pr N --dry-run --force` on 5 open PRs.
Nothing was written to GitHub. Rules: examples/cleanyourtv/MAINTAINER.md. Precedents: 497 past decisions.
Models: decision + critic claude-opus-5.5, second opinion glm-5.3-flash, all through the 0G router.

| PR | Kind | Bot posts | Model alone | Labels | Cost |
|---|---|---|---|---|---|
| #709 | tv-list | merge-with-fix | merge-with-fix | bot-suggests:merge-with-fix, p2, tv-list | $0.088 |
| #657 | tv-list | merge-with-fix | merge-with-fix | bot-suggests:merge-with-fix, p2, tv-list | $0.098 |
| #696 | docs | merge | merge | bot-suggests:merge, docs, p3 | $0.053 |
| #695 | launcher | hold | merge-with-fix | launcher, needs-maintainer | $0.040 |
| #706 | showcase | close | close | bot-suggests:close, docs, p3 | $0.035 |

Total $0.31, about $0.063 per PR.

Notes:
- #657: in the first dry run (head 93ed0ab) the new pairing/input hold fired (`com.tcl.autopair` disabled) and the bot posted
  "needs a maintainer decision". The author then commented the package out (head e57edc0) and the bot moved to merge-with-fix.
- #695 is launcher code, so it always goes to the maintainer; the comment shows the model's own suggestion.
- First run found a wording bug: the model wrote its note as if the PR were already merged ("Merged, thank you! … I added the row").
  Fixed with a live-only instruction (the note is a pre-decision suggestion, no "I", no @-mentions) and a guard that falls back
  to the plain reasons if the note claims an action. The comments below are from the fixed run.

## #709: docs: add Skyworth 65A3F (Chinese Coocaa) example

Labels: bot-suggests:merge-with-fix, p2, tv-list

```markdown
<!-- maintainer-bot sha=b5087ce6b98d v=1 -->
**maintainer-bot review** · suggests **merge with a small fix** (p2)

Thank you for this careful CCOS list. The write-up on why com.coocaa.aigc.home has to stay enabled, with the factory-reset recovery steps, will save people a bricked set. It looks ready apart from one small thing: the TV also needs a row in the main README TV table, to match the examples/README row.

**The small fix:** Add a skyworth-65a3f row (Skyworth 65A3F, China, Android 13 CCOS, Chinese Coocaa firmware, no GMS) to the TV table in the main README.md, matching the examples/README.md row.

<details><summary>Checks</summary>

- **OK**: new TV folder, not on main yet: `skyworth-65a3f`
- **OK**: no protected packages disabled
- **OK**: remote pairing and input left alone
- **OK**: everything it changes can be undone
- Size: size/S (+56 -0, 2 files)

</details>

This is a suggestion; a maintainer makes the final call. A maintainer can comment `/bot review` to run it again.

<sub>Reviewed by maintainer-bot · runs on [0G Private Computer](https://pc.0g.ai)</sub>
```

## #657: examples: TCL G08 EU/UK Android 12 debloat list (G08_4K_GB, AS34)

Labels: bot-suggests:merge-with-fix, p2, tv-list

```markdown
<!-- maintainer-bot sha=e57edc0ab863 v=1 -->
**maintainer-bot review** · suggests **merge with a small fix** (p2)

Thanks for this careful EU G08 list. The DO-NOT-DISABLE notes on com.tcl.suspension, interactive and ttvs, with their failure signatures, are a really useful finding. It looks ready once two small things are fixed: the main README needs a TV table row, and the package count and the setupwraith note should say the same thing everywhere.

**The small fix:** Add a row for tcl-g08-eu-android12 to the TV table in the top-level README.md, matching the examples/README row. Count the active (uncommented) lines in debloat.txt and use that number in both the debloat.txt header and the folder README (they say 25, the PR text says 26). Keep the folder README saying setupwraith and launcherx stay enabled, which matches the debloat-only scope.

<details><summary>Checks</summary>

- **OK**: new TV folder, not on main yet: `tcl-g08-eu-android12`
- **OK**: no protected packages disabled
- **OK**: remote pairing and input left alone
- **OK**: everything it changes can be undone
- Size: size/M (+95 -0, 3 files)

</details>

This is a suggestion; a maintainer makes the final call. A maintainer can comment `/bot review` to run it again.

<sub>Reviewed by maintainer-bot · runs on [0G Private Computer](https://pc.0g.ai)</sub>
```

## #696: docs: clarify automated D-pad and lifecycle checks

Labels: bot-suggests:merge, docs, p3

```markdown
<!-- maintainer-bot sha=e2027bfe85d7 v=1 -->
**maintainer-bot review** · suggests **merge** (p3)

Thanks for writing down the touch-mode, Home-readiness and trim-level pitfalls. Each one can make an automated focus or lifecycle check give the wrong answer. This sits well next to the existing long-press testing note, and it looks good to merge as it is.

<details><summary>Checks</summary>

- Size: size/S (+18 -0, 1 files)

</details>

This is a suggestion; a maintainer makes the final call. A maintainer can comment `/bot review` to run it again.

<sub>Reviewed by maintainer-bot · runs on [0G Private Computer](https://pc.0g.ai)</sub>
```

## #695: Use Indonesian greeting hours when locale is Indonesian

Labels: launcher, needs-maintainer

```markdown
<!-- maintainer-bot sha=6c8a7bddb861 v=1 -->
**maintainer-bot review** · this one needs **a maintainer decision**

Thank you for spotting that Indonesian day parts don't follow the English hours, and for keeping the fix this small. The suggestion is a tiny tweak: also accept "id" as well as "in", and read the language from the app's resources locale, so the greeting always follows the language shown on screen.

Why it goes to a maintainer: launcher PRs always go to the maintainer.
The bot's own suggestion would be: merge with a small fix.

<details><summary>Checks</summary>

- **OK**: no INTERNET permission added
- Size: size/S (+14 -5, 1 files)

</details>

This is a suggestion; a maintainer makes the final call. A maintainer can comment `/bot review` to run it again.

<sub>Reviewed by maintainer-bot · runs on [0G Private Computer](https://pc.0g.ai)</sub>
```

## #706: SHOWCASE: add XGIMI Clean — root & debloat toolkit for China-market GMUI projectors

Labels: bot-suggests:close, docs, p3

```markdown
<!-- maintainer-bot sha=b9a9f6f4d467 v=1 -->
**maintainer-bot review** · suggests **close (kindly)** (p3)

Thanks for the careful write-up, and for checking your keep-list against the xgimi examples. That's a useful cross-check. The showcase can't list this tool, though: it gets root through the vendor SSH service, uninstalls apps and blocks domains, and CleanYourTV is built on "no root, nothing uninstalled", so the suggestion is to close this one kindly. If you ever make a version that only disables packages over ADB, a list under examples/ or a new showcase row would be very welcome.

<details><summary>Checks</summary>

- Size: size/S (+1 -0, 1 files)

</details>

This is a suggestion; a maintainer makes the final call. A maintainer can comment `/bot review` to run it again.

<sub>Reviewed by maintainer-bot · runs on [0G Private Computer](https://pc.0g.ai)</sub>
```
