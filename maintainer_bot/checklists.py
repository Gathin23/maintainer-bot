"""PR types and a short checklist per type, put in the prompt so the model checks the right things."""
from __future__ import annotations

CHECKLISTS = {
    "tv-list": """- One TV model per folder under examples/<brand-model>/ with debloat.txt (and notes if needed).
- Not a duplicate: the folder or the same model/firmware is not already on main or in another open PR
  (if it is: close, or fold the notes into the existing list).
- Disables, never uninstalls; no protected packages (TV/input/tuner, keyboard, Bluetooth, Play Store/Services).
- The folder has a tv.json (tv, os, brand, notes): the README TV tables are generated from it, so a list PR
  never needs README rows, and rows an older PR added move into its tv.json on merge
  (if tv.json is missing → merge-with-fix: add examples/<folder>/tv.json).
- A device report without a list, or a list never run on the TV, is weaker: hold only if it changes rules.""",
    "docs": """- Accurate and consistent with the current README/PROMPT; no claims the repo can't back.
- Does not change the prompt's safety rules (that needs the maintainer → hold).
- Small corrections and translations are merged; rewrites of structure the maintainer already changed are
  closed kindly (point at what landed).""",
    "showcase": """- A public repo/branch, built on CleanYourTV, one short honest line, author credited.
- Not already in SHOWCASE.md.""",
    "tools": """- Small, standard-library Python/shell, no network calls beyond the TV, no prebuilt binaries.
- Does not weaken the Home-safety or restore logic (that needs the maintainer → hold).
- Overlaps an existing tool → rework into the existing tool.""",
    "launcher": """- Off by default behind a config flag; strings in every locale; no INTERNET permission; no heavy deps.
- Not a second design for something already merged or open (pick one).
- Changes users would see usually need a TV run before merge.""",
    "theme": """- Lives under themes/<name>/ (config.json + wallpaper), adds nothing to the APK.
- Festival/seasonal themes need a festival_until date.""",
    "workflow": """- CI/workflow, APK size gate or bot changes always need the maintainer → hold.""",
}


def pr_type(paths: list[str], title: str = "") -> str:
    """The dominant kind of change, judged from the files (shared README tables don't count) and the title."""
    if title.lower().lstrip("[(").startswith(("launcher", "feat(launcher", "fix(launcher")):
        return "launcher"
    p = [x for x in paths if x not in ("README.md", "examples/README.md", "README.zh-CN.md")]
    if any(x.startswith(".github/") for x in p):
        return "workflow"
    if any(x.startswith("launcher/") for x in p) or any(
            x in ("themes/README.md",) or x.endswith("config.xml") for x in p):
        return "launcher"
    if p and all(x.startswith("examples/") for x in p):
        return "tv-list"
    if p and all(x == "SHOWCASE.md" for x in p):
        return "showcase"
    if p and all(x.startswith("themes/") for x in p):
        return "theme"
    if p and all(x.startswith("addons/") or x in ("SHOWCASE.md", "CONTRIBUTING.md") for x in p) and \
            any(x.startswith("addons/") for x in p):
        return "addon"
    if any(x.startswith("tools/") or x.endswith((".sh", ".ps1", ".py")) for x in p):
        return "tools"
    if not p and paths:
        return "tv-list" if any(x == "examples/README.md" for x in paths) else "docs"
    return "docs"


# kinds the bot never decides alone, whatever it thinks (v3; v4 decides launcher PRs through the launcher gate)
ALWAYS_MAINTAINER = {"launcher", "workflow"}

# v4: the small core plus the hub. Where a checklist isn't here, the v3 one is used.
CHECKLISTS_V4 = {
    **CHECKLISTS,
    "tv-list": CHECKLISTS["tv-list"] + """
- Never Android's core packages (#884: permission controller, package installer, ext services/shared, module
  metadata, mainline overlays, systemui, shell, phone, settings, tv.settings, providers except calendar/contacts/
  userdictionary/blockednumber): tools/disable.sh refuses such a list → rework.
- Disabling only: `pm uninstall` steps → rework (drop them). A Private DNS / AdGuard setup in the folder is
  dropped on merge (the main README already has the optional DNS extra). The folder's own install/restore
  scripts are dropped on merge; the README points at tools/disable.sh and tools/restore.sh.
- The TV's own firmware updater stays enabled (commented out on merge). Entries the author marks untested are
  commented out until tested.
- Same product code and firmware as a folder already on main (see same_product_on_main): a second unit or a
  re-badge of the same model → rework (fold into that folder); a different model number whose list makes its
  own choices → its own folder. A judgement call.
- Edits to a list already on main are judgement calls: decide only when the change is clearly right.""",
    "launcher": """- The core takes only fixes, translations and small opt-in switches. A switch qualifies only if it is OFF by
  default (today's behaviour unchanged until a theme or config.xml turns it on), has its strings in every
  locale (or no strings: config-only), and stays small (see core_lines_changed; the APK has a hard size gate).
- Check the facts, not the description: new_config_keys and their defaults, changed_config_defaults (a changed
  default for every TV → rework), locales_missing_new_strings, new_permissions / network_use, manifest_changes,
  home_path_touched (Home/launch behaviour needs a run on a real TV → hold), conflicts_with_main (→ rework:
  rebase).
- Bug fixes that correct wrong behaviour need no flag; a fix tested on a device can merge.
- A new look (colours, wallpaper, dock style) that config keys can already express → theme (themes/<name>/ with a
  real-TV screenshot).
- A feature that can be its own small app (a card, a widget, a screensaver, a stats view) → addon
  (addons/<name>/, a module card; it never touches launcher/).
- Big in-launcher rewrites, new permissions or network access, old-Android ports (minSdk), Fire TV Home takeover,
  alternative launchers, or a change of the default for everyone → showcase (the contributor's fork plus one
  row in SHOWCASE.md). Not a rework: the author doesn't have to shrink it.
- Not a second design for something already merged or open (one design per feature: rework or close).""",
    "theme": """- Lives under themes/<name>/ (config.json + wallpaper), adds nothing to the APK.
- Needs themes/<name>/screenshot.jpg: Home on a real TV with the theme (missing → merge-with-fix only if the
  author can add it easily, else rework). Festival/seasonal themes need a festival_until date.
- Only keys the launcher already reads; a theme that needs new launcher code is a launcher PR.""",
    "addon": """- It already is an add-on: judge it on its merits (merge / merge-with-fix / rework), never "addon".
- addons/<name>/ is its own Gradle app that plugs into Home only through the module-card spec. Its
  gradle/wrapper/gradle-wrapper.jar is required by the add-ons CI, not a prebuilt binary.
- An add-on that does what an existing add-on already does (same source, same card) → rework: fold it in.
- Never touches launcher/ (a PR that does → rework: keep it to addons/<name>/). No APKs in the repo.
- Its README has a Permissions heading; addons/README.md gets an index row; the author maintains it.
- Network access is allowed in an add-on if its README says so; it never makes the core bigger.""",
    "showcase": CHECKLISTS["showcase"] + """
- One row in the right SHOWCASE.md section, short and honest; the table stays one table (no blank line before
  the row).""",
}
