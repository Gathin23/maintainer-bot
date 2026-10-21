# Phase 2 dry run: what `/approve` would do on Gathin23/cleanyourtv

Built 2026-10-21 23:01 IST from the live labels and sticky reviews. Read-only: no comment, label, merge or push was made.

- Open non-draft PRs: 139; with a review at their latest commit: 74; new commits since the review: 0; not reviewed yet: 48
- Queue by suggestion: close 1, hold 61, merge 9, merge-with-fix 3
- `/approve` would act on: 13 PRs (12 would go ahead, 1 skipped)

- README counts on main now: {"tv_models": 174, "brands": 53, "languages": 24, "new_brands": [], "gone_brands": []}

## Would do (12)

- #472 **close** Showcase TV-local Home and startup companion for rooted LG webOS: comment and close: Thanks for the careful write-up and for keeping the webOS companion in its own repo, with an opt-in installer, a device 
- #437 **merge** tools: a benchmark for the launcher key latency, jank and idle cost: merge commit through the API
- #699 **merge** docs: document C71KW-200 carrier-update caveat and launcher verification: merge commit through the API
- #703 **merge** docs(examples): add Skyworth / Coocaa 8R40_K5C (China, Android 8.0) debloat list: merge commit through the API
- #720 **merge** README in Vietnamese: merge commit through the API
- #721 **merge** SHOWCASE: add a fork with a live background and theme sounds (TCL 55C728): merge commit through the API
- #723 **merge** docs: add Fire OS 7 fast Home fork to the showcase: merge commit through the API
- #727 **merge** Add TCL 50C725K (BeyondTV4, Android TV 11) debloat list: merge commit through the API
- #728 **merge** examples: Anker Nebula D2426 projector (Android TV 14): merge commit through the API
- #732 **merge** examples: OK. AI PONT (Changhong ikebukuro, Android TV 11): merge commit through the API
- #338 **merge-with-fix** SHOWCASE: add cleanyourtv for Haier: would build bot/merge-338 with the fix: In the new SHOWCASE.md row, change the 'Built on' cell to: "Haier Android TV / Google TV (MediaTek, 
- #709 **merge-with-fix** docs: add Skyworth 65A3F (Chinese Coocaa) example: would build bot/merge-709 with the fix: Add a skyworth-65a3f row (Skyworth 65A3F, China, Android 13 CCOS, no GMS) to the TV table in the roo

## Would skip (1)

- #733 **merge-with-fix** examples: Skyworth SWTV-24AE-4K NF (Google TV 14, eleonas / MediaTek mt5896): new commits since the review; the bot re-reviews on push

## The queue issue body it would post

````markdown
**Today's queue · 2026-10-21** · 74 PRs with a review at their latest commit, 13 with a proposed action.

Comment here to act (only the repo owner and the allow-list are read):
`/approve` everything with a checkbox · `/approve except #a #b` · `/approve #a #b` only those · `/skip #n` · `/close #n reason` · `/rework #n ask`. Anything else is kept as a note, never an action.

### Merge (9)
- [ ] #437 tools: a benchmark for the launcher key latency, jank and idle cost (by eddysangalli) · p2 · Thanks for this benchmark, and for writing down the hard parts: matching frames by when they finish, ignoring keys that move nothing, and keeping the accessibility list intact after force-stop. It…
- [ ] #699 docs: document C71KW-200 carrier-update caveat and launcher verification (by SaviorOneZero) · p2 · Thanks for writing up the Osprey. The carrier update taking back Home, with the two updater/installer packages named and the firmware-update tradeoff spelled out, is a useful caveat for the next…
- [ ] #703 docs(examples): add Skyworth / Coocaa 8R40_K5C (China, Android 8.0) debloat list and… (by joselynrianaaa) · p2 · Thanks for turning the #692 report into a careful list and guide, especially the About-page/ADB trap and the Activity Launcher escape hatch. It's in scope and matches the owner's reboot-checked run,…
- [ ] #727 Add TCL 50C725K (BeyondTV4, Android TV 11) debloat list (by victorNavas) · p2 · Thanks for the careful header, especially the full 'never disable' set and the RAM note on katniss. This model gets its own folder, like the 55C725 and 65C725 lists from the same family, and both…
- [ ] #728 examples: Anker Nebula D2426 projector (Android TV 14) (by sedir) · p2 · Thanks for a really careful projector list. The do-not-disable section found with dumpsys and the note on the two packages the firmware turns back on at every boot will help the next Nebula owner.…
- [ ] #732 examples: OK. AI PONT (Changhong ikebukuro, Android TV 11) (by ehystiv) · p2 · Thanks for the careful OK. AI PONT list, especially the HOME and setupwraith check and the note on the dmt.upgrade crash. This one looks ready to merge: it's a new model with both README rows,…
- [ ] #720 README in Vietnamese (by nahtheking) · p3 · Thanks for the Vietnamese README. It follows the Chinese guide closely, the badge and language line are tidy, and the short "TVs sold in Vietnam" section is a nice touch. This looks ready to go in…
- [ ] #721 SHOWCASE: add a fork with a live background and theme sounds (TCL 55C728) (by csermet) · p3 · Thanks for sharing the fork! The theme sounds that wait for the ARC soundbar, and the FORK.md explaining how to push videos and sounds, are nice touches. The row is in the same format as the others,…
- [ ] #723 docs: add Fire OS 7 fast Home fork to the showcase (by andrewsaad) · p3 · Thanks for sharing this. Getting past the 5 s background-start delay on Fire OS 7 by clicking the launcher's own tile in Amazon's apps row is a clever trick, and it fills the gap between the Fire OS…

