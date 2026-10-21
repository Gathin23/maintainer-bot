# Round M head-to-head: Claude review vs maintainer-bot (v3), 21 Oct 2026

61 open PRs on Gathin23/cleanyourtv: 47 opened since Round L and 14 older ones with new commits.
Both sides judged every PR blind. The bot ran in dry-run on the 0G router (Opus 5.5 to decide, Opus critic, GLM-5.3-flash second opinion, v3 policy); nothing it decided was written to GitHub.
Files: `.review-notes/2026-10-21c/{scope,claude,bot}.json` in the cleanyourtv worktree; raw bot output `runs/live-round-m/`.

## Numbers

| | Count |
|---|---|
| PRs in scope | 61 |
| Bot's raw model verdict agrees with Claude (same family: accept / rework / close / escalate) | 54 / 61 (89%) |
| Bot's final action agrees with Claude (after the policy routes PRs to Gathin) | 34 / 61 (56%) |
| Bot would have decided alone | 25 / 61 (41%) |
| Agreement where the bot decided alone | 22 / 25 (88%) |
| Escalated to Gathin by policy | 36: 27 launcher, 4 edits to an existing list, 3 low confidence, 1 PROMPT.md, 1 model asked |
| Merged this round (both accept, fixes compatible, tests and build green) | 21 (+1 withdrawn, see below) |
| 0G spend | $4.26 (ledger $36.07 → $40.33, cap $56) |

Raw agreement by type: TV lists 18/19, showcase 4/4, docs 7/8, tools 2/3, launcher 23/27.

The 56% headline is mostly policy, not disagreement: the bot sends every launcher PR to Gathin by design, so 27 launcher PRs count as "escalate" against Claude's merge/merge-with-fix calls even where the model's own verdict matched.

## Where the bot decided alone and disagreed (3)

| PR | Claude | Bot | Who was right |
|---|---|---|---|
| #636 Golem article + a press-count test | needs Gathin | merge | **Claude.** The Golem page sits behind a cookie wall and could not be opened to confirm it names CleanYourTV; the coverage rule is "articles we could open and check". The bot had no way to see that from the diff. |
| #678 FFalcon r34a0 (Android 5.1) | rework | merge-with-fix (add the README row) | **Claude.** The list is applied with `pm hide`, but its Undo line points at `restore.sh`, which runs `pm enable` and cannot unhide. The bot missed a broken undo path, which breaks the "one line undoes it" promise. |
| #686 Mi TV 3S 48 (Android 4.4, not Android TV) | needs Gathin | merge | **Draw.** It is a scope call: the notes are careful and `pm block` is reversible, but our scripts cannot apply or undo it. Gathin decides. |

## Where the bot was right and Claude was not

- **#657 TCL G08 EU list:** the bot's critic flagged that it disables `com.tcl.autopair` (Bluetooth remote pairing), a package every other list keeps on purpose, and #658's own header lists as do-not-disable. Claude said merge-with-fix (add a README row) and missed it. The bot routed it to Gathin; Claude's view is now **rework**: keep autopair.
- **#684 Cosy TV showcase:** a blank line before the new row split it off the SHOWCASE table. The bot caught it; Claude did not. Fixed on merge.
- **#656 Karbonn list:** the header suggested AdGuard private DNS, a global setting `restore.sh` would not undo. The bot asked to drop it; Claude missed it. Fixed on merge.
- **#633 Haier report** and **#654 TROUBLESHOOTING:** small catches (a blank line splitting a list, clearer wording). Applied on merge.

## Other differences in the model's own verdict (escalated anyway)

- **#640 Russian strings:** bot merge; Claude merge-with-fix. The PR also points `testInstrumentationRunner` at a single test class in `build.gradle`, which the bot did not flag.
- **#666 return-to-Home rework:** bot merge; Claude hold for a TV run. Both fine; it is a Home behaviour change.
- **#673 wallpaper cross-fade:** bot hold (0.60); Claude merge (opt-in).
- **#464:** bot rework; Claude hold (TV run and menu choice).
- **#482:** bot close; Claude hold (parked).
- **#525, #667, #674, #650:** bot merge-with-fix vs Claude merge. Small suggestions; same family.

Both sides agreed on the hard ones: **close #677** (weather card adds the INTERNET permission) and **#680** (INTERNET, default dock change, shots/ at the root: offer a showcase row instead), **hold** the gethari Companion series and #608 (still +150 KB), and **#648** is a duplicate of the existing Fire OS 8 karat list. The bot found #466 as the precedent; Claude found the folder.

## Verdict on the bot

