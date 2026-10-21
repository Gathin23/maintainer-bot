# maintainer-bot backtest on Gathin23/cleanyourtv

Generated locally, nothing posted to GitHub. All model calls went through the 0G Private Computer router.

## Summary for Gathin

**What was built** (local only, nothing pushed, nothing posted): `~/Arsenal/maintainer-bot`, an MIT Python package + GitHub Action skeleton.
Facts layer, decision step on the 0G router, memory of earlier decisions (no leakage), deterministic overrides,
daily queue renderer, `/approve` parser, action planner (dry-run), merge-with-fix job A (edit proposals + validator),
spend ledger with a hard cap, backtest + report. 14 unit tests pass.

**Backtest:** 497 decided community PRs from the repo's real history (272 merged, 102 merged with a fix, 76 closed,
26 rework, 21 hold).

| Model (rules v2) | PRs | Agrees with you (merge ≈ merge-with-fix) | Bot decides itself | Agreement when it decides | Safety misses | $/PR |
|---|---|---|---|---|---|---|
| Claude Opus 5.5 | 97 (sample) | **74%** | 88% | **84%** | 4 | ~$0.037 |
| GLM-5.3 (TEE-sealed) | 53 (sample, capacity-limited) | **70%** | 89% | 79% | 3 | ~$0.017 |
| GLM-5.3-flash | 120 (sample) | 69% | 79% | 82% | 10 | ~$0.002 |
| Claude Opus 5.5 · Round L (today) | 72 | **78%** | 78% | 84% | 4 | ~$0.037 |

On the 51 PRs all three models judged: Opus 36, GLM-5.3 35, flash 33 correct. GLM-5.3 is within one PR of Opus at
under half the price, and it is the one we can honestly call private (sealed in a TEE).

**Where it's strong:** TV-list PRs: 37 of 41 agree (90%) on the Opus sample. Docs and showcase rows are reliable too.