### Merge with a small fix (3)
- [ ] #709 docs: add Skyworth 65A3F (Chinese Coocaa) example (by wenyuwen2011) · p2 · fix: Add a skyworth-65a3f row (Skyworth 65A3F, China, Android 13 CCOS, no GMS) to the TV table in the root README.md, matching the examples/README.md entry.
- [ ] #733 examples: Skyworth SWTV-24AE-4K NF (Google TV 14, eleonas / MediaTek mt5896) (by MazubaM) · p2 · fix: Add a `skyworth-swtv-24ae-4k-nf/` row to the TV table in the root README.md, next to the skyworth-swtv-24na-4k-nf row and matching the examples/README entry.
- [ ] #338 SHOWCASE: add cleanyourtv for Haier (by abuhasanrumi) · p3 · fix: In the new SHOWCASE.md row, change the 'Built on' cell to: "Haier Android TV / Google TV (MediaTek, CVTE); not yet run on a TV"

### Close (kindly) (1)
- [ ] #472 Showcase TV-local Home and startup companion for rooted LG webOS (by Amoulier) · p3 · why: Thanks for the careful write-up and for keeping the webOS companion in its own repo, with an opt-in installer, a device report and honest limits. Because it needs a rooted TV, it doesn't fit the…

### Needs a maintainer (61)
_Not part of `/approve`; only `/close #n` or `/rework #n` moves these._
- #39 Launcher: faster Home, cache app tiles off the main thread (by leovvay) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: a few changes first
- #146 launcher: run on Android 5.1 (minSdk 22) and Xiaomi China firmware (by terryli-94) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: a few changes first
- #150 Perf: skip the rebuild on return to Home, trim memory, less overdraw (by ptrinh) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: close (kindly)
- #174 Gallery: family photos and videos from Pictures/Launcher as the Home background (by ptrinh) · question: launcher PRs always go to the maintainer
- #175 Hold OK on the network pill: read-only IP, ADB and Wireless debugging port (by ptrinh) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: a few changes first
- #228 Renamed TV 4A as general model TV MOOQ1 and included extra packages similar to MOOQ0.… (by juliovegap) · question: confidence 0.60 < 0.65. The bot's own suggestion would be: a few changes first
- #244 launcher: InputKeyService handles KEYCODE_MEDIA_RECORD / TV_INPUT remotes (by silpdev) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: a few changes first
- #257 Greeting intro: typed out large when the TV comes on, then glides into its corner (by ptrinh) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: a few changes first
- #268 Xiaomi MiTV-AXSO0 debloat, launcher features, and one-file TV Setup APK (by rakshajag13) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: close (kindly)
- #308 Phone control: change the launcher's layout settings from a phone on the home network… (by ptrinh) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: close (kindly)
- #309 Screen time: a Report pill opens 24 hour and 7 day screen time per app (opt-in) (by ptrinh) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: merge with a small fix
- #310 Compact Home (compact_ui): short header, icon pills, see-through dock, magnified tiles,… (by ptrinh) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: a few changes first
- #326 Nokia Streaming Box 8000 list; launcher: Home redirect, hide the network pill, no-bounce… (by UavL) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: a few changes first
- #327 Launcher: hold OK on a tile for Move / App info; Background in Launcher settings (by UavL) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: a few changes first
- #378 Launcher: optional parental PIN for protected apps (by LuizPT) · question: launcher PRs always go to the maintainer
- #383 On-TV theme reader: show and reset the pushed theme (by PatrickNoFilter) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: a few changes first
- #389 Optional night picture for themes (wallpaper_night.jpg, night_from/ni… (by andikatuluspangestu) · question: launcher PRs always go to the maintainer
- #401 launcher: input_action_map for TVs that switch inputs with an action + integer extra (by ForeverSkys) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: merge with a small fix
- #407 launcher: Fire OS routes standard settings intents to a CTS stub; fall back to… (by delta-whiplash) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: merge
- #448 launcher: dynamic apps-per-row grid setting, remote settings key inte… (by MandipKumarKanu) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: a few changes first
- #450 themes: a screenshot in every theme folder, required for new themes (by maxhayim)
- #451 examples: TCL 60C635 (Google TV 11, Realtek rtd288o), tested on a real unit (by ComeCaramelos) · question: edits an existing TV list: the maintainer decides. The bot's own suggestion would be: merge
- #452 Add .gitattributes and .editorconfig (by ComeCaramelos) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: merge
- #456 Add an on-TV picker for the remote TV button (by lionlev21) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: a few changes first
- #457 Show free/total capacity and fix Hebrew stats alignment (by lionlev21) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: a few changes first
- #458 Add opt-in Shizuku access for system CPU stats (by lionlev21) · question: launcher PRs always go to the maintainer
- #467 Support Amazon Fire TV (Fire OS): debloat list, Home redirect, Fire mode install (by GaneshVarma1) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: a few changes first
- #473 Launcher: inputs as Home tiles (home_inputs) (by owine) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: merge
- #479 launcher: stock_home_redirect, for firmware that turns the stock launcher back on (XGIMI) (by TeaTax16) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: merge
- #484 Theme: ruska, a Finnish autumn dusk drawn in code (by priku) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: merge
- #487 feat(launcher): remote wallpaper, dock glass, and TV Settings (by PedroAlvesUSE) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: close (kindly)
- #488 Launcher: hold OK to reorder, Italian, settings applied on Home; examples: TCL 43P7K (by AngelusGi) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: a few changes first
- #496 launcher: boot_to_live_tv, open Live TV on the first Home after boot (by alessandrodauria) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: merge
- #497 tools: an audit for voice, ACR and telemetry, with the evidence (#444) (by xbsheng) · question: model asked for the maintainer
- #505 Launcher: an app moved into the dock on the TV stays there with fill_dock false (by johnossawy) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: merge
- #510 launcher: show_stats memory segment as used/total instead of free-only (by hikiasi) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: merge with a small fix
- #511 Launcher: banners for Xiaomi TV system apps (by fants) · question: launcher PRs always go to the maintainer
- #518 Adds a debloat list for the Philips Google TV TA7 (by wesley-prado) · question: confidence 0.55 < 0.65. The bot's own suggestion would be: a few changes first
- #522 Add on-TV toggle for system stats (by PatrickNoFilter) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: a few changes first
- #523 launcher: reduced_motion settles in 5 frames, nothing over 90 ms (by Samreay) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: merge
- #524 launcher: glow_style horizon, the app's colour washing down from the top (by Samreay) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: merge
- #525 launcher: each top-bar pill shows its icon, its label or both, with a label width (by Samreay) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: merge
- #526 build-and-install: grant TCL's AUTO_START app-op and rebind a listed key service (by Samreay) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: merge
- #527 Launcher: theme palette keys (accent, text, dock band, glow) and five palette themes (by seixando) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: merge
- #534 launcher: allow selecting an exact Live TV tuner (by midhatn) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: merge
- #535 Launcher: optionally hide inactive HDMI ports and refresh the open Inputs menu (by midhatn) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: a few changes first
- #537 Skyworth 7S60_A5 on Coocaa OS (China market): debloat list and Inputs support (by VincentYe123) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: merge
- #558 launcher: app_glow, the focus highlight in the focused app's colour on every tile (opt-in) (by cristianrojas07) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: merge
- #560 tools/tv.py --screenshot: press remote keys first, and tell a failed capture from an… (by Samreay) · question: touches maintainer-only paths: PROMPT.md. The bot's own suggestion would be: merge
- #566 Check PowerShell transport failures and recover failed Home handovers (by am-tmac) · question: launcher PRs always go to the maintainer
- #572 Add Hisense 65U68QF Fire TV (Fire OS 8) debloat list (by Solankimimoh) · question: confidence 0.60 < 0.65. The bot's own suggestion would be: merge
- #593 tcl-qm6k-google-tv: config.json with the gear and YouTube keys (by jerinjoy) · question: edits an existing TV list: the maintainer decides. The bot's own suggestion would be: merge with a small fix
- #595 Launcher: focus_overshoot, highlight and tile zoom without the bounce (from #326) (by priku) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: merge
- #708 launcher: quick settings panel along the right edge, as Google TV's (by cristianrojas07) · question: launcher PRs always go to the maintainer
- #719 launcher: long-press remote buttons to open a second app (by nikhiltalreja) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: merge
- #722 Inputs: map HW inputs to vendor source numbers (Xiaomi China tvplayer) (by Miradil-paridin) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: merge with a small fix
- #724 launcher: dock_rows option for 1 or 2 rows in the dock capsule (opt-in) (by esherk) · question: launcher PRs always go to the maintainer
- #725 launcher: Spanish date on two lines on Home (by oscarolbe) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: merge
- #726 Xiaomi MiTV-MOOR2: remote keys once launcherx is off, and theme.sh leaving the key… (by raafaelima) · question: edits an existing TV list: the maintainer decides. The bot's own suggestion would be: merge
- #730 launcher: answer VIEW_INPUTS with the Inputs menu (by johnbenwoo) · question: launcher PRs always go to the maintainer. The bot's own suggestion would be: a few changes first
- #731 examples: Hisense 75" U9DG (huangshan, Android TV 10), USA (by johnbenwoo) · question: confidence 0.60 < 0.65. The bot's own suggestion would be: a few changes first

