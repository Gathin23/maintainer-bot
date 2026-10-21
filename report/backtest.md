# maintainer-bot backtest on Gathin23/cleanyourtv

Generated locally, nothing posted to GitHub. All model calls went through the 0G Private Computer router.

## Dataset

- **497 decided community PRs** (the maintainer's own PRs excluded), replayed in the order they were decided.
- Truth = what actually happened: merge 272, merge-with-fix 102, close 76, rework 26, hold 21.
  merge-with-fix = merged with an 'On merge: …' note in the merge commit; rework / hold = the open PR's current label.
- Snapshot = the PR as merged (merge commit's second parent) or its last commit before the decision. Commit dates are author-set, so a few reworked PRs may show a later push.
- Memory = up to 8 similar PRs decided **earlier** (never the PR itself, never later decisions), with the maintainer's merge note or comment as the reason.
- Stratified sample of 120 for model comparison (Claude Opus 5.5 ran on the first 100 of it); Round L = PRs #543+ (decided today).

## Headline (rules v2)

### Claude Opus 5.5 · 100-PR sample

- PRs judged: **5** (8 failed calls not counted)
- Exact agreement with the maintainer: **40%**
- Agreement treating merge and merge-with-fix as one: **60%**
- The bot decided on its own in 100% of PRs; when it did, it agreed **60%** (merge family). The rest went to the maintainer as 'hold'.
- Model alone, before the deterministic overrides: 60% (merge family)
- Safety misses (bot says merge, maintainer closed/reworked/held): **0**
- Spend: $6.90 total, $1.380 per PR

| truth ↓ / bot → | merge | merge-with-fix | rework | close | hold | n |
|---|---|---|---|---|---|---|
| **merge** | 2 | 1 | 0 | 0 | 0 | 3 |
| **merge-with-fix** | 0 | 0 | 0 | 0 | 0 | 0 |
| **rework** | 0 | 0 | 0 | 0 | 0 | 0 |
| **close** | 0 | 0 | 1 | 0 | 0 | 1 |
| **hold** | 0 | 0 | 1 | 0 | 0 | 1 |

| class | n | recall | precision |
|---|---|---|---|
| merge | 3 | 67% | 100% |
| merge-with-fix | 0 | – | 0% |
| rework | 0 | – | 0% |
| close | 1 | 0% | – |
| hold | 1 | 0% | – |

### Claude Opus 5.5 · Round L (today, PRs #543+)

- PRs judged: **5** (9 failed calls not counted)
- Exact agreement with the maintainer: **40%**
- Agreement treating merge and merge-with-fix as one: **60%**
- The bot decided on its own in 100% of PRs; when it did, it agreed **60%** (merge family). The rest went to the maintainer as 'hold'.
- Model alone, before the deterministic overrides: 60% (merge family)
- Safety misses (bot says merge, maintainer closed/reworked/held): **2**
- Spend: $6.90 total, $1.380 per PR

| truth ↓ / bot → | merge | merge-with-fix | rework | close | hold | n |
|---|---|---|---|---|---|---|
| **merge** | 2 | 1 | 0 | 0 | 0 | 3 |
| **merge-with-fix** | 0 | 0 | 0 | 0 | 0 | 0 |
| **rework** | 0 | 0 | 0 | 0 | 0 | 0 |
| **close** | 2 | 0 | 0 | 0 | 0 | 2 |
| **hold** | 0 | 0 | 0 | 0 | 0 | 0 |

| class | n | recall | precision |
|---|---|---|---|
| merge | 3 | 67% | 50% |
| merge-with-fix | 0 | – | 0% |
| rework | 0 | – | – |
| close | 2 | 0% | – |
| hold | 0 | – | – |

Safety misses:
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

✅ 4 · 🔧 1 · ↩️ 0 · ❌ 0 · 🤔 0

### ✅ Merge (4)
- [ ] #591 **Remote keys: map app buttons by scancode** · p2 · launcher<br>Opt-in addition to the existing app_keys config: only takes effect when scan: entries are set, and old keycode entries parse exactly as before
- [ ] #627 **Launcher: Portuguese date on two lines next to the clock** · p2 · launcher<br>Override for the Portuguese locale only, using the same mechanism as the German fix (#276): date_single_line=false plus a two-line date_format_home
- [ ] #628 **examples: add Xiaomi MiTV-ASTP0 (mulan, L55M7-EA), China firmware** · p2 · tv-list<br>New, device-tested list in its own folder (xiaomi-mitv-astp0); it doesn't duplicate any existing list
- [ ] #629 **SHOWCASE: add freeTV** · p3 · showcase<br>A heavily changed fork with network features belongs in SHOWCASE, which is where we pointed earlier launcher PRs like #591, #613 and #627

### 🔧 Merge with a small fix (1)
- [ ] #626 **docs: record TCL BeyondTV AP08 setup and verification** · p3 · docs<br>Docs-only device note for a new firmware (AP08), linked from the existing BeyondTV and RT2851 examples; it is not a duplicate list<br>fix: In examples/README.md, delete the blank line added after the new TCL BeyondTV AP08 bullet so it sits directly above the Sony XR-75X91K bullet in the same list.

<sub>Proposed by maintainer-bot, running on 0G Private Computer (claude-opus-5.5). Nothing happens until a maintainer replies <code>/approve</code>. Commands: <code>/approve</code>, <code>/approve except #N</code>, <code>/merge #N</code>, <code>/close #N</code>, <code>/rework #N</code>, <code>/hold #N</code>.</sub>

</details>

## Dry-run of `/approve except #543` + `hold 608` on that queue

5 PRs selected, 10 actions (nothing sent):

```
[dry-run] merge           #591  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #627  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #628  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge           #629  --no-ff merge through the queue, after CI on the merged tree
[dry-run] merge-with-fix  #626  fix (job A, read/edit only) → test (job B, no secrets) → merge (job C): In examples/README.md, delete the blank line added after the new TCL BeyondTV AP08 bulle
[dry-run] comment         #591  Thanks @wouterdamman, this is a really useful fix. Sony remotes sending YouTube, Prime and Disney+ all as keycode 196 is exactly the case keycode-only mapping c
[dry-run] comment         #626  Thanks for the careful AP08 report. It's very useful to have the HOME handover, the input services and the limits of the test written down this clearly. On merg
[dry-run] comment         #627  Thanks @FCardeira! This is a clean fix that works the same way as the German one. In Portuguese the home date now shows on two lines ("TERÇA-FEIRA / 20 DE OUTUB
[dry-run] comment         #628  Thanks! This merges the MiTV-ASTP0 (mulan / L55M7-EA) list, with its rows in README and examples/README. The notes on the remote relay loop, keeping com.mitv.tv
[dry-run] comment         #629  Thanks @kienmai160598! The tvctl CLI with undoable debloat and the Material 3 Expressive redesign look great, and SHOWCASE is the right home for a fork that goe
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
| glm-5.3 | 33 | 49,591 | 96,218 | 0.49 |
| glm-5.3-flash | 76 | 197,352 | 239,410 | 0.15 |
| claude-opus-5.5 | 197 | 1,164,217 | 130,766 | 7.27 |
| **total** | | | | **7.91** (cap $25) |