**Where it's weak (and why autonomy stays off for them):**
- The safety misses are almost all launcher code where you found a real bug or wanted a TV run (#39, #401, #407,
  #568) and one header-only list edit you closed (#124). Policy "launcher code = always needs you" removes the
  launcher ones; then 2 misses remain on the sample.
- merge vs merge-with-fix is a coin flip (your small on-merge touches are hard to predict); treated as one family.
- Rules v1 → v2 (setupwraith is normal on Google TV lists; omnibus PRs aren't competing lists; bundles and
  superseded ideas get a kind close; overrides only ever stop merges) moved Opus from 63% → 74% agreement.

**Merge-with-fix, job A:** on 5 past PRs it produced valid edits for 3 (#301 matches your note exactly, #392 adds the
missing README row like you did), proposed a different but reasonable fix on #251, escalated #172 (needs a rebase),
and the validator caught one edit whose search text didn't match (#399), so it would have gone to you, not merged.

**0G Private Computer notes from this run:** GLM-5.3 (TEE) was overloaded for minutes at a time ("retry in 30s") and
answers in ~60–90 s per decision because it thinks first; fine for a daily batch (~100 PRs/day), too slow for
instant per-PR labels. The bot waits and retries and never switches provider, so the "runs on 0G" claim stays true.
Claude on 0G PC refuses a forced tool on one of its two providers; handled by asking for the tool instead.

**Recommendation**
1. Decisions on **GLM-5.3** (sealed, cheaper, near-Opus accuracy); fixes on Claude Opus 5.5 (better at exact edits).
   Footer: "runs on 0G Private Computer (GLM-5.3, sealed in a TEE)".
2. Policy: launcher code, workflows, prompt safety rules and scripts' Home logic are always "needs you".
3. Next tuning: the close-vs-rework line, and teach it your TV-run holds (launcher behaviour you want to see first).
4. **Ready for the shadow week, not for /approve yet:** post the queue on a private test repo (or as a gist) daily,
   you keep deciding as now, and we compare for 7 days. Autonomy only for TV-list PRs after that if they stay ≥95%.

## Dataset

- **497 decided community PRs** (the maintainer's own PRs excluded), replayed in the order they were decided.
- Truth = what actually happened: merge 272, merge-with-fix 102, close 76, rework 26, hold 21.
  merge-with-fix = merged with an 'On merge: …' note in the merge commit; rework / hold = the open PR's current label.
- Snapshot = the PR as merged (merge commit's second parent) or its last commit before the decision. Commit dates are author-set, so a few reworked PRs may show a later push.
- Memory = up to 8 similar PRs decided **earlier** (never the PR itself, never later decisions), with the maintainer's merge note or comment as the reason.
- Stratified sample of 120 for model comparison (Claude Opus 5.5 ran on the first 100 of it); Round L = PRs #543+ (decided today).

## Headline (rules v2)

### Claude Opus 5.5 · 100-PR sample

- PRs judged: **97** (3 failed calls not counted)
- Exact agreement with the maintainer: **44%**
- Agreement treating merge and merge-with-fix as one: **74%**
- The bot decided on its own in 88% of PRs; when it did, it agreed **84%** (merge family). The rest went to the maintainer as 'hold'.
- Model alone, before the deterministic overrides: 79% (merge family)
- Safety misses (bot says merge, maintainer closed/reworked/held): **4**
- Spend: $3.60 total, $0.037 per PR

| truth ↓ / bot → | merge | merge-with-fix | rework | close | hold | n |
|---|---|---|---|---|---|---|
| **merge** | 26 | 18 | 4 | 1 | 4 | 53 |
| **merge-with-fix** | 11 | 8 | 1 | 0 | 3 | 23 |
| **rework** | 2 | 1 | 2 | 0 | 0 | 5 |
| **close** | 1 | 0 | 3 | 6 | 4 | 14 |
| **hold** | 0 | 0 | 1 | 0 | 1 | 2 |

| class | n | recall | precision |
|---|---|---|---|
| merge | 53 | 49% | 65% |
| merge-with-fix | 23 | 35% | 30% |
| rework | 5 | 40% | 18% |
| close | 14 | 43% | 86% |
| hold | 2 | 50% | 8% |

Safety misses:
- #39 (rework → bot merge, conf 0.72): Launcher: faster Home, cache app tiles off the main thread — bot's reason: Performance-only launcher change: no new dependencies, permissions, config or strings, and visuals stay the same
- #124 (close → bot merge, conf 0.92): examples/tcl-q10g-pro: correct the ADB and sideloading notes — bot's reason: The original author is correcting the notes on the same unit as #111. The change stays inside the header comments of examples/tcl-q10g-pro.
- #401 (rework → bot merge-with-fix, conf 0.8): launcher: input_action_map for TVs that switch inputs with an action + integer e — bot's reason: Clean, small design: only runs after ACTION_VIEW fails, and a malformed entry returns false so the old input_action path still runs
- #407 (rework → bot merge, conf 0.85): launcher: Fire OS routes standard settings intents to a CTS stub; fall back to M — bot's reason: Fixes dead Settings pill, quick settings rows and Wi-Fi long-press on Fire TV, which uses a CTS stub handler for settings intents

### GLM-5.3 (TEE-sealed) · 120-PR sample

- PRs judged: **53** (0 failed calls not counted)
- Exact agreement with the maintainer: **45%**
- Agreement treating merge and merge-with-fix as one: **70%**
- The bot decided on its own in 89% of PRs; when it did, it agreed **79%** (merge family). The rest went to the maintainer as 'hold'.
- Model alone, before the deterministic overrides: 75% (merge family)
- Safety misses (bot says merge, maintainer closed/reworked/held): **3**
- Spend: $0.93 total, $0.017 per PR

| truth ↓ / bot → | merge | merge-with-fix | rework | close | hold | n |
|---|---|---|---|---|---|---|
| **merge** | 18 | 12 | 2 | 1 | 2 | 35 |
| **merge-with-fix** | 1 | 3 | 1 | 0 | 0 | 5 |
| **rework** | 1 | 0 | 0 | 0 | 1 | 2 |
| **close** | 2 | 0 | 1 | 3 | 3 | 9 |
| **hold** | 0 | 0 | 2 | 0 | 0 | 2 |

| class | n | recall | precision |
|---|---|---|---|
| merge | 35 | 51% | 82% |
| merge-with-fix | 5 | 60% | 20% |
| rework | 2 | 0% | 0% |
| close | 9 | 33% | 75% |
| hold | 2 | 0% | 0% |

Safety misses:
- #39 (rework → bot merge, conf 0.78): Launcher: faster Home, cache app tiles off the main thread — bot's reason: Real-device tested with Perfetto/gfxinfo numbers: Home key-to-frame 151→94 ms, cold start roughly halved — exactly the launcher's small-and-fast goal for 1 GB T
- #58 (close → bot merge, conf 0.88): launcher: verify install and home switch before disabling the stock l… — bot's reason: Implements the safety behavior the README already promises: install and home switch are verified, fail-closed, before the stock launcher is disabled
- #124 (close → bot merge, conf 0.95): examples/tcl-q10g-pro: correct the ADB and sideloading notes — bot's reason: Same-unit correction to the merged #111 list header; both edits come from real-device observation

### GLM-5.3-flash · 120-PR sample

- PRs judged: **120** (0 failed calls not counted)
- Exact agreement with the maintainer: **43%**
- Agreement treating merge and merge-with-fix as one: **69%**
- The bot decided on its own in 79% of PRs; when it did, it agreed **82%** (merge family). The rest went to the maintainer as 'hold'.
- Model alone, before the deterministic overrides: 72% (merge family)
- Safety misses (bot says merge, maintainer closed/reworked/held): **10**
- Spend: $0.25 total, $0.002 per PR

| truth ↓ / bot → | merge | merge-with-fix | rework | close | hold | n |
|---|---|---|---|---|---|---|
| **merge** | 35 | 16 | 1 | 1 | 8 | 61 |
| **merge-with-fix** | 15 | 7 | 1 | 0 | 2 | 25 |
| **rework** | 3 | 2 | 1 | 0 | 2 | 8 |
| **close** | 3 | 0 | 3 | 4 | 8 | 18 |
| **hold** | 2 | 0 | 1 | 0 | 5 | 8 |

| class | n | recall | precision |
|---|---|---|---|
| merge | 61 | 57% | 60% |
| merge-with-fix | 25 | 28% | 28% |
| rework | 8 | 12% | 14% |
| close | 18 | 22% | 80% |
| hold | 8 | 62% | 20% |

Safety misses:
- #39 (rework → bot merge, conf 0.88): Launcher: faster Home, cache app tiles off the main thread — bot's reason: Tested on a real TV with Perfetto/gfxinfo/meminfo numbers and a rebase that preserves the merged launcher behaviour
- #58 (close → bot merge, conf 0.9): launcher: verify install and home switch before disabling the stock l… — bot's reason: Fixes a real hazard: a failed install or set-home could disable the stock launcher and leave no working home screen
- #124 (close → bot merge, conf 0.95): examples/tcl-q10g-pro: correct the ADB and sideloading notes — bot's reason: corrects merged device notes against what was actually observed on the same tested unit
- #347 (close → bot merge, conf 0.85): docs(showcase): add firetv-clean-root — bot's reason: In-scope one-row SHOWCASE entry for a CleanYourTV-based Fire TV companion toolkit
- #401 (rework → bot merge-with-fix, conf 0.78): launcher: input_action_map for TVs that switch inputs with an action + integer e — bot's reason: Shipped config should stay neutral: device-specific entries belong in that TV's example config, as the author offered
- #407 (rework → bot merge, conf 0.9): launcher: Fire OS routes standard settings intents to a CTS stub; fall back to M — bot's reason: Fixes dead Settings pill, key panel and Wi-Fi long-press on Fire TV
- #446 (hold → bot merge, conf 0.85): Launcher: single-pass grid layout, 128×72 L2 gradients & Scratch FBO trim — bot's reason: maintainer-requested perf trims extracted from #398/#39
- #558 (rework → bot merge-with-fix, conf 0.78): launcher: ambient_glow and app_glow, the focused app's colour on its tile instea — bot's reason: ambient_glow already landed in #581 — re-adding it would duplicate the key; only app_glow is new
- #560 (rework → bot merge, conf 0.93): tools/shot.py: screenshot from the TV, optionally pressing remote keys first — bot's reason: delivers the three things #241 asked for (key-name check, clear screencap failure message, README row)
- #568 (hold → bot merge, conf 0.85): launcher: dock band, more room at the sides so a focused first or last tile clea — bot's reason: Tested on a real TV with screenshot, focus checked on edge and middle tiles

### Claude Opus 5.5 · Round L (today, PRs #543+)

- PRs judged: **72** (0 failed calls not counted)
- Exact agreement with the maintainer: **58%**
- Agreement treating merge and merge-with-fix as one: **78%**
- The bot decided on its own in 78% of PRs; when it did, it agreed **84%** (merge family). The rest went to the maintainer as 'hold'.
- Model alone, before the deterministic overrides: 82% (merge family)
- Safety misses (bot says merge, maintainer closed/reworked/held): **4**
- Spend: $2.67 total, $0.037 per PR

| truth ↓ / bot → | merge | merge-with-fix | rework | close | hold | n |
|---|---|---|---|---|---|---|
| **merge** | 30 | 7 | 1 | 0 | 6 | 44 |
| **merge-with-fix** | 7 | 0 | 0 | 0 | 0 | 7 |
| **rework** | 0 | 1 | 2 | 2 | 0 | 5 |
| **close** | 2 | 0 | 0 | 1 | 1 | 4 |
| **hold** | 1 | 0 | 2 | 0 | 9 | 12 |

| class | n | recall | precision |
|---|---|---|---|
| merge | 44 | 68% | 75% |
| merge-with-fix | 7 | 0% | 0% |
| rework | 5 | 40% | 40% |
| close | 4 | 25% | 33% |
| hold | 12 | 75% | 56% |

Safety misses:
- #558 (rework → bot merge-with-fix, conf 0.72): launcher: ambient_glow and app_glow, the focused app's colour on its tile instea — bot's reason: ambient_glow already landed in #581; this PR's copy of that key duplicates it and will conflict
- #568 (hold → bot merge, conf 0.82): launcher: dock band, more room at the sides so a focused first or last tile clea — bot's reason: Small visual fix: since #476, a focused first dock tile nearly touches the band's rounded end and the dock looks off-centre
- #591 (close → bot merge, conf 0.85): Remote keys: map app buttons by scancode — bot's reason: Opt-in addition to the existing app_keys config: only takes effect when scan: entries are set, and old keycode entries parse exactly as before
- #627 (close → bot merge, conf 0.86): Launcher: Portuguese date on two lines next to the clock — bot's reason: Override for the Portuguese locale only, using the same mechanism as the German fix (#276): date_single_line=false plus a two-line date_format_home

### v1 rules, Claude Opus 5.5 · same sample

- PRs judged: **98** (2 failed calls not counted)
- Exact agreement with the maintainer: **35%**
- Agreement treating merge and merge-with-fix as one: **63%**
- The bot decided on its own in 84% of PRs; when it did, it agreed **74%** (merge family). The rest went to the maintainer as 'hold'.
- Model alone, before the deterministic overrides: 70% (merge family)
- Safety misses (bot says merge, maintainer closed/reworked/held): **4**
- (v1 run, before tuning)

| truth ↓ / bot → | merge | merge-with-fix | rework | close | hold | n |
|---|---|---|---|---|---|---|
| **merge** | 25 | 19 | 6 | 0 | 4 | 54 |
| **merge-with-fix** | 9 | 6 | 4 | 1 | 2 | 22 |
| **rework** | 2 | 1 | 2 | 0 | 0 | 5 |
| **close** | 1 | 0 | 5 | 0 | 9 | 15 |
| **hold** | 0 | 0 | 1 | 0 | 1 | 2 |

| class | n | recall | precision |
|---|---|---|---|
| merge | 54 | 46% | 68% |
| merge-with-fix | 22 | 27% | 23% |
| rework | 5 | 40% | 11% |
| close | 15 | 0% | 0% |
| hold | 2 | 50% | 6% |

Safety misses:
- #39 (rework → bot merge, conf 0.65): Launcher: faster Home, cache app tiles off the main thread — bot's reason: Clear speed gain measured on a real Google TV (MiTV-MOOR2): Home press median 151 → 94 ms, cold start roughly halved, fewer frames drawn
- #124 (close → bot merge, conf 0.92): examples/tcl-q10g-pro: correct the ADB and sideloading notes — bot's reason: Only comment lines change in the header of the existing tcl-q10g-pro list, from the same author and unit as #111
- #401 (rework → bot merge-with-fix, conf 0.8): launcher: input_action_map for TVs that switch inputs with an action + integer e — bot's reason: Clean, opt-in mechanism: it only runs after ACTION_VIEW fails, and a malformed entry falls back to input_action. HDMI1 was verified on a real MiTV-ANSP0.
- #407 (rework → bot merge, conf 0.85): launcher: Fire OS routes standard settings intents to a CTS stub; fall back to M — bot's reason: Fixes dead Settings, Wi-Fi long-press and quick-settings rows on Fire TV, where the standard intents resolve to a CTS stub

## What the daily queue looks like (Round L, rendered from the bot's own decisions)

<details><summary>Queue issue</summary>

## Today's queue · 2026-10-21

✅ 40 · 🔧 8 · ↩️ 5 · ❌ 3 · 🤔 16

### ✅ Merge (40)
- [ ] #544 **launcher: network and Inputs pills refresh after the first frame back on Home** · p2 · launcher<br>A small speed fix with no visible change. Coming back to Home, the network and Inputs pills now refresh after the first frame instead of holding it up; the first resume still fills them before drawing.
- [ ] #545 **Add Hisense Fire TV (AFTCIBFBD1, Fire OS 8) debloat list** · p2 · tv-list<br>New, tested Fire OS 8 TV list in its own folder (hisense-fire-tv-aftcibfbd1), disable-only, protected launcher kept
- [ ] #552 **launcher: Home while Home is still on screen no longer replays the entrance animation** · p2 · launcher<br>Small, correct bug fix: when Home was never stopped, its tiles are still current, so it now refocuses instead of rebuilding. Rebuilding after returning from an app works as before.
- [ ] #553 **launcher: keep the stats line while Home is paused, and let it run past the date** · p2 · launcher<br>Fixes a real bug: hiding the stats line on pause made the grid jump up while the glass highlight stayed in place
- [ ] #554 **i18n: Spanish strings for quick settings, wallpaper, home picker, module cards and races** · p2 · launcher<br>Fills in the 43 strings values-es was missing, so these screens no longer fall back to English on Spanish TVs
- [ ] #555 **examples/tcl-g09-google-tv: map the remote's Netflix, Prime Video and YouTube buttons** · p2 · tv-list<br>Only touches its own folder: adds app_keys to the G09 config and documents the remote buttons
- [ ] #556 **launcher: compact top bar, opt-in (icon_only_buttons, wifi_label_width, library_button)** · p2 · launcher<br>All three keys are opt-in and off by default. They reuse existing strings, so no locale is missing anything.
- [ ] #557 **launcher: always_show_names, names under every tile including the dock (opt-in)** · p2 · launcher<br>Opt-in flag always_show_names, off by default, so nothing changes for existing TVs
- [ ] #559 **feat(examples): add Dialog ViU (SEI103DL, Android TV 9)** · p2 · tv-list<br>This is the first list for this model (new folder dialog-viu-sei103dl). It was tested on a real box the same day, including a reboot.
- [ ] #567 **Verify staged base64 uploads before replacing the destination** · p2 · scripts<br>Fixes real data loss: b64push deleted the destination before the transfer, so a failed upload lost the old file
- [ ] #568 **launcher: dock band, more room at the sides so a focused first or last tile clears the rou** · p2 · launcher<br>Small visual fix: since #476, a focused first dock tile nearly touches the band's rounded end and the dock looks off-centre
- [ ] #578 **examples: add TCL 43S5400A (C06_2K_GB, MediaTek MT9221, Android TV 11)** · p2 · tv-list<br>New, non-duplicate folder for a tested 43" C06_2K_GB unit, with real-device results (apps, all inputs, Live TV, RAM)
- [ ] #582 **examples/sony-bravia-vu31: remote app buttons go through launcherx** · p2 · tv-list<br>Only adds header notes to the existing VU31 list; no package lines change, so the list's safety stays the same
- [ ] #585 **Launcher: let go of the tiles when memory is short and Home is hidden** · p2 · launcher<br>Small, self-contained memory fix that only runs while Home is stopped. Users see no difference, so it doesn't need a config flag.
- [ ] #586 **Launcher: the key services subscribe to no accessibility events** · p2 · launcher<br>Both onAccessibilityEvent bodies are empty, so subscribing to typeWindowStateChanged only made the system wake the launcher on every window change for nothing
- [ ] #588 **Add Norwegian Bokmål (nb) translation** · p2 · launcher<br>A new translation that covers all strings, with the locale registered in locales_config and added to the README list
- [ ] #591 **Remote keys: map app buttons by scancode** · p2 · launcher<br>Opt-in addition to the existing app_keys config: only takes effect when scan: entries are set, and old keycode entries parse exactly as before
- [ ] #592 **Remote keys: map app buttons by scancode** · p2 · launcher<br>Opt-in: it only does something when a user adds scan: entries to app_keys, so nothing changes by default and no UI strings are needed
- [ ] #594 **Launcher: show_network_pill, to hide the Wi-Fi/Ethernet pill (from #326)** · p2 · launcher<br>Small opt-in config flag; the default keeps today's behaviour, so no TV changes unless it is set
- [ ] #596 **Launcher: no connection state on AV rows in the Inputs menu (from #429)** · p2 · bug<br>Small, correct bug fix: AV, component and other analog jacks can't detect when something is plugged in, so their 'Connected' state is wrong; HDMI rows keep theirs, and the hdmiStateBogus case still works
- [ ] #606 **examples: Sony BRAVIA 4K VH21 (XR-55A80K), EU firmware** · p2 · tv-list<br>New EU firmware list for VH21; preloads differ from the AU folder, so it is not a duplicate
- [ ] #610 **launcher: opt-in clock screensaver that starts only from Home** · p2 · launcher<br>It's opt-in (home_idle_clock_minutes defaults to 0), offline, adds no strings and keeps the APK at 406 KB.
- [ ] #615 **examples: add Artel smart TV (CVTE MT5863, Android 7.0) list** · p2 · tv-list<br>New TV folder, not a duplicate, with rows added to both README.md and examples/README.md
- [ ] #620 **Wallpapers: opt-in sequential/shuffle playback order with restart reconciliation (#602)** · p2 · theme<br>Opt-in theme key: if wallpaper_order is missing or unknown, rotation stays random as before
- [ ] #627 **Launcher: Portuguese date on two lines next to the clock** · p2 · launcher<br>Override for the Portuguese locale only, using the same mechanism as the German fix (#276): date_single_line=false plus a two-line date_format_home
- [ ] #628 **examples: add Xiaomi MiTV-ASTP0 (mulan, L55M7-EA), China firmware** · p2 · tv-list<br>New, device-tested list in its own folder (xiaomi-mitv-astp0); it doesn't duplicate any existing list
- [ ] #631 **examples: Redmi TV MiTV-MFTP0 (alita), China firmware 23.2.10.6129** · p2 · tv-list<br>New folder (redmi-mitv-mftp0) with no duplicate. It was tested on the real TV, and the header honestly says it hasn't been used for several days yet.
- [ ] #548 **Showcase: pipes-tv, a 3D Pipes screensaver** · p3 · showcase<br>Adds one SHOWCASE.md row for a separate open-source app (MIT) tested on a TCL 75T7 running Google TV 14, which fits the showcase rules
- [ ] #549 **SHOWCASE: add Vibe Launcher** · p3 · showcase<br>Adds one SHOWCASE row in the existing format: open source (MIT), the author's own project, and tested devices are listed
- [ ] #569 **launcher: smooth focus glow, twelve thin rings instead of three wide strokes** · p3 · launcher<br>Small rendering fix in GlassView: same inset and strength, but a smooth falloff instead of three visible bands
- [ ] #570 **launcher: wallpaper_true_color, decode wallpapers in 32-bit colour (opt-in)** · p3 · launcher<br>Small opt-in config flag, off by default, so 1 GB TVs keep RGB_565
- [ ] #574 **SHOWCASE: TV Remote gains TV Home, a launcher set up from the phone or computer** · p3 · showcase<br>It updates the author's existing SHOWCASE row (from #404) and changes nothing else
- [ ] #579 **examples: TCL G10 list used on a C69B, with its remote's keycodes** · p3 · tv-list<br>Adds only header notes to the existing G10 list; no list entries change
- [ ] #580 **launcher: follow the real sunrise and sunset when a location is set** · p3 · launcher<br>Off by default: with latitude and longitude left empty, the sky works exactly as before
- [ ] #581 **Launcher: ambient_glow option to turn off the app-coloured glow** · p3 · launcher<br>Small opt-out config flag that defaults to the current behaviour, so existing setups don't change
- [ ] #583 **Launcher: don't load a tile's icon when it has a banner** · p3 · launcher<br>One-line change that skips decoding an icon that is never drawn when a tile has a banner, which saves work on every rebuild on low-RAM TVs
- [ ] #584 **Launcher: one LEANBACK query per rebuild; card records read only when an app declares a ca** · p3 · launcher<br>Small internal refactor with no change in what users see: one LEANBACK query per rebuild, and cards.json is only read when an app declares a card
- [ ] #607 **Add Dutch translations** · p3 · launcher<br>Adds a new Dutch locale: values-nl covers every translatable string, including the plural
- [ ] #609 **launcher: add Uzbek (Latin) translation** · p3 · launcher<br>Adds a complete values-uz locale, registers it in locales_config.xml and adds it to the README language list
- [ ] #629 **SHOWCASE: add freeTV** · p3 · showcase<br>A heavily changed fork with network features belongs in SHOWCASE, which is where we pointed earlier launcher PRs like #591, #613 and #627

### 🔧 Merge with a small fix (8)
- [ ] #547 **Add TCL 75T7 (G08, US firmware) list** · p2 · tv-list<br>New model and firmware (G08_4K_US, AU16), so it doesn't duplicate the AU02 G08 lists. Disable-only, and it keeps the TV, input, input menu, autopair, voice and Play Services packages.<br>fix: In the debloat.txt header and the folder README, add that disabling com.google.android.tungsten.setupwraith gives Home back but costs casting. In the examples/README.md row, change 'ttvs, partnercustomizer, Chromecast and the USB player kept' to 'ttvs, partnercustomizer and the USB player kept; casting lost with setupwraith off'.
- [ ] #551 **Add Skyworth SW-22SA (SW6H) debloat list** · p2 · tv-list<br>New, well-documented list tested on a real device. It disables only, keeps TV/input, BLE remote pairing, Play Store and Services, and documents setupwraith<br>fix: In examples/README.md, put back the deleted `sanyo-atv-r2/` row (SANYO ATV R2 (SCBC, Realtek RTD285O) | Android TV 9 | S-Channels, E-SHOW demo, Vewd, TV Booster, SANYO OTA) right above the new `skyworth-sw-22sa/` row.
- [ ] #575 **launcher: accept java_home's answer only when it really is a 17** · p2 · launcher<br>Real build failure for contributors who follow CONTRIBUTING.md on a Mac with a newer JDK registered; the fix is small and scoped to the build script<br>fix: In launcher/build-and-install.sh, widen the case pattern to `*'version "17"'*|*'version "17.'*)` so the JDK 17 GA release (`version "17"`) is also accepted.
- [ ] #587 **docs: add Strong LEAP-S3 device note (Skyworth YDA Google TV box)** · p2 · docs<br>Useful, honest device note: identity table, the HOME order that avoided a black screen, remote keycodes, and why oemservice/deviceinfo were kept or disabled<br>fix: In examples/README.md, move the '- [Strong LEAP-S3](../docs/devices/strong-leap-s3.md) ...' bullet out of the table (it currently sits between the tcl-qm6k-google-tv and tcl-g07-google-tv rows) and into the device-notes list under the table.
- [ ] #612 **Add Xiaomi MiTV-MTEQ0 (baymax, China firmware) list and device notes** · p2 · tv-list<br>New, device-tested list for a model that isn't in the repo yet (xiaomi-mitv-mteq0), with rows in README and examples/README<br>fix: Bump the TV/list counts in README.md (and examples/README.md if it has one) by one for the new xiaomi-mitv-mteq0 list.
- [ ] #614 **Launcher: keep the theme overlay readable before storage mounts** · p2 · bug<br>Real bug: Home starts before storage mounts, so the dock order and on-TV choices are lost at boot. Tested across two reboots on a Xiaomi MiTV-MTEQ0<br>fix: In Config.java, move the existing '/** Reads and parses the overlay; any problem means "no overlay"... */' comment back so it sits directly above read(), leaving only the new Javadoc above readOverlay().
- [ ] #558 **launcher: ambient_glow and app_glow, the focused app's colour on its tile instead of the w** · p3 · launcher<br>ambient_glow already landed in #581; this PR's copy of that key duplicates it and will conflict<br>fix: Resolve against #581: keep #581's ambient_glow (field, config.xml bool, View.GONE handling, README row) and drop this PR's duplicate of it. Add only app_glow to the Config constructor and config.xml, plus the MainActivity glass-accent change and the themes/README row. Defaults stay the same.
- [ ] #626 **docs: record TCL BeyondTV AP08 setup and verification** · p3 · docs<br>Docs-only device note for a new firmware (AP08), linked from the existing BeyondTV and RT2851 examples; it is not a duplicate list<br>fix: In examples/README.md, delete the blank line added after the new TCL BeyondTV AP08 bullet so it sits directly above the Sony XR-75X91K bullet in the same list.

### ↩️ Ask for rework (5)
- [ ] #546 **launcher: restore selected Home after Xiaomi STR wake (MiTV-ASTP0)** · p2 · launcher<br>The boot/STR receiver and RECEIVE_BOOT_COMPLETED are on for every build and every TV. New launcher behaviour must be opt-in and off by default.<br>ask: Make StartupReceiver opt-in, enabled only in the legacyXiaomiWake build or behind a config flag that is off by default, and link the device note to the existing MiTV-ASTP0 example list from #628.
- [ ] #562 **Add Sankey SMART2KTVSE (Whale OS, Android 13) debloat list** · p2 · tv-list<br>com.zeasn.livetv is an active list entry, but the notes say disabling it causes 'No Signal' on all inputs, so running the list as written breaks HDMI/AV.<br>ask: Comment out com.zeasn.livetv (and any other line you kept enabled) so that debloat.txt lists only the packages you actually disabled on the TV.
- [ ] #573 **Launcher: long-press a tile to Hide App or Uninstall** · p2 · launcher<br>Changes long-press for every TV instead of sitting behind a config flag that is off by default<br>ask: Put the long-press menu behind a config flag that is off by default (long-press still opens App info when the flag is off), add the 6 strings to every values-* locale, and test it on a real TV.
- [ ] #593 **config.xml: default Google TV / TCL remote keycodes for gear and YouTube** · p2 · launcher<br>Changes the launcher defaults for every TV. The rule is that per-remote keycodes go in that TV's example config.<br>ask: Leave both arrays in config.xml empty. Put settings_key_keycodes [83] and app_keys ["190:com.google.android.youtube.tv"] in examples/tcl-qm6k-google-tv's config.json instead, and note that this needs HOME_KEY_SERVICE=1.
- [ ] #595 **Launcher: focus_overshoot, highlight and tile zoom without the bounce (from #326)** · p2 · launcher<br>new launcher strings in 2 of 23 locales<br>ask: Resolve the Config constructor/Config.load and config.xml conflicts with the options merged since (#557, #570, #610, #620), keeping every option and leaving all defaults unchanged (focus_overshoot stays true).

### ❌ Close (kindly) (3)
- [ ] #543 **Launcher: a Zen list of app names instead of tiles** · p2 · launcher<br>Adds the INTERNET permission and a RemoteWallpaper network fetch. The launcher stays offline and network features have been refused before.
- [ ] #560 **tools/shot.py: screenshot from the TV, optionally pressing remote keys first** · p3 · scripts<br>Screenshot capture has since landed another way: #571 added tv.py --screenshot, which captures on the TV and pulls the PNG
- [ ] #572 **Add Hisense 65U68QF Fire TV (Fire OS 8) debloat list** · p3 · tv-list<br>Same device (Hisense Fire TV AFTCIBFBD1, Fire OS 8) is already covered by the merged list from #545, so this would be a second folder for one TV

### 🤔 Needs you (16)
- [ ] #565 **Keep a usable Home when launcher resolution is inconclusive** · p1 · scripts<br>Changes the Home-safety guard in tools/disable.sh and tools/disable.ps1, and the review rules say the maintainer has to decide on that<br>question: Changes the Home-safety guard in tools/disable.sh and tools/disable.ps1, and the review rules say the maintainer has to decide on that
- [ ] #561 **tools/relay.py: reach the TV from an assistant whose sandbox can't** · p2 · scripts<br>touches maintainer-only paths: PROMPT.md<br>question: touches maintainer-only paths: PROMPT.md
- [ ] #571 **tools: tv.py --screenshot, capture on the TV and pull the PNG (#364)** · p2 · scripts<br>touches maintainer-only paths: PROMPT.md<br>question: touches maintainer-only paths: PROMPT.md
- [ ] #608 **launcher: support Android 7.0 (minSdk 24) and name an activity for Live TV and tiles** · p2 · launcher<br>Raises the CI APK size gate from 440 KB to 570 KB (desugaring adds ~124 KB). Changes to the size gate and CI need the maintainer.<br>question: Raises the CI APK size gate from 440 KB to 570 KB (desugaring adds ~124 KB). Changes to the size gate and CI need the maintainer.
- [ ] #613 **Launcher: use Lexend for Vietnamese, Outfit has no Vietnamese glyphs** · p2 · launcher<br>Fixes a real rendering bug: the existing values-vi strings fall back to the system font mid-word because Outfit has no Vietnamese glyphs<br>question: Fixes a real rendering bug: the existing values-vi strings fall back to the system font mid-word because Outfit has no Vietnamese glyphs
- [ ] #616 **Cecotec shandao: four more packages, and a TV_INPUT_HARDWARE false positive worth naming** · p2 · tv-list<br>touches maintainer-only paths: tools/disable.sh<br>question: touches maintainer-only paths: tools/disable.sh
- [ ] #617 **docs: some firmware refuses every pm route, plus the TVision Hub note (#577)** · p2 · docs<br>Adds a new stop-and-report rule to PROMPT.md, a sensitive path where prompt and safety changes need the maintainer's decision<br>question: Adds a new stop-and-report rule to PROMPT.md, a sensitive path where prompt and safety changes need the maintainer's decision
- [ ] #618 **Companion bridge: opt-in read-only protocol v1 provider (#597)** · p2 · launcher<br>This adds an API that outside apps can call (a companion ContentProvider plus its protocol). Under the repo rules, that kind of add-on needs a maintainer decision.<br>question: This adds an API that outside apps can call (a companion ContentProvider plus its protocol). Under the repo rules, that kind of add-on needs a maintainer decision.
- [ ] #619 **Home handover: read-only status contract and exact prior-component restore (#601)** · p2 · launcher<br>It changes the Home-safety logic in build-and-install.sh (exact-component restore, chooser refusal, resolve-before-disable), and the rules say that needs the maintainer.<br>question: It changes the Home-safety logic in build-and-install.sh (exact-component restore, chooser refusal, resolve-before-disable), and the rules say that needs the maintainer.
- [ ] #621 **TCL profiles: exact-firmware gate, per-package risk and restore manifest (#603)** · p2 · scripts<br>Adds a second list format (profiles/ plus the 526-line tools/profile.py) next to examples/. Whether the repo wants that is a scope call for the maintainer.<br>question: Adds a second list format (profiles/ plus the 526-line tools/profile.py) next to examples/. Whether the repo wants that is a scope call for the maintainer.
- [ ] #622 **Release artifact: release-key signing config and pinned launcher-release.json verification** · p2 · launcher<br>Publishing a release-signed APK is a maintainer call: it needs the maintainer's key, a release process, and a prebuilt artifact the repo has avoided so far<br>question: Publishing a release-signed APK is a maintainer call: it needs the maintainer's key, a release process, and a prebuilt artifact the repo has avoided so far
- [ ] #623 **Companion bridge: atomic staging, asset streaming and activation (#598)** · p2 · launcher<br>Part of the companion bridge series (#618, #619, #621, #624, #625), which is already on hold while the maintainer decides scope<br>question: Part of the companion bridge series (#618, #619, #621, #624, #625), which is already on hold while the maintainer decides scope
- [ ] #630 **launcher: ask the TV's SDK level before building (minSdk preflight), and answer #576** · p2 · launcher<br>Edits PROMPT.md, a sensitive path: the new line tells the assistant when to refuse the launcher and how to treat APKs built elsewhere, so the maintainer needs to approve it<br>question: Edits PROMPT.md, a sensitive path: the new line tells the assistant when to refuse the launcher and how to treat APKs built elsewhere, so the maintainer needs to approve it
- [ ] #605 **docs: a display density override that comes back as 640 is not a launcher bug (#590)** · p3 · docs<br>touches maintainer-only paths: PROMPT.md<br>question: touches maintainer-only paths: PROMPT.md
- [ ] #624 **Companion: opt-in TV-side theme schedules with local solar/timezone evaluation (#599)** · p3 · launcher<br>This is part of the Companion bridge series (stacked on #618/#623), which is already on hold while the maintainer decides on scope.<br>question: This is part of the Companion bridge series (stacked on #618/#623), which is already on hold while the maintainer decides on scope.
- [ ] #625 **Companion: opt-in private provider credentials with revocation and redaction (#600)** · p3 · launcher<br>This is part of the Companion series stacked on #624, #623 and #618, and all of those are on hold while the maintainer decides on scope<br>question: This is part of the Companion series stacked on #624, #623 and #618, and all of those are on hold while the maintainer decides on scope

<sub>Proposed by maintainer-bot, running on 0G Private Computer (claude-opus-5.5). Nothing happens until a maintainer replies <code>/approve</code>. Commands: <code>/approve</code>, <code>/approve except #N</code>, <code>/merge #N</code>, <code>/close #N</code>, <code>/rework #N</code>, <code>/hold #N</code>.</sub>

</details>

## Dry-run of `/approve except #543` + `hold 608` on that queue

55 PRs selected, 110 actions (nothing sent):

```
[dry-run] merge           #544  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #545  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #548  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #549  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #552  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #553  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #554  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #555  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #556  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #557  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #559  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #567  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #568  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #569  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #570  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #574  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #578  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #579  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #580  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #581  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #582  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #583  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #584  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #585  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #586  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #588  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #591  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #592  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #594  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #596  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #606  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #607  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #609  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #610  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #615  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #620  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #627  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #628  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #629  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #631  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge-with-fix  #547  fix (job A, read/edit only) → test (job B, no secrets) → merge (job C): In the debloat.txt header and the folder README, add that disabling com.google.android.t
[dry-run] merge-with-fix  #551  fix (job A, read/edit only) → test (job B, no secrets) → merge (job C): In examples/README.md, put back the deleted `sanyo-atv-r2/` row (SANYO ATV R2 (SCBC, Rea
[dry-run] merge-with-fix  #558  fix (job A, read/edit only) → test (job B, no secrets) → merge (job C): Resolve against #581: keep #581's ambient_glow (field, config.xml bool, View.GONE handli
[dry-run] merge-with-fix  #575  fix (job A, read/edit only) → test (job B, no secrets) → merge (job C): In launcher/build-and-install.sh, widen the case pattern to `*'version "17"'*|*'version 
[dry-run] merge-with-fix  #587  fix (job A, read/edit only) → test (job B, no secrets) → merge (job C): In examples/README.md, move the '- [Strong LEAP-S3](../docs/devices/strong-leap-s3.md) .
[dry-run] merge-with-fix  #612  fix (job A, read/edit only) → test (job B, no secrets) → merge (job C): Bump the TV/list counts in README.md (and examples/README.md if it has one) by one for t
[dry-run] merge-with-fix  #614  fix (job A, read/edit only) → test (job B, no secrets) → merge (job C): In Config.java, move the existing '/** Reads and parses the overlay; any problem means "
[dry-run] merge-with-fix  #626  fix (job A, read/edit only) → test (job B, no secrets) → merge (job C): In examples/README.md, delete the blank line added after the new TCL BeyondTV AP08 bulle
[dry-run] label           #546  +needs-rework
[dry-run] label           #562  +needs-rework
[dry-run] label           #573  +needs-rework
[dry-run] label           #593  +needs-rework
[dry-run] label           #595  +needs-rework
[dry-run] comment         #544  Thanks @Samreay, this is a careful one. The network and Inputs pills now refresh just after the first frame back on Home, not before it. A cold start still fill
[dry-run] comment         #545  Thank you! This is the first Fire OS 8 TV list here, and the notes in the header are really useful: Alexa voice coming back after every reboot, the two protecte
[dry-run] comment         #546  Thank you for this careful investigation and for the clear write-up of how the STR wake 
```

## Merge-with-fix, job A dry-run (Claude Opus 5.5 on 0G PC)

| PR | maintainer's actual note | bot's fix | proposed edit | validator |
|---|---|---|---|---|
| #251 | On merge: zh-TW is added to locales_config so Android 13+ can set it for the launcher alone. | In the README header, change "14 languages" to "15 languages" so it matches the updated Language list. | README.md: …25 brands &nbsp;·&nbsp; 15 languages &nbsp;… | ok |
| #301 | On merge: fi added to locales_config.xml, so Android 13+ can set Finnish for the launcher alone. | Add <locale android:name="fi"/> to launcher/app/src/main/res/xml/locales_config.xml so Android 13+ can set Fin | launcher/app/src/main/res/xml/locales_config.xml: …    <locale android:name="pt" />     <locale android:name="fi" /> </lo… | ok |
| #399 | On merge: dropped screenshot.png (binary), added the README.md row, the Xiaomi updater is commented out (#322) | Add a `xiaomi-mitv-ansp0/` row to the main README examples table, next to xiaomi-mitv-astp1. Make it short: Xi | README.md: …/ `xiaomi-mitv-ansp0/` / Xiaomi MiTV-ANSP0 (Mi TV 5 Pro, CN firmware) … | README.md: search text found 0 times (needs exactly 1) |
| #392 | On merge: resolved the examples/README.md conflict, added the missing README.md row and trimmed the examples r | Add the tcl-32s5k row to the TV table in the main README.md (matching the examples/README entry, shortened to  | README.md: …/ TCL 32S5K (C06, MediaTek MT9221), EU / Android TV 11 / / TCL 40S5400… | ok |
| #172 | On merge: rebased onto today's Config fields; Finnish and Vietnamese get the greeting format. | Merge after #150 lands, then rebase so only the greeting_name commit is left. Add greeting_with_name to the 2  | no edit (needs a rebase: escalate) | ok |

## Spend

| model | calls | input tokens | output tokens | $ |
|---|---|---|---|---|
| glm-5.3 | 115 | 184,981 | 397,509 | 2.01 |
| glm-5.3-flash | 238 | 671,579 | 812,900 | 0.50 |
| claude-opus-5.5 | 364 | 2,172,016 | 240,313 | 13.49 |
| **total** | | | | **16.01** (cap $25) |