<details><summary>Not in today's queue</summary>

- Labelled on-hold: #28, #82, #98, #173, #311, #348, #446, #459, #464, #482, #546, #565, #568, #573, #608, #618, #619
- Not reviewed yet: 48

</details>

<sub>Built by maintainer-bot from its reviews · runs on [0G Private Computer](https://pc.0g.ai)</sub>

<!-- mb-queue {"date":"2026-10-21","items":{"437":{"sha":"bb7fe8b7d85a","v":"merge"},"699":{"sha":"acc7655ce395","v":"merge"},"703":{"sha":"08fefbe82f3c","v":"merge"},"709":{"sha":"b5087ce6b98d","v":"merge-with-fix"},"727":{"sha":"5df7828891c1","v":"merge"},"728":{"sha":"d827cda776f7","v":"merge"},"732":{"sha":"bba711e49e68","v":"merge"},"733":{"sha":"8582297e388d","v":"merge-with-fix"},"338":{"sha":"2c168adfa3d7","v":"merge-with-fix"},"472":{"sha":"38eb0c3c5ffb","v":"close"},"720":{"sha":"0bd819ea4b12","v":"merge"},"721":{"sha":"27abe5290fb9","v":"merge"},"723":{"sha":"7715f317f9df","v":"merge"},"39":{"sha":"ca6490cf37b7","v":"hold"},"146":{"sha":"2b2b825263ce","v":"hold"},"150":{"sha":"78376dd45763","v":"hold"},"174":{"sha":"186240e0b17e","v":"hold"},"175":{"sha":"876254a4582d","v":"hold"},"228":{"sha":"a16153fa15b6","v":"hold"},"244":{"sha":"ee78d8b49776","v":"hold"},"257":{"sha":"b7e2ebc81c81","v":"hold"},"268":{"sha":"2fdb53c9b025","v":"hold"},"308":{"sha":"6d273b9dcca2","v":"hold"},"309":{"sha":"023543054f89","v":"hold"},"310":{"sha":"522daa5075c6","v":"hold"},"326":{"sha":"5add0e998ba7","v":"hold"},"327":{"sha":"55a8ebb34731","v":"hold"},"378":{"sha":"16fd6feaee1e","v":"hold"},"383":{"sha":"20c28177f08b","v":"hold"},"389":{"sha":"a3f5aae9802f","v":"hold"},"401":{"sha":"94fbac55aad3","v":"hold"},"407":{"sha":"36b4128fe3a4","v":"hold"},"448":{"sha":"52f8adbcb3de","v":"hold"},"450":{"sha":"9c84406a8c9c","v":"hold"},"451":{"sha":"98a4134e87c9","v":"hold"},"452":{"sha":"eaf2daea2968","v":"hold"},"456":{"sha":"89d7dc990faf","v":"hold"},"457":{"sha":"df397ca571d9","v":"hold"},"458":{"sha":"531906ed24f6","v":"hold"},"467":{"sha":"97a9c605059c","v":"hold"},"473":{"sha":"a05282756a99","v":"hold"},"479":{"sha":"2c873c727500","v":"hold"},"484":{"sha":"4e68b6e60153","v":"hold"},"487":{"sha":"9753c1f52c89","v":"hold"},"488":{"sha":"46afc2857ddc","v":"hold"},"496":{"sha":"a677e27a4594","v":"hold"},"497":{"sha":"fef5edb234e3","v":"hold"},"505":{"sha":"5edc52f27140","v":"hold"},"510":{"sha":"df34384514c6","v":"hold"},"511":{"sha":"1c4b1a87e719","v":"hold"},"518":{"sha":"40dcd10246e8","v":"hold"},"522":{"sha":"f1c5d2fd8405","v":"hold"},"523":{"sha":"8f5d4bf07316","v":"hold"},"524":{"sha":"5a5508ad51e0","v":"hold"},"525":{"sha":"0efc394db501","v":"hold"},"526":{"sha":"7186c7c0b75b","v":"hold"},"527":{"sha":"1233acbb8f47","v":"hold"},"534":{"sha":"56b416164337","v":"hold"},"535":{"sha":"24da0cb1478b","v":"hold"},"537":{"sha":"5fa4a8ef9172","v":"hold"},"558":{"sha":"b3c1d3d1afa5","v":"hold"},"560":{"sha":"4b026f841b24","v":"hold"},"566":{"sha":"39555c0fd491","v":"hold"},"572":{"sha":"27d965242d8e","v":"hold"},"593":{"sha":"5b7023bc7bff","v":"hold"},"595":{"sha":"69c4e8efb993","v":"hold"},"708":{"sha":"41ef8ae44370","v":"hold"},"719":{"sha":"770ee98b4693","v":"hold"},"722":{"sha":"4e850fee7805","v":"hold"},"724":{"sha":"6127c7b70f2a","v":"hold"},"725":{"sha":"c6f264badb1d","v":"hold"},"726":{"sha":"8b2f6232286f","v":"hold"},"730":{"sha":"0b4782d44697","v":"hold"},"731":{"sha":"a4c70564dfb3","v":"hold"}}} -->
````

## Real fix trial (0G router, local only, nothing pushed)

The three merge-with-fix PRs, run through the real fix path on a local clone: branch at the PR head (main merged in when needed), the fix model proposes search/replace edits, the checks validate them, the edits are committed locally and CleanYourTV's own test suite runs on the result.

| PR | Fix asked | Edit | Checks | cleanyourtv tests after | Cost |
|---|---|---|---|---|---|
| #338 | In the new SHOWCASE.md row, change the 'Built on' cell to: "Haier Android TV / Google TV (MediaTek, CVTE); not | note in the cleanyourtv for Haier SHOWCASE row that it has not yet run on a TV (`SHOWCASE.md` +1) | ok | OK (skipped=1) | $0.021 |
| #709 | Add a skyworth-65a3f row (Skyworth 65A3F, China, Android 13 CCOS, no GMS) to the TV table in the root README.m | add Skyworth 65A3F row to the root README TV table, matching examples/README.md (`README.md` +1) | ok | OK (skipped=1) | $0.056 |
| #733 | Add a `skyworth-swtv-24ae-4k-nf/` row to the TV table in the root README.md, next to the skyworth-swtv-24na-4k | list Skyworth SWTV-24AE-4K NF in the root README TV table next to SWTV-24NA-4K NF (`README.md` +1) | ok | OK (skipped=1) | $0.059 |

Before the fix, #709 and #733 fail CleanYourTV's "Lists, tools and docs" check (the README TV table is missing their row); after it, the suite passes. A first attempt (before the bot learned to look up the brand's neighbouring rows in the big README) proposed nothing usable for #709 and #733; validation rejected those edits, so nothing would have been merged. Total spend for the trial including that first attempt: about $0.26 (this table: $0.14).

Note: the dry run cannot see conflicts that appear mid-batch. If one of the TV-list merges adds a table row next to another one, the later PR stops merging cleanly; it then goes through the bot-branch path (table rows from both sides kept, count lines from main, then the counts PR), as in the E2E simulation.
