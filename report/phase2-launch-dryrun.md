# Phase 2 dry run: what `/approve` would do on Gathin23/cleanyourtv

Built 2026-10-24 13:05 IST from the live labels and sticky reviews. Read-only: no comment, label, merge or push was made.


**Launch notes (phase2-launch, written by hand after the run).** In the order a real wave acts (closes, then merges
by priority, then merges with a fix), `/approve` today would close #1146 and merge #1257, #1315, #1319, #1336,
#1175, #1307, #1317, #1324, #1325, #1328 and #1341, then **stop at #1353** (its own "Lists, tools and docs" check is
red), so #1360 and the three merges with a fix would wait. `/approve except #1353` acts on all 16 others:
1 close, 12 merges, 3 merges with a fix (#1306, #1340, #1357), every one inside the gate, under the cap of 25.
The fix calls cost about $0.09 each. The counts step on today's main already has work to do: its brand line
becomes Sony 32, Xiaomi 29, Hisense 10 and adds INCLO, KTC and Liberton, the same README change #1359 makes (#1359
stays outside the gate because it also changes a test). So the first counts PR does #1359's README part; merge
#1359 by hand first if its test should land too.

- Open non-draft PRs: 116; with a review at their latest commit: 105; new commits since the review: 0; not reviewed yet: 0
- Queue by suggestion: close 1, hold 55, merge 44, merge-with-fix 4, rework 1
- Outside the wave's paths (left for a maintainer): 33
- main's CI now: success; wave size cap: 25
- `/approve` would act on: 17 PRs (16 would go ahead, 0 skipped, stopped at #1353: checks failing on #1353: Lists, tools and docs)

- README counts on main now: {"tv_models": 260, "brands": 77, "languages": 25, "new_brands": ["Skyworth", "INCLO", "KTC", "Liberton"], "gone_brands": []}

## Would do (16)

- #1146 **close** PRISM+ Q65 Ultra (R10G): disable setupwraith, feedbackconsent and Privacy Sandbo: comment and close: Thanks for grouping the Privacy Sandbox services and keeping the Wi-Fi caution on setupwraith. #1139 already updates thi
- #1175 **merge** docs: document Mi TV 3S input and casting interfaces: merge commit through the API
- #1257 **merge** examples: add Anker Nebula Mars 3 Air projector D2325 (taihang, MediaTek m7332),: merge commit through the API
- #1307 **merge** docs: Coocaa home[0] repair lives in the homepage shim: merge commit through the API
- #1315 **merge** Fix T_Solo: it is the Bluetooth music app, not game centre; make it opt-in: merge commit through the API
- #1317 **merge** SHOWCASE: add Redmi Glass Launcher with Mountain Glass: merge commit through the API
- #1319 **merge** values-zh-rCN: 135 strings, up from 60: merge commit through the API
- #1324 **merge** SHOWCASE: add Premium Minimal Home on Sony KD-55X9000H: merge commit through the API
- #1325 **merge** docs: record Sony KD-55X9000H key-filter and native-volume findings: merge commit through the API
- #1328 **merge** Hisense FFM (songshan): HomeKeyService did bind in a later session: merge commit through the API
- #1336 **merge** examples: add Vu VIBE TV (KONKA bandra, Realtek), Google TV 14: merge commit through the API
- #1341 **merge** SHOWCASE: add local Skyworth launcher fork: merge commit through the API
- #1360 **merge** Showcase: add CleanYourTV Studio: merge commit through the API
- #1306 **merge-with-fix** Add TCL 55L8 (China, x32a0, Android 9): would build bot/merge-1306 with the fix: In examples/tcl-55l8-x32a0-cn/debloat.txt, comment out com.snm.upgrade (the firmware updater) and ad
- #1340 **merge-with-fix** SHOWCASE: add TV Remote + Timer Lock (phone remote over a Cloudflare relay, Sony: would build bot/merge-1340 with the fix: Trim the SHOWCASE.md description cell to one sentence, e.g. "A launcher fork with a phone web remote
- #1357 **merge-with-fix** SHOWCASE: add a Changhong fork with a weather, AQI and prayer-time glance line: would build bot/merge-1357 with the fix: Trim the SHOWCASE.md description cell to one short line (e.g. "A glance line under the clock: weathe

## Would stop the batch (1)

- #1353 **merge** SHOWCASE: Forslag, what is in your own streaming subscriptions (Philips, Android: checks failing on #1353: Lists, tools and docs

## Outside the wave's paths (33)

- #1166 suggests merge: Brightness: darker than 80 % for real, shorter card caption, day pictu: changes addons/brightness/README.md
- #1167 suggests merge: Launcher: an "inputs" app_keys target opens the Inputs menu: changes launcher/app/src/main/java/com/gathin/tvhome/RemoteKeys.java
- #1172 suggests merge: Launcher: glass_style, a quieter focus highlight: changes launcher/app/src/main/java/com/gathin/tvhome/Config.java
- #1173 suggests merge: Launcher: focus_sweep, a light band across the focused tile: changes launcher/app/src/main/java/com/gathin/tvhome/Config.java
- #1184 suggests merge: Launcher: action words as app_keys targets (mute, sleep, recents...): README.md changes outside the table rows
- #1190 suggests merge: Add-on: Quiet Hours: changes addons/README.md
- #1191 suggests merge: Add-on: Remote Access: changes addons/README.md
- #1192 suggests merge: Add-on: AirPlay Status: changes addons/README.md
- #1193 suggests merge: Add-on: Sources: changes addons/README.md
- #1194 suggests merge: Add-on: Smart Home: changes addons/README.md
- #1195 suggests merge: Add-on: Ad Blocking: changes addons/README.md
- #1228 suggests merge: addons: add offline World Clock: changes addons/README.md
- #1234 suggests merge: perf(launcher): release wallpaper bitmap on background memory trim: changes launcher/app/src/main/java/com/gathin/tvhome/MainActivity.java
- #1243 suggests merge: Launcher: orange and red states for wifi_status_color (wifi_status_war: changes launcher/app/src/main/java/com/gathin/tvhome/Config.java
- #1247 suggests merge: Launcher: Home's wallpaper or plain black behind the clock screensaver: changes launcher/app/src/main/java/com/gathin/tvhome/ClockActivity.java
- #1262 suggests merge: Launcher: build-and-install.sh skips a JRE without jlink on macOS (#12: changes launcher/build-and-install.sh
- #1278 suggests merge: tools: build-and-install.sh writes sdk.dir with forward slashes, so Gi: changes launcher/build-and-install.sh
- #1279 suggests merge: addons: add Frigate Wall camera module card: changes addons/README.md
- #1280 suggests merge: addons: add flocking simulation: changes addons/README.md
- #1289 suggests merge: zh: last_opened strings, library pill level with CJK glyphs, no clippe: changes launcher/app/src/main/res/drawable-zh/ic_apps_pill.xml
- #1291 suggests merge-with-fix: Sleep Timer: quick bar for a remote button, bedtime in one press, zh-T: changes addons/sleep-timer/.gitignore
- #1293 suggests merge: Bring a killed key helper back: add, remove, add: changes launcher/app/src/main/java/com/gathin/tvhome/ServiceRepair.java
- #1297 suggests merge: launcher: send the HDMI/AV input intent to live_tv_package first: changes launcher/app/src/main/java/com/gathin/tvhome/MainActivity.java
- #1311 suggests rework: launcher/build-and-install.sh: say how to make tools/venv when it is m: changes launcher/build-and-install.sh
- #1320 suggests merge: docs: the theme recipe bumps the README count and passes TV_HOST: changes tests/test_theme_recipe_count.py
- #1322 suggests merge: README.zh-CN: say where the language lives, not just that it follows t: changes README.zh-CN.md
- #1327 suggests merge: docs: the docs recipe links a new device note from examples/README.md: changes tests/test_docs_notes_recipe_index.py
- #1338 suggests merge: addons: Frigate Glance trusts Frigate's new certificate from Overview,: changes addons/README.md
- #1342 suggests merge: launcher: unit tests for Shamsi.toJalali: changes launcher/app/src/test/java/com/gathin/tvhome/ShamsiTest.java
- #1343 suggests merge: docs: the launcher-switch recipe asks for the switch's screenshot: changes tests/test_launcher_switch_recipe.py
- #1346 suggests merge: tools, tests: drop two unused imports: changes tests/test_b64push_atomic.py
- #1348 suggests merge: docs: the showcase recipe asks for both count lines: changes tests/test_showcase_recipe_count.py
- #1359 suggests merge: README: the brand line counts Sony, Xiaomi and Hisense right and names: changes tests/test_readme_brand_coverage.py

## The queue issue body it would post

````markdown
**Today's queue · 2026-10-24** · 105 PRs with a review at their latest commit, 17 with a proposed action.

Comment here to act (only the repo owner and the allow-list are read):
`/approve` everything with a checkbox · `/approve except #a #b` · `/approve #a #b` only those · `/skip #n` · `/close #n reason` · `/rework #n ask`. Anything else is kept as a note, never an action.

### Merge (13)
- [ ] #1257 examples: add Anker Nebula Mars 3 Air projector D2325 (taihang, MediaTek m7332), Google… (by TiagoAryan) · p2 · Thank you for the careful notes on the Google TV 14 Home quirk: the check of what setupwraith owned before disabling it will save the next Nebula owner a lot of time. This looks ready to go in as…
- [ ] #1315 Fix T_Solo: it is the Bluetooth music app, not game centre; make it opt-in (by aalvii) · p2 · Thanks for tracking down what com.tcl.t_solo really is, with the activity, APK path and launcher label from a real 65Q10M Pro. Making it opt-in is the right call for a Bluetooth speaker feature, so…
- [ ] #1319 values-zh-rCN: 135 strings, up from 60 (by symi-daguo) · p2 · Thank you for completing Simplified Chinese and testing it on two zh-CN devices, a Hisense and a Fengmi. The module cards, wallpapers and quick settings now read in Chinese too, so this looks ready…
- [ ] #1336 examples: add Vu VIBE TV (KONKA bandra, Realtek), Google TV 14 (by SuperSecureHuman) · p2 · Thank you for the careful notes on this set's quirks, especially how the Realtek key handler sends the YouTube and Netflix buttons to launcherx and why key_filter is an all-or-nothing trade. This…
- [ ] #1175 docs: document Mi TV 3S input and casting interfaces (by sofarx) · p3 · Thanks for the careful Mi TV 3S 48 note, especially the detail that the `input` extra is an integer and the block/unblock undo that comes with it. It's a small, accurate device note that fits…
- [ ] #1307 docs: Coocaa home(0) repair lives in the homepage shim (by VincentYe123) · p3 · Thanks for tracking down the home[0] / home[1] overwrite and moving the repair into coocaa-home-shim 2.1, which keeps the launcher untouched. The updated notes and showcase row read clearly and look…
- [ ] #1317 SHOWCASE: add Redmi Glass Launcher with Mountain Glass (by harshsingh0930) · p3 · Thanks for the Mountain Glass fork, and for the real-TV screenshots and the clear notes on data use. The row and the count updates look ready for the showcase as they are.
- [ ] #1324 SHOWCASE: add Premium Minimal Home on Sony KD-55X9000H (by Lzchyi) · p3 · Thank you for the careful Sony KD-55X9000H testing notes and for keeping the fork offline. This showcase row looks ready to go as it is.
- [ ] #1325 docs: record Sony KD-55X9000H key-filter and native-volume findings (by Lzchyi) · p3 · Thank you for the simultaneous kernel/callback capture: it shows clearly why held Volume breaks while the key helper is bound. This looks ready to merge as a device note, and it's good that the…
- [ ] #1328 Hisense FFM (songshan): HomeKeyService did bind in a later session (by nthnle) · p3 · Thanks for retesting and for correcting "never bound" to what was actually seen. It's a small comment-only fix to the Hisense FFM notes and looks good to merge as is.
- [ ] #1341 SHOWCASE: add local Skyworth launcher fork (by abhishek00235) · p3 · Thanks for the on-device theme picker and for the clear note that the Pixabay key stays on the TV and out of the source. This fits the showcase well as it is; once it has run on the Skyworth set, a…
- [ ] #1353 SHOWCASE: Forslag, what is in your own streaming subscriptions (Philips, Android TV 11) (by modist) · p3 · Thanks for following up on #1269 with a tidy row, the Philips brand-index entry and the updated count. This looks ready to merge as it is.
- [ ] #1360 Showcase: add CleanYourTV Studio (by dazdenii) · p3 · Thanks for CleanYourTV Studio. A local-only studio that drives the existing theme.sh, tv.py and check.py is a great fit for the showcase, and the row and count bump look ready to go in as they are.

### Merge with a small fix (3)
- [ ] #1306 Add TCL 55L8 (China, x32a0, Android 9) (by afanty2021) · p2 · fix: In examples/tcl-55l8-x32a0-cn/debloat.txt, comment out com.snm.upgrade (the firmware updater) and add a header note saying it stays enabled on purpose.
- [ ] #1340 SHOWCASE: add TV Remote + Timer Lock (phone remote over a Cloudflare relay, Sony BRAVIA… (by ptrinh) · p3 · fix: Trim the SHOWCASE.md description cell to one sentence, e.g. "A launcher fork with a phone web remote over a Cloudflare relay (QR pairing, live view, keyboard, Lock TV with a PIN timer, screen…
- [ ] #1357 SHOWCASE: add a Changhong fork with a weather, AQI and prayer-time glance line (by bayhaqy) · p3 · fix: Trim the SHOWCASE.md description cell to one short line (e.g. "A glance line under the clock: weather and AQI, next prayer countdown, RAM and storage; adds INTERNET; crimson glass-dock theme"), keep…

### Close (kindly) (1)
- [ ] #1146 PRISM+ Q65 Ultra (R10G): disable setupwraith, feedbackconsent and Privacy Sandbox services (by dineshalphaque) · p3 · why: Thanks for grouping the Privacy Sandbox services and keeping the Wi-Fi caution on setupwraith. #1139 already updates this PRISM+ list, so the suggestion is to add these entries and your Hey Google…

### For a maintainer: outside the wave's paths (33)
_Not part of `/approve`; only `/close #n` or `/rework #n` moves these._
- #1166 Brightness: darker than 80 % for real, shorter card caption, day picture restore checked (by maxhayim) · p2 · suggests merge · changes addons/brightness/README.md
- #1167 Launcher: an "inputs" app_keys target opens the Inputs menu (by LECOQQ) · p2 · suggests merge · changes launcher/app/src/main/java/com/gathin/tvhome/RemoteKeys.java
- #1172 Launcher: glass_style, a quieter focus highlight (by LECOQQ) · p2 · suggests merge · changes launcher/app/src/main/java/com/gathin/tvhome/Config.java
- #1173 Launcher: focus_sweep, a light band across the focused tile (by LECOQQ) · p2 · suggests merge · changes launcher/app/src/main/java/com/gathin/tvhome/Config.java
- #1184 Launcher: action words as app_keys targets (mute, sleep, recents...) (by ScaryFr92) · p2 · suggests merge · README.md changes outside the table rows
- #1190 Add-on: Quiet Hours (by maxhayim) · p2 · suggests merge · changes addons/README.md
- #1191 Add-on: Remote Access (by maxhayim) · p2 · suggests merge · changes addons/README.md
- #1192 Add-on: AirPlay Status (by maxhayim) · p2 · suggests merge · changes addons/README.md
- #1193 Add-on: Sources (by maxhayim) · p2 · suggests merge · changes addons/README.md
- #1194 Add-on: Smart Home (by maxhayim) · p2 · suggests merge · changes addons/README.md
- #1195 Add-on: Ad Blocking (by maxhayim) · p2 · suggests merge · changes addons/README.md
- #1228 addons: add offline World Clock (by SaviorOneZero) · p2 · suggests merge · changes addons/README.md
- #1234 perf(launcher): release wallpaper bitmap on background memory trim (by maxsonferovante) · p2 · suggests merge · changes launcher/app/src/main/java/com/gathin/tvhome/MainActivity.java
- #1243 Launcher: orange and red states for wifi_status_color (wifi_status_warnings) (by benny117) · p2 · suggests merge · changes launcher/app/src/main/java/com/gathin/tvhome/Config.java
- #1247 Launcher: Home's wallpaper or plain black behind the clock screensaver (clock_wallpaper,… (by benny117) · p2 · suggests merge · changes launcher/app/src/main/java/com/gathin/tvhome/ClockActivity.java
- #1262 Launcher: build-and-install.sh skips a JRE without jlink on macOS (#1255) (by jammies99) · p2 · suggests merge · changes launcher/build-and-install.sh
- #1278 tools: build-and-install.sh writes sdk.dir with forward slashes, so Git Bash on Windows… (by starlord-93) · p2 · suggests merge · changes launcher/build-and-install.sh
- #1279 addons: add Frigate Wall camera module card (by marceloglacial) · p2 · suggests merge · changes addons/README.md
- #1280 addons: add flocking simulation (by maxsonferovante) · p2 · suggests merge · changes addons/README.md
- #1289 zh: last_opened strings, library pill level with CJK glyphs, no clipped CJK tile names (by NewPlayer0213) · p2 · suggests merge · changes launcher/app/src/main/res/drawable-zh/ic_apps_pill.xml
- #1291 Sleep Timer: quick bar for a remote button, bedtime in one press, zh-TW strings (by NewPlayer0213) · p2 · suggests merge-with-fix · changes addons/sleep-timer/.gitignore
- #1293 Bring a killed key helper back: add, remove, add (by nthnle) · p2 · suggests merge · changes launcher/app/src/main/java/com/gathin/tvhome/ServiceRepair.java
- #1297 launcher: send the HDMI/AV input intent to live_tv_package first (by PierreKerschgens) · p2 · suggests merge · changes launcher/app/src/main/java/com/gathin/tvhome/MainActivity.java
- #1311 launcher/build-and-install.sh: say how to make tools/venv when it is missing (#1142) (by Gathin23) · p2 · suggests rework · changes launcher/build-and-install.sh
- #1338 addons: Frigate Glance trusts Frigate's new certificate from Overview, says why a card… (by NickLD) · p2 · suggests merge · changes addons/README.md
- #1343 docs: the launcher-switch recipe asks for the switch's screenshot (by xbsheng) · p2 · suggests merge · changes tests/test_launcher_switch_recipe.py
- #1348 docs: the showcase recipe asks for both count lines (by xbsheng) · p2 · suggests merge · changes tests/test_showcase_recipe_count.py
- #1359 README: the brand line counts Sony, Xiaomi and Hisense right and names KTC, INCLO and… (by xbsheng) · p2 · suggests merge · changes tests/test_readme_brand_coverage.py
- #1320 docs: the theme recipe bumps the README count and passes TV_HOST (by xbsheng) · p3 · suggests merge · changes tests/test_theme_recipe_count.py
- #1322 README.zh-CN: say where the language lives, not just that it follows the TV (by symi-daguo) · p3 · suggests merge · changes README.zh-CN.md
- #1327 docs: the docs recipe links a new device note from examples/README.md (by xbsheng) · p3 · suggests merge · changes tests/test_docs_notes_recipe_index.py
- #1342 launcher: unit tests for Shamsi.toJalali (by silpdev) · p3 · suggests merge · changes launcher/app/src/test/java/com/gathin/tvhome/ShamsiTest.java
- #1346 tools, tests: drop two unused imports (by silpdev) · p3 · suggests merge · changes tests/test_b64push_atomic.py

### Needs a maintainer (55)
_Not part of `/approve`; only `/close #n` or `/rework #n` moves these._
- #39 Launcher: pre-render banners to HARDWARE bitmaps, cache tile entries & keys (by leovvay) · question: the bot asks for a maintainer decision
- #488 Launcher: hold OK to reorder, Italian, settings applied on Home; examples: TCL 43P7K (by AngelusGi) · question: the same product may already be on main (docs/devices/tcl-55p71b-g09-key-repeat.md, tcl-55p7k, tcl-55p8ls): fold in or a separate model? (confidence 0.72 < 0.75). The bot's own suggestion would be:…
- #566 Check PowerShell transport failures and recover failed Home handovers (by am-tmac) · question: changes tools/disable.ps1, tools/restore.ps1: the maintainer decides
- #686 examples: add Xiaomi Mi TV 3S 48 (hancock) list and device notes (by peekewang) · question: a list disables remote-pairing or input packages: com.sohu.inputmethod.sogou.tv. The bot's own suggestion would be: merge with a small fix
- #800 Add Sony BRAVIA 4K VH21, EU firmware (by m-brakni) · question: confidence 0.62 is below 0.65. The bot's own suggestion would be: a few changes first
- #836 launcher: lunar_date, the Vietnamese / Chinese lunisolar date under the date (by vgscity) · question: changes 243 lines in launcher/, more than a small switch. The bot's own suggestion would be: merge
- #864 Launcher: dock_scroll, one horizontal row of every app at the bottom (by Sumyabazar1) · question: confidence 0.60 is below 0.75. The bot's own suggestion would be: merge
- #1085 examples: add TCL G08_4K_GB (Smart TV Pro), Google TV 14, zh-TW firmware (by tmrsm) · question: the same product may already be on main (docs/devices/tcl-75qm751g-qm7.md, tcl-55c745, tcl-55c7k-uk): fold in or a separate model? (confidence 0.62 < 0.75). The bot's own suggestion would be: a few…
- #1088 examples: google-chromecast-gtv-4k dock config and ADB notes (by tmrsm) · question: confidence 0.50 is below 0.65. The bot's own suggestion would be: a few changes first
- #1092 disable.sh/disable.ps1/check.py: keep the apps that open the inputs and Settings (by vgscity) · question: changes tools/disable.ps1, tools/disable.sh: the maintainer decides
- #1113 Launcher: add dock_band and focus_subtle switches (by REGT-URRED) · question: confidence 0.62 is below 0.75. The bot's own suggestion would be: merge with a small fix
- #1114 themes: add retro, a black invisible-dock theme with time-of-day wallpapers (by REGT-URRED) · question: confidence 0.55 is below 0.65. The bot's own suggestion would be: merge with a small fix
- #1117 Launcher: wallpaper_crossfade, fade between rotating pictures (by Zuo-Hang) · question: confidence 0.60 is below 0.65. The bot's own suggestion would be: a few changes first
- #1147 fix(settings): treat CTS stub settings activities as missing to fall back to vendor… (by r3ha) · question: confidence 0.62 is below 0.65. The bot's own suggestion would be: a few changes first
- #1148 examples: TCL 43A30 (Indonesia), G09 Google TV 12 (by monmonsky) · question: the same product may already be on main (tcl-g09-google-tv): fold in or a separate model? (confidence 0.72 < 0.75). The bot's own suggestion would be: a few changes first
- #1168 Launcher: open package-name app launches (market://launch?id=…) after launcherx is… (by kylerw) · question: changes the launcher's manifest (activity) (confidence 0.78 < 0.85). The bot's own suggestion would be: merge
- #1170 tools: update the launcher from a local release tag (by lionlev21) · question: the bot asks for a maintainer decision
- #1177 addons/restart: restart the TV from the remote (by JemyChao) · question: second reviewer: "Its README has a Permissions heading; addons/README.md gets an index row; the author maintains it." (Checklist for this kind of PR). Compare also "A new list needs its row in…
- #1196 Add-on: Corner Player (by maxhayim) · question: second reviewer: The add-on fetches camera/playlist streams (RTSP/HLS) and playlist URLs over the network from within the add-on, which is fine per the rule \"Network access is allowed in an add-on…
- #1206 tools: add validated ZIP transport for folder themes (by DipsySu) · question: confidence 0.60 is below 0.65. The bot's own suggestion would be: merge
- #1209 Launcher: offer App info only where the TV has an App info page (#1202) (by fgarciag97) · question: changes the launcher's manifest (other) (confidence 0.80 < 0.85). The bot's own suggestion would be: merge
- #1211 docs: Wanbo T6R Max projector runs network ADB on port 5877, not 5555 (by ehles) · question: changes PROMPT.md: the maintainer decides
- #1215 Add-on: Kids Mode (by maxhayim) · question: the bot asks for a maintainer decision
- #1216 tools/manage.py: add-ons, themes and switches in one place, installed the creator's way (by maxhayim) · question: confidence 0.60 is below 0.65. The bot's own suggestion would be: merge
- #1221 addons: Up next, your Stremio shows (Continue watching and Coming next) (by quicodomingo) · question: the bot asks for a maintainer decision
- #1233 Launcher: open_on_start_choice, an Open on start app picked in Launcher settings (by devesh760b) · question: confidence 0.65 is below 0.75. The bot's own suggestion would be: merge
- #1235 feat(launcher): add Apple Glass focus anticipation & multi-layer depth effects (by bhaskarvilles) · question: a bigger launcher change (323 lines) the bot would send back: rework or a home in the showcase/addons is the maintainer's call. The bot's own suggestion would be: a few changes first
- #1241 Launcher: build-and-install stops the instance restarted mid-update (#1101) (by SiirGustav) · question: changes the Home/launch path (build-and-install.ps1, build-and-install.sh), which usually needs a run on a real TV (confidence 0.72 < 0.85). The bot's own suggestion would be: merge
- #1242 Launcher: consume_volume_keys, for firmware that doubles a filtered volume key (#1100) (by SiirGustav) · question: changes the Home/launch path (HomeKeyService.java), which usually needs a run on a real TV (confidence 0.75 < 0.85). The bot's own suggestion would be: merge
- #1244 Launcher: apps as round logo buttons in the top bar (top_bar_apps) (by benny117) · question: confidence 0.72 is below 0.75. The bot's own suggestion would be: merge
- #1245 Launcher: every app in one sideways-scrolling row (single_row, dock_band_all) (by benny117) · question: confidence 0.72 is below 0.75. The bot's own suggestion would be: merge
- #1246 Launcher: hide the greeting, full-white date (show_greeting, header_white) (by benny117) · question: confidence 0.72 is below 0.75. The bot's own suggestion would be: merge with a small fix
- #1259 docs: add AFTKRT Fire OS 8.1.7.4 owner notes (#1256) (by wojciechsacewicz) · question: confidence 0.60 is below 0.65. The bot's own suggestion would be: a few changes first
- #1267 themes: add ambient rotating landscape theme (by audiedv) · question: a second model disagrees (theme). The bot's own suggestion would be: merge
- #1272 SHOWCASE: pin rows to a tag or commit, declare sensitive capabilities, add a pre-install… (by daniel-villada) · question: the bot asks for a maintainer decision
- #1284 Launcher: optional Hebrew dates and Jewish holiday greetings (by lionlev21) · question: changes 274 lines in launcher/, more than a small switch. The bot's own suggestion would be: merge
- #1287 RemoteKeys: hold fires after HOLD_MS, one launch per press, app_keys activity targets (by NewPlayer0213) · question: confidence 0.62 is below 0.75. The bot's own suggestion would be: merge
- #1288 glass_haze theme key, and Motion.focus for the focus spring (by NewPlayer0213) · question: confidence 0.70 is below 0.75. The bot's own suggestion would be: merge
- #1290 Brightness: quick bar for a remote button, night mode in one press (by NewPlayer0213) · question: second reviewer: "A stacked series (one PR built on another) is not a duplicate." / addon checklist: "Never touches launcher/ ... judge it on its merits" — but the PR's own description states it…
- #1308 examples: the undo for five lists passes the stock launcher each one disables (by xbsheng) · question: edits a TV list that is already on main (confidence 0.78 < 0.85). The bot's own suggestion would be: merge
- #1309 launcher: uniform icon tiles, off unless a theme asks (by VincentYe123) · question: confidence 0.65 is below 0.75. The bot's own suggestion would be: merge
- #1312 docs: a disabled mitv.service takes the Xiaomi Settings app down on CN firmware (#1310) (by xbsheng) · question: edits a TV list that is already on main (confidence 0.78 < 0.85). The bot's own suggestion would be: merge
- #1313 Settings menu: offer the vendor settings app as "Native settings" (by hanzg-han) · question: confidence 0.60 is below 0.75. The bot's own suggestion would be: merge with a small fix
- #1316 addons: Bedtime Lock, a code lock for the TV during the hours you choose (by justin-newman) · question: confidence 0.60 is below 0.65. The bot's own suggestion would be: merge
- #1318 examples: add README for Skyworth SWTV-22AE-FHD (umeda), Android 11/Google TV (by y-amit125) · question: edits a TV list that is already on main (confidence 0.62 < 0.85). The bot's own suggestion would be: merge with a small fix
- #1323 examples(mitv-mooq0): Input button (MEDIA_RECORD) is set via input_key_keycodes (by silpdev) · question: edits a TV list that is already on main (confidence 0.75 < 0.85). The bot's own suggestion would be: merge with a small fix
- #1330 examples: add Sony BRAVIA KDL-43W950D (SVP-DTV15), Android TV 8.0.0, India (by vinaybedre) · question: a list disables remote-pairing or input packages: com.google.android.inputmethod.japanese. The bot's own suggestion would be: merge
- #1332 docs: the hengshan volume trade is a third unit, soundbar or not (#1326) (by xbsheng) · question: edits a TV list that is already on main (confidence 0.65 < 0.85). The bot's own suggestion would be: merge
- #1337 Launcher: Off and App details on chosen apps (by callmejm) · question: confidence 0.60 is below 0.75. The bot's own suggestion would be: merge
- #1344 docs(tcl-g09): add AS24 India verification, 0.5x animation scaling, and RAM optimization… (by amanjolhe) · question: edits a TV list that is already on main (confidence 0.62 < 0.85). The bot's own suggestion would be: merge with a small fix
- #1345 SHOWCASE: refresh LG webOS editions and installer description (by Razdva122) · question: confidence 0.60 is below 0.65. The bot's own suggestion would be: a few changes first
- #1349 Add-on: TV Remote, a phone remote from anywhere through your own Cloudflare relay (by ptrinh) · question: the bot asks for a maintainer decision
- #1356 addons: TV Care (RAM and disk rings, network, Clean RAM, recent apps with Close) (by bayhaqy) · question: confidence 0.60 is below 0.65. The bot's own suggestion would be: merge
- #1358 addons: Stay Awake, a screen wake while media plays (by callmejm) · question: a second model disagrees (merge-with-fix). The bot's own suggestion would be: a few changes first
- #1361 SHOWCASE: add stillOS (by maximfakel) · question: confidence 0.60 is below 0.65. The bot's own suggestion would be: merge with a small fix

<details><summary>Not in today's queue</summary>

- Changes already asked, waiting for the author: #751, #752, #813, #1132, #1210
- Labelled on-hold: #446, #546, #565, #812, #844, #1153

</details>

<sub>Built by maintainer-bot from its reviews · runs on [0G Private Computer](https://pc.0g.ai)</sub>

<!-- mb-queue {"date":"2026-10-24","items":{"1166":{"sha":"a3b1ddefceff","v":"merge","o":1},"1167":{"sha":"3438fe1c7c09","v":"merge","o":1},"1172":{"sha":"2a5a858b35e1","v":"merge","o":1},"1173":{"sha":"a9431714488d","v":"merge","o":1},"1184":{"sha":"21de338a169a","v":"merge","o":1},"1190":{"sha":"2e6c9eb413d3","v":"merge","o":1},"1191":{"sha":"1bcf92cb5a17","v":"merge","o":1},"1192":{"sha":"6236660d579e","v":"merge","o":1},"1193":{"sha":"26da8fdee55e","v":"merge","o":1},"1194":{"sha":"cd9729d4a1da","v":"merge","o":1},"1195":{"sha":"2b494772f5c1","v":"merge","o":1},"1228":{"sha":"09aa2dafba75","v":"merge","o":1},"1234":{"sha":"b32236486237","v":"merge","o":1},"1243":{"sha":"caf9880981e2","v":"merge","o":1},"1247":{"sha":"c73015b8385d","v":"merge","o":1},"1257":{"sha":"559fdb788619","v":"merge"},"1262":{"sha":"320c6422a0ce","v":"merge","o":1},"1278":{"sha":"da6481c55d97","v":"merge","o":1},"1279":{"sha":"c46b343ccee0","v":"merge","o":1},"1280":{"sha":"ee3a0bebe1b4","v":"merge","o":1},"1289":{"sha":"1ffe86c723d0","v":"merge","o":1},"1291":{"sha":"23f9be731a60","v":"merge-with-fix","o":1},"1293":{"sha":"fa7279e9b657","v":"merge","o":1},"1297":{"sha":"812a0e1e0e9f","v":"merge","o":1},"1306":{"sha":"2281ee0b806e","v":"merge-with-fix"},"1311":{"sha":"71888eea2b0f","v":"rework","o":1},"1315":{"sha":"eb697ec8492a","v":"merge"},"1319":{"sha":"8f75ec0a89bb","v":"merge"},"1336":{"sha":"aa8b04bf6ae3","v":"merge"},"1338":{"sha":"ce12933b46b7","v":"merge","o":1},"1343":{"sha":"e25a90e99df3","v":"merge","o":1},"1348":{"sha":"8fc54b1ad331","v":"merge","o":1},"1359":{"sha":"3d1a985f54a1","v":"merge","o":1},"1146":{"sha":"b8715e8e64dc","v":"close"},"1175":{"sha":"b6d08dfcc858","v":"merge"},"1307":{"sha":"bdcb4040b5cf","v":"merge"},"1317":{"sha":"06874da30ce5","v":"merge"},"1320":{"sha":"15d6c3034948","v":"merge","o":1},"1322":{"sha":"bb0b94559aa5","v":"merge","o":1},"1324":{"sha":"b482c12b7836","v":"merge"},"1325":{"sha":"e1fbd3c18ad2","v":"merge"},"1327":{"sha":"c2ae0b7e3e58","v":"merge","o":1},"1328":{"sha":"291f6a5e799c","v":"merge"},"1340":{"sha":"98b7c0302b67","v":"merge-with-fix"},"1341":{"sha":"c4320f0f5f60","v":"merge"},"1342":{"sha":"da07a6b054ce","v":"merge","o":1},"1346":{"sha":"f359f7de9f1c","v":"merge","o":1},"1353":{"sha":"d07065b540b3","v":"merge"},"1357":{"sha":"4c415d657445","v":"merge-with-fix"},"1360":{"sha":"855c782cb2c3","v":"merge"},"39":{"sha":"22ae9e3adcd1","v":"hold"},"488":{"sha":"46afc2857ddc","v":"hold"},"566":{"sha":"569940cec5c6","v":"hold"},"686":{"sha":"d0f5b21e6eb9","v":"hold"},"800":{"sha":"85e77231377a","v":"hold"},"836":{"sha":"f9f10cb68fa7","v":"hold"},"864":{"sha":"7526d3a007f7","v":"hold"},"1085":{"sha":"fd23804065cb","v":"hold"},"1088":{"sha":"433edb8134f4","v":"hold"},"1092":{"sha":"31937a6cb3f6","v":"hold"},"1113":{"sha":"9323581cdce2","v":"hold"},"1114":{"sha":"e3de40cc64f5","v":"hold"},"1117":{"sha":"efb71cfd46da","v":"hold"},"1147":{"sha":"9342e6b8c89c","v":"hold"},"1148":{"sha":"b671a0c35873","v":"hold"},"1168":{"sha":"2141d052a853","v":"hold"},"1170":{"sha":"09a030e17c7e","v":"hold"},"1177":{"sha":"8955ff7ddccc","v":"hold"},"1196":{"sha":"6e60b2ccda5f","v":"hold"},"1206":{"sha":"3307a145c117","v":"hold"},"1209":{"sha":"7413402ea8fd","v":"hold"},"1211":{"sha":"d74b63061e30","v":"hold"},"1215":{"sha":"3028c113887e","v":"hold"},"1216":{"sha":"2b62fb6a68a2","v":"hold"},"1221":{"sha":"931c250e3630","v":"hold"},"1233":{"sha":"ec9ad6094943","v":"hold"},"1235":{"sha":"dcc5a84b6bcb","v":"hold"},"1241":{"sha":"397a500a97d2","v":"hold"},"1242":{"sha":"45be1e148080","v":"hold"},"1244":{"sha":"0b020955d63f","v":"hold"},"1245":{"sha":"967ea8d7f0ac","v":"hold"},"1246":{"sha":"7d914f85241f","v":"hold"},"1259":{"sha":"e90df8e9f2a3","v":"hold"},"1267":{"sha":"893cc08b467a","v":"hold"},"1272":{"sha":"b1ae832b344a","v":"hold"},"1284":{"sha":"8daab7c20b0a","v":"hold"},"1287":{"sha":"a16993d4aac5","v":"hold"},"1288":{"sha":"08fae92275b9","v":"hold"},"1290":{"sha":"930fdd47512d","v":"hold"},"1308":{"sha":"38cd517bc4c5","v":"hold"},"1309":{"sha":"cd8aa4995b52","v":"hold"},"1312":{"sha":"072bada39cf5","v":"hold"},"1313":{"sha":"7ad1e09e9312","v":"hold"},"1316":{"sha":"d2c533e189d4","v":"hold"},"1318":{"sha":"1814ddd20075","v":"hold"},"1323":{"sha":"53eb8cfb815d","v":"hold"},"1330":{"sha":"c59cd7a15b34","v":"hold"},"1332":{"sha":"bec19d42027f","v":"hold"},"1337":{"sha":"68ba359d2f20","v":"hold"},"1344":{"sha":"5c006aea52b0","v":"hold"},"1345":{"sha":"dcaa412225ca","v":"hold"},"1349":{"sha":"b93c29d2b05e","v":"hold"},"1356":{"sha":"58fd9f9e5b20","v":"hold"},"1358":{"sha":"e63f479086b4","v":"hold"},"1361":{"sha":"3a623787db84","v":"hold"}}} -->
````
