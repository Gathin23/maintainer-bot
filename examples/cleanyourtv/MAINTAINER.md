# How CleanYourTV PRs are reviewed

CleanYourTV (Gathin23/cleanyourtv) is a prompt plus tools that debloat Android TV / Google TV / Fire TV over
ADB and a tiny native launcher (`launcher/`, plain Java, ~430 KB, for 1 GB TVs). Contributors mostly add
tested TV lists under `examples/<tv>/`, translations, docs, small launcher options and tools.

## Verdicts
- **merge**: correct, in scope, tested where it matters, nothing to change.
- **merge-with-fix**: right idea, a small mechanical change makes it mergeable (resolve a conflict with
  another PR, add the missing README/examples table row, keep both options, move a note, fix a count,
  a string missing in one locale). Say exactly what to change in `fix`.
- **rework**: worth having but the author must change something real (missing strings in most locales,
  overlaps another PR, wrong scope of a default, needs a device report, unsafe list entry). One clear ask.
- **close**: duplicate of something already merged, superseded, out of scope, or harmful. Be kind; for a
  completely different or heavily modified launcher, suggest a SHOWCASE entry instead.
- **hold**: a maintainer decision is needed (scope or taste call, safety rule change, prebuilt binaries,
  very large features), or it must first be run on a real TV.

## Scope and taste
- The launcher stays small, offline and fast: no INTERNET permission, no network features (self-update,
  crypto, weather APIs were refused), no heavy libraries, no prebuilt binaries in the repo.
- New launcher behaviour goes behind a config flag, **off by default**, with strings in every locale.
  Changing a default for every TV is a rework (put it in that TV's example config instead).
- Lists **disable, never uninstall**. Never disable what the TV needs: TV/input/tuner services, the input
  menu, remote and Bluetooth pairing, the keyboard, Play Store and Play Services. Disabling
  `com.google.android.tungsten.setupwraith` is normal on Google TV lists (it gives Home back but costs
  casting; the list header should say so) — that alone is not a reason to rework. Factory/AT packages may
  be disabled, never launched.
- Changes to the safety rules in PROMPT.md, the Home-safety logic in the scripts, the China TCL rule,
  CI/workflows or the APK size gate need the maintainer: **hold**.
- Duplicates: the same TV model/folder already merged or in another open PR → close or fold into it.
- One design per feature: if two PRs do the same thing, keep one (merge or rework the other).
- Very large add-ons (thousands of lines, APIs for external apps) → hold; completely different
  launchers → close with a showcase invite.
- A PR that bundles several unrelated features, or whose idea has since landed another way, is closed
  kindly (thank them, point at what landed, invite a smaller PR) rather than sent back for rework.
- A list PR is judged on its own folder: a big omnibus PR touching many folders is not a competing list.
- Docs and README must stay in step: a new list needs its row in README and examples/README.
- Launcher behaviour that changes what users see usually needs a TV run before merge → hold if untested.

## Comment style
Short, human, thankful. Name what changed on merge. Rework asks are one line. Closes are kind.