Ready for a **shadow week**, not for `/approve` on its own:
- On the PRs it would decide alone, it matched 22 of 25. Its one clear miss (#678's undo path) is the kind of check that belongs in the deterministic facts: if a list header says `pm hide` or `pm block`, require an unhide or unblock undo.
- It caught three real defects Claude missed (#657, #684, #656), so the two together are better than either alone.
- **Two fixes before the shadow week:**
  1. A fact for a list that disables a remote-pairing or input package (`*autopair*`, `tcl_bt_rcu`, `inputmethod`) → hold.
  2. A fact for a non-`disable-user` apply method (`pm hide`, `pm block`) → hold unless the header gives the matching undo.

## Per-PR table

| PR | Type | Claude | Bot model (confidence) | Bot final | Same family | Result |
|---|---|---|---|---|---|---|
| #464 | launcher | hold | rework (0.78) | hold | yes |  |
| #482 | launcher | hold | close (0.80) | hold | yes |  |
| #497 | tools | needs-gathin | hold (0.55) | hold | yes |  |
| #523 | launcher | merge | merge (0.75) | hold | no |  |
| #524 | launcher | merge | merge (0.78) | hold | no |  |
| #525 | launcher | merge | merge-with-fix (0.68) | hold | no |  |
| #537 | launcher | merge | merge (0.60) | hold | no |  |
| #560 | tools | merge | merge (0.85) | hold | no |  |
| #595 | launcher | merge | merge (0.80) | hold | no |  |
| #608 | launcher | hold | hold (0.60) | hold | yes |  |
| #618 | launcher | hold | hold (0.85) | hold | yes |  |
| #623 | launcher | hold | hold (0.90) | hold | yes |  |
| #624 | launcher | hold | hold (0.90) | hold | yes |  |
| #625 | launcher | hold | hold (0.90) | hold | yes |  |
| #633 | docs | merge-with-fix | merge-with-fix (0.72) | merge-with-fix (alone) | yes | merged |
| #634 | tv-list | merge | merge (0.85) | merge (alone) | yes | merged |
| #635 | tv-list | merge | merge-with-fix (0.78) | merge-with-fix (alone) | yes | merged |
| #636 | tools | needs-gathin | merge (0.80) | merge (alone) | no |  |
| #638 | showcase | merge | merge (0.82) | merge (alone) | yes | merged |
| #639 | tv-list | merge-with-fix | merge-with-fix (0.80) | merge-with-fix (alone) | yes | merged |
| #640 | launcher | merge-with-fix | merge (0.60) | hold | no |  |
| #641 | tv-list | merge | merge (0.85) | merge (alone) | yes | merged |
| #642 | docs | merge | merge (0.80) | merge (alone) | yes | merged |
| #643 | tv-list | merge-with-fix | merge-with-fix (0.82) | merge-with-fix (alone) | yes | merged |
| #644 | launcher | merge | merge (0.78) | hold | no |  |
| #645 | docs | merge | merge (0.78) | hold | no |  |
| #648 | tv-list | rework | rework (0.55) | hold | no |  |
| #650 | docs | merge | merge-with-fix (0.62) | hold | no |  |
| #651 | tv-list | merge | merge (0.85) | merge (alone) | yes | merged |
| #652 | docs | merge | merge (0.62) | hold | no |  |
| #653 | tv-list | merge | merge-with-fix (0.80) | merge-with-fix (alone) | yes | merged |
| #654 | docs | merge | merge-with-fix (0.82) | merge-with-fix (alone) | yes | merged |
| #656 | tv-list | merge | merge-with-fix (0.72) | merge-with-fix (alone) | yes | merged |
| #657 | tv-list | merge-with-fix | merge-with-fix (0.62) | hold | no |  |
| #658 | tv-list | merge | merge (0.78) | merge (alone) | yes | merged |
| #660 | docs | merge | merge (0.85) | merge (alone) | yes | merged |
| #661 | tv-list | merge | merge (0.87) | merge (alone) | yes | merged |
| #662 | showcase | merge | merge (0.85) | merge (alone) | yes | withdrawn by author |
| #663 | tv-list | merge | merge (0.86) | hold | no |  |
| #664 | showcase | merge | merge (0.85) | merge (alone) | yes | merged |
| #665 | tv-list | merge | merge (0.90) | hold | no |  |
| #666 | launcher | hold | merge (0.70) | hold | yes |  |
| #667 | launcher | merge | merge-with-fix (0.62) | hold | no |  |
| #668 | launcher | merge | merge (0.80) | hold | no |  |
| #669 | launcher | merge | merge (0.75) | hold | no |  |
| #670 | launcher | needs-gathin | hold (0.55) | hold | yes |  |
| #671 | launcher | merge | merge (0.75) | hold | no |  |
| #672 | launcher | hold | hold (0.55) | hold | yes |  |
| #673 | launcher | merge | hold (0.60) | hold | no |  |
| #674 | launcher | merge | merge-with-fix (0.60) | hold | no |  |
| #675 | launcher | merge | merge (0.75) | hold | no |  |
| #676 | launcher | needs-gathin | hold (0.60) | hold | yes |  |
| #677 | launcher | close | close (0.90) | hold | no |  |
| #678 | tv-list | rework | merge-with-fix (0.85) | merge-with-fix (alone) | no |  |
| #679 | tv-list | merge | merge (0.88) | merge (alone) | yes | merged |
| #680 | launcher | close | close (0.82) | hold | no |  |
| #681 | tv-list | merge | merge (0.82) | merge (alone) | yes | merged |
| #682 | tv-list | merge | merge-with-fix (0.78) | merge-with-fix (alone) | yes | merged |
| #684 | showcase | merge | merge-with-fix (0.80) | merge-with-fix (alone) | yes | merged |
| #685 | tv-list | merge | merge (0.72) | merge (alone) | yes | merged |
| #686 | docs | needs-gathin | merge (0.75) | merge (alone) | no |  |
