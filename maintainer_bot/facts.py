"""Deterministic facts about a PR (no AI). They feed the labels, the decision prompt and the hard overrides.

Everything here works on a plain snapshot dict so it can be unit-tested and replayed in the backtest:
    {"files": [{"path": str, "additions": int, "deletions": int, "patch": str}], "title": str, ...}
The repo-specific knobs (which folders mean which label, which packages are protected) come from the config.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

BINARY_EXT = (".apk", ".aab", ".so", ".jar", ".aar", ".dex", ".exe", ".dll", ".bin", ".zip")
# not prebuilt apps: the Gradle wrapper an add-on's own build needs (.github/workflows/addons.yml runs ./gradlew)
ALLOWED_BINARY_RE = re.compile(r"^addons/[^/]+/gradle/wrapper/gradle-wrapper\.jar$")


@dataclass
class RepoRules:
    """Repo-specific settings; defaults fit Gathin23/cleanyourtv."""
    path_labels: dict = field(default_factory=lambda: {
        "examples/": "tv-list", "launcher/": "launcher", "tools/": "scripts", "themes/": "theme",
        "docs/": "docs", "README": "docs", "PROMPT.md": "docs", "CONTRIBUTING": "docs", "SHOWCASE.md": "showcase",
    })
    list_folder_re: str = r"^examples/([^/]+)/"
    list_file_re: str = r"^examples/[^/]+/.*\.txt$"
    # packages a list must never disable (the TV stops working without them). setupwraith and factory
    # packages are allowed: the repo's own tests guard setupwraith, and factory apps may be disabled, only
    # never launched.
    protected_packages: tuple = (
        "com.android.vending", "com.google.android.gms", "com.android.inputmethod.latin",
        "com.google.android.inputmethod.latin", "com.android.bluetooth", "com.android.tv.settings",
        "com.google.android.katniss.setup", "com.android.providers.tv",
    )
    protected_keywords: tuple = ()
    # Android's core packages (cleanyourtv #884, tools/recovery.py): the TV may not boot again without them;
    # tools/disable.sh refuses a list naming one, so a list that does is sent back
    core_re: str = (r"^(android|com\.android\.systemui|com\.android\.shell|com\.android\.phone|com\.android\.settings|"
                    r"com\.android\.tv\.settings|com\.(google\.)?android\.(permissioncontroller|packageinstaller|"
                    r"ext\.services|ext\.shared|modulemetadata)|com\.google\.android\.overlay\.modules.*|"
                    r"com\.android\.providers\..*)$")
    core_ok: str = r"^com\.android\.providers\.(calendar|contacts|userdictionary|blockednumber)$"
    # paths whose changes always need the maintainer
    sensitive_paths: tuple = (".github/", "PROMPT.md", "tools/disable", "tools/restore", "launcher/app/build.gradle",
                              ".opencodereview/", ".github/maintainer/")
    manifest_path: str = "launcher/app/src/main/AndroidManifest.xml"
    strings_base: str = "launcher/app/src/main/res/values/strings.xml"
    strings_locale_re: str = r"^launcher/app/src/main/res/values-[^/]+/strings\.xml$"
    # v4: the small core and its neighbours
    core_prefix: str = "launcher/"
    config_xml: str = "launcher/app/src/main/res/values/config.xml"
    test_dir_re: str = r"^launcher/app/src/(test|androidTest)/"
    # the Home/launch path: a change here needs a run on a real TV before it merges
    home_path_files: tuple = ("launcher/app/src/main/java/com/gathin/tvhome/HomeKeyService.java",
                              "launcher/build-and-install.sh", "launcher/build-and-install.ps1",
                              "tools/build-and-install.sh")
    home_path_file: str = "launcher/app/src/main/java/com/gathin/tvhome/MainActivity.java"
    own_packages: tuple = ("com.gathin.tvhome",)   # uninstalling the launcher itself is fine
    addon_prefix: str = "addons/"
    theme_prefix: str = "themes/"
    # the policy says "always the maintainer" for these, whatever the verdict (safety rules, CI, the bot's rules)
    always_maintainer_paths: tuple = (".github/", ".opencodereview/", "PROMPT.md", "tools/disable", "tools/restore")


# Packages that pair the remote or handle text input. Disabling them can leave a TV with no way to re-pair the
# Bluetooth remote or to type the Wi-Fi password again, so a list that does it always goes to the maintainer.
PAIRING_INPUT_RE = re.compile(r"autopair|bt_?rcu|rcu_?pair|remote_?pair|btpair|bluetooth.*pair|pair.*bluetooth|"
                              r"inputmethod|\.ime(\.|$)|_ime$|\.ime_|keyboard", re.I)
PKG_RE = re.compile(r"\b([a-zA-Z][a-zA-Z0-9_]*(?:\.[a-zA-Z0-9_]+)+)\b")
# a pm hide/block step on a package, or a list line "hide <package>"; prose ("…, which doesn't
# block YouTube ads") must never count (#982 got an invented pm hide from a wrapped README sentence)
HIDE_RE = re.compile(r"\bpm\s+(hide|block)\s+(?:--user\s+\d+\s+)?[a-zA-Z]\w*(?:\.\w+)+|"
                     r"^\s*(hide|block)\s+[a-zA-Z]\w*(?:\.\w+)+\s*$", re.I)
# in a list file's header, saying the list is applied with pm hide/block is enough ("Use `pm hide` instead")
PM_HIDE_RE = re.compile(r"\b(use|using|with|via|swap to|apply|applied|run)\b[^.\n]{0,20}\bpm\s+(hide|block)\b|"
                        r"\bpm\s+(hide|block)\s+<", re.I)
UNDO_RE = re.compile(r"\bpm\s+(unhide|unblock)\b|\b(unhide|unblock)\b", re.I)


def _list_package(line: str) -> str:
    """The package a list line acts on: the first token, or the package inside a `pm …` command."""
    s = line.strip()
    if not s or s.startswith("#"):
        return ""
    if s.split()[0] in ("pm", "adb", "cmd"):
        m = PKG_RE.search(s.split("#", 1)[0].split(None, 1)[1] if " " in s else "")
        return m.group(1) if m else ""
    return s.split()[0]


def _added_lines(patch: str) -> list[str]:
    return [l[1:] for l in (patch or "").splitlines() if l.startswith("+") and not l.startswith("+++")]


def _code_lines(lines: list[str]) -> list[str]:
    """Lines that are code, not comments: no <!-- … --> XML comments, // or /* … */ or * javadoc lines."""
    out, in_xml = [], False
    for l in lines:
        s = l.strip()
        if in_xml:
            in_xml = "-->" not in s
            continue
        if s.startswith("<!--"):
            in_xml = "-->" not in s
            continue
        if s.startswith(("//", "/*", "*")):
            continue
        out.append(l.split("//", 1)[0] if "://" not in l else l)
    return out


def compute(snapshot: dict, rules: RepoRules | None = None, *, existing_list_folders: set | None = None,
            other_open_list_folders: dict | None = None, locale_count: int = 0) -> dict:
    """Facts for one PR snapshot.

    existing_list_folders: examples/ folder names already on main when the PR is judged.
    other_open_list_folders: {folder: [pr numbers]} for other PRs open at that time.
    locale_count: number of translated strings.xml files on main (for the "strings in every locale" check).
    """
    rules = rules or RepoRules()
    files = snapshot.get("files") or []
    paths = [f["path"] for f in files]
    labels = set()
    for p in paths:
        for prefix, label in rules.path_labels.items():
            if p.startswith(prefix):
                labels.add(label)
    adds = sum(int(f.get("additions") or 0) for f in files)
    dels = sum(int(f.get("deletions") or 0) for f in files)
    size = "size/S" if adds + dels < 60 else "size/M" if adds + dels < 400 else "size/L"

    list_folders = sorted({m.group(1) for p in paths if (m := re.match(rules.list_folder_re, p))})
    new_list_folders = [f for f in list_folders if existing_list_folders is not None and f not in existing_list_folders]
    duplicate_of_merged = [f for f in list_folders
                           if existing_list_folders is not None and f in existing_list_folders
                           and any(p.startswith(f"examples/{f}/") and fi.get("status") == "added"
                                   for fi in files for p in [fi["path"]])]
    competing = {f: prs for f, prs in (other_open_list_folders or {}).items() if f in list_folders and prs}

    protected_hits, core_hits, evidence = [], [], {}
    for f in files:
        if not re.match(rules.list_file_re, f["path"]):
            continue
        for line in _added_lines(f.get("patch", "")):
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            pkg = _list_package(line) or s.split()[0]
            if pkg in rules.protected_packages or any(k in pkg.lower() for k in rules.protected_keywords):
                protected_hits.append(pkg)
                evidence.setdefault("protected_packages_disabled", s[:120])
            if re.match(rules.core_re, pkg) and not re.match(rules.core_ok, pkg):
                core_hits.append(pkg)
                evidence.setdefault("core_packages_disabled", s[:120])

    pairing_input = []
    hide_lines, has_undo = [], False
    for f in files:
        if not f["path"].startswith("examples/"):
            continue
        added = _added_lines(f.get("patch", ""))
        if any(UNDO_RE.search(l) for l in added):
            has_undo = True
        for line in added:
            in_list = bool(re.match(rules.list_file_re, f["path"]))
            if HIDE_RE.search(line.split("#", 1)[0]) or HIDE_RE.search(line.strip().lstrip("#").strip()) or (
                    in_list and PM_HIDE_RE.search(line)):
                hide_lines.append(line.strip()[:80])
            if not re.match(rules.list_file_re, f["path"]):
                continue
            pkg = _list_package(line)
            if pkg and PAIRING_INPUT_RE.search(pkg) and pkg not in rules.protected_packages:
                pairing_input.append(pkg)
                evidence.setdefault("pairing_or_input_packages_disabled", line.strip()[:120])
    hide_without_undo = sorted(set(hide_lines)) if hide_lines and not has_undo else []
    if hide_without_undo:
        evidence["hide_without_undo"] = hide_without_undo[0]

    internet = [l.strip() for f in files if f["path"] == rules.manifest_path
                for l in _code_lines(_added_lines(f.get("patch", ""))) if "android.permission.INTERNET" in l]
    adds_internet = bool(internet)
    if internet:
        evidence["adds_internet_permission"] = internet[0][:120]
    binaries = [p for p in paths if p.lower().endswith(BINARY_EXT) and not ALLOWED_BINARY_RE.match(p)]
    sensitive = sorted({p for p in paths for s in rules.sensitive_paths if p.startswith(s)})

    new_strings = 0
    for f in files:
        if f["path"] == rules.strings_base:
            new_strings = sum(1 for l in _added_lines(f.get("patch", "")) if "<string " in l)
    locales_touched = sum(1 for p in paths if re.match(rules.strings_locale_re, p))

    return {
        "labels": sorted(labels),
        "size": size,
        "additions": adds,
        "deletions": dels,
        "files": len(files),
        "top_dirs": sorted({p.split("/")[0] for p in paths}),
        "list_folders": list_folders,
        "new_list_folders": new_list_folders,
        "duplicate_of_merged_folder": duplicate_of_merged,
        "competing_open_prs": competing,
        "protected_packages_disabled": sorted(set(protected_hits)),
        "core_packages_disabled": sorted(set(core_hits)),
        "evidence": evidence,
        "pairing_or_input_packages_disabled": sorted(set(pairing_input)),
        "hide_without_undo": hide_without_undo,
        "adds_internet_permission": adds_internet,
        "binary_files": binaries,
        "sensitive_paths": sensitive,
        "new_launcher_strings": new_strings,
        "locales_with_strings": locales_touched,
        "locale_count_on_main": locale_count,
    }


def hard_overrides(facts: dict) -> tuple[str | None, str]:
    """Deterministic rules that can stop a merge. Returns (verdict to use instead of a merge, why).

    They only ever downgrade merge / merge-with-fix: a model's close, rework or hold is left alone.
    """
    if facts.get("protected_packages_disabled"):
        return "rework", "a list disables protected packages: " + ", ".join(facts["protected_packages_disabled"][:4])
    if facts.get("pairing_or_input_packages_disabled"):
        return "hold", ("a list disables remote-pairing or input packages: "
                        + ", ".join(facts["pairing_or_input_packages_disabled"][:4]))
    if facts.get("hide_without_undo"):
        return "hold", "a list uses pm hide/block without the matching unhide/unblock undo in the header"
    if facts.get("sensitive_paths"):
        return "hold", "touches maintainer-only paths: " + ", ".join(facts["sensitive_paths"][:4])
    if facts.get("binary_files"):
        return "hold", "adds prebuilt binaries: " + ", ".join(facts["binary_files"][:3])
    if facts.get("adds_internet_permission"):
        return "hold", "adds the INTERNET permission to the launcher"
    return None, ""


def merge_blockers(facts: dict) -> list[str]:
    """Facts that turn a 'merge' into a 'rework': strings missing in most locales, a list folder that exists."""
    out = []
    gap = strings_gap(facts)
    if gap:
        out.append(gap)
    if facts.get("duplicate_of_merged_folder"):
        out.append("adds a list folder that already exists: " + ", ".join(facts["duplicate_of_merged_folder"]))
    return out


def strings_gap(facts: dict) -> str:
    """A note for the prompt and the fix: new launcher strings missing in most locales."""
    if facts.get("new_launcher_strings") and facts.get("locale_count_on_main") and \
            facts.get("locales_with_strings", 0) < max(1, facts["locale_count_on_main"] // 2):
        return (f"new launcher strings in {facts.get('locales_with_strings', 0)} of "
                f"{facts['locale_count_on_main']} locales")
    return ""


def apply_overrides(model_verdict: str, facts: dict) -> tuple[str, str]:
    """Final verdict after the deterministic rules. Returns (verdict, override reason or '')."""
    if model_verdict not in ("merge", "merge-with-fix"):
        return model_verdict, ""
    forced, why = hard_overrides(facts)
    if forced:
        return forced, why
    blockers = merge_blockers(facts)
    if blockers:
        return "rework", "; ".join(blockers)
    return model_verdict, ""


# ---------- v4: facts for the small core, the hub (themes/, addons/, SHOWCASE) and today's list rules ----------

CONFIG_ITEM_RE = re.compile(r'<(bool|integer|string|string-array|integer-array|array|color|dimen|fraction)\s+'
                            r'name="([^"]+)"([^>]*)>(.*?)(?:</\1>|$)')
STRING_RE = re.compile(r'<string\s+name="([^"]+)"([^>]*)>')
PERMISSION_RE = re.compile(r'<uses-permission[^>]*android:name="([^"]+)"')
NETWORK_RE = re.compile(r"\b(HttpURLConnection|HttpsURLConnection|URLConnection|new\s+URL\s*\(|OkHttp|Retrofit|"
                        r"new\s+Socket\s*\(|DatagramSocket|ServerSocket|WebView|DownloadManager|java\.net\.(URL|Socket|"
                        r"HttpURLConnection|InetSocketAddress))")
MANIFEST_KINDS = (("permission", r"<uses-permission"), ("service", r"<service"), ("receiver", r"<receiver"),
                  ("activity", r"<activity"), ("provider", r"<provider"), ("queries", r"<queries|<package "),
                  ("home intent", r"CATEGORY_HOME|android\.intent\.category\.HOME|category\.LAUNCHER"))
LIFECYCLE_RE = re.compile(r"\bvoid\s+on(Create|NewIntent|Resume|Start|Stop|Restart|Pause|WindowFocusChanged)\s*\(|"
                          r"CATEGORY_HOME|ACTION_BOOT_COMPLETED|BOOT_COMPLETED")
# a pm uninstall step on a package (a mention like "refuses `pm uninstall`" is not a step)
UNINSTALL_RE = re.compile(r"\bpm\s+uninstall\b(?:\s+(?:-k|--user\s+\d+))*\s+([a-zA-Z][\w]*\.[\w.]+)", re.I)
# setting Private DNS up (the command, or an instruction); "Private DNS works on this set" is only a note
DNS_SETUP_RE = re.compile(r"settings\s+put\s+global\s+private_dns_(?:specifier|mode)|Private DNS(?: is)? set to|"
                          r"\*\*Private DNS\*\*:|\bset (?:the )?Private DNS\b|Ad-blocking DNS", re.I)
UPDATER_RE = re.compile(r"(?:^|\.)(?:ota|fota|otaupdate|otaservice|systemupdate|systemupdater|sysupdate|swupdate|"
                        r"fwupdate|firmwareupdate|forcedotaupdater(?:\.v\d)?|updater|upgrade|upgrader|tvupgrade)"
                        r"(?:$|\.|_)", re.I)
UPDATER_NOT_FIRMWARE = re.compile(r"soundbar|peripheral|remote|rcu|appstore|app\.store|market|store|webview|"
                                  r"playstore|vending|chrome|youtube|netflix", re.I)
UNTESTED_RE = re.compile(r"untested|not tested|not yet tested|haven'?t tested|not verified|unverified|unsure|"
                         r"not sure|\(\?\)|\?\s*$", re.I)
SCRIPT_EXT = (".sh", ".ps1", ".bat", ".cmd", ".py")
# product, build and model identifiers in a list header: TCL G08_4K_GB, Xiaomi MiTV-MOOQ1, Fire TV AFTKM,
# Android build ids (UTT2.250416.001) and short firmware tags after a slash (…/AR2101/AR28)
PRODUCT_RE = re.compile(r"\b([A-Z]\d{2}_[0-9A-Z]{2,3}_[A-Z]{2}|MiTV-[A-Z0-9]{4,6}|AFT[A-Z0-9]{2,8}|"
                        r"[A-Z]{2,5}\d?[A-Z]?\.\d{6}\.\d{3}(?:\.[A-Z0-9]+)?)\b")
MODEL_TOKEN_RE = re.compile(r"^(?=.*\d)(?=.*[a-z])[a-z0-9]{4,}$")


def _removed_lines(patch: str) -> list[str]:
    return [l[1:] for l in (patch or "").splitlines() if l.startswith("-") and not l.startswith("---")]


def _config_items(lines: list[str]) -> dict[str, dict]:
    out = {}
    for l in lines:
        m = CONFIG_ITEM_RE.search(l)
        if m:
            kind, name, attrs, val = m.groups()
            out[name] = {"type": kind, "default": "(list)" if "array" in kind else val.strip()[:60]}
    return out


def _locale_of(path: str) -> str:
    m = re.search(r"/values-([^/]+)/strings\.xml$", path)
    return m.group(1) if m else ""


def core_facts(files: list[dict], rules: RepoRules, *, main_locales: list[str] | None = None) -> dict:
    """What a launcher PR changes in the core: size, config keys and defaults, strings per locale, permissions,
    network use, manifest and the Home/launch path."""
    core = [f for f in files if f["path"].startswith(rules.core_prefix)]
    if not core:
        return {}
    code = [f for f in core if not re.match(rules.test_dir_re, f["path"]) and not _locale_of(f["path"])]
    tests = [f for f in core if re.match(rules.test_dir_re, f["path"])]
    out: dict = {
        "core_lines_changed": sum(int(f.get("additions") or 0) + int(f.get("deletions") or 0) for f in code),
        "core_test_lines": sum(int(f.get("additions") or 0) for f in tests),
        "core_files": len(code),
    }
    cfg = next((f for f in files if f["path"] == rules.config_xml), None)
    if cfg:
        added = _config_items(_added_lines(cfg.get("patch", "")))
        removed = _config_items(_removed_lines(cfg.get("patch", "")))
        out["new_config_keys"] = [{"name": n, **v} for n, v in added.items() if n not in removed]
        out["changed_config_defaults"] = [{"name": n, "old": removed[n]["default"], "new": v["default"]}
                                          for n, v in added.items() if n in removed
                                          and removed[n]["default"] != v["default"] and "array" not in v["type"]]
    base = next((f for f in files if f["path"] == rules.strings_base), None)
    new_strings: list[str] = []
    if base:
        gone = {m.group(1) for l in _removed_lines(base.get("patch", "")) if (m := STRING_RE.search(l))}
        for l in _added_lines(base.get("patch", "")):
            m = STRING_RE.search(l)
            if m and 'translatable="false"' not in m.group(2) and m.group(1) not in gone:
                new_strings.append(m.group(1))
    added_locales = sorted({_locale_of(f["path"]) for f in files
                            if _locale_of(f["path"]) and f.get("status") == "added"})
    if added_locales:
        out["new_locales"] = added_locales
    if new_strings:
        out["new_strings"] = new_strings[:30]
        if main_locales:
            have: dict[str, set] = {}
            for f in files:
                loc = _locale_of(f["path"])
                if loc:
                    have[loc] = {m.group(1) for l in _added_lines(f.get("patch", "")) if (m := STRING_RE.search(l))}
            missing = sorted(loc for loc in main_locales if not set(new_strings) <= have.get(loc, set()))
            out["locales_missing_new_strings"] = missing
            out["locales_on_main"] = len(main_locales)
    perms, net, manifest, home = [], [], set(), []
    for f in core:
        added = _added_lines(f.get("patch", ""))
        changed = added + _removed_lines(f.get("patch", ""))
        if f["path"].endswith("AndroidManifest.xml"):
            perms += [m.group(1) for l in _code_lines(added) if (m := PERMISSION_RE.search(l))]
            for kind, rx in MANIFEST_KINDS:
                if any(re.search(rx, l) for l in changed):
                    manifest.add(kind)
            if not manifest and changed:
                manifest.add("other")
            if "home intent" in manifest:
                home.append(f["path"])
        elif f["path"].endswith((".java", ".kt")):
            net += sorted({m.group(1) for l in _code_lines(added) if (m := NETWORK_RE.search(l))})
        if f["path"] in rules.home_path_files or (
                f["path"] == rules.home_path_file and any(LIFECYCLE_RE.search(l) for l in changed)):
            home.append(f["path"])
    for f in files:  # the install scripts outside launcher/ are part of the launch path too
        if f["path"] in rules.home_path_files and f["path"] not in home:
            home.append(f["path"])
    if perms:
        out["new_permissions"] = sorted(set(perms))
    if net:
        out["network_use"] = sorted(set(net))
    if manifest:
        out["manifest_changes"] = sorted(manifest)
    if home:
        out["home_path_touched"] = sorted(set(home))
    return out


def list_facts(files: list[dict], rules: RepoRules, *, existing_list_folders: set | None,
               examples_readme: str = "") -> dict:
    """Today's list rules: uninstall steps, Private DNS setup, the TV's own firmware updater, untested entries,
    per-folder scripts, the same product already on main, and edits to a list that is already there."""
    out: dict = {}
    uninstall, dns, updaters, untested, scripts = [], [], [], [], []
    header_text = []
    for f in files:
        p = f["path"]
        if not p.startswith("examples/"):
            continue
        added = _added_lines(f.get("patch", ""))
        if p.count("/") >= 2 and p.lower().endswith(SCRIPT_EXT):
            scripts.append(p)
        for l in added:
            for m in UNINSTALL_RE.finditer(l):
                pkg = m.group(1)
                if pkg not in rules.own_packages and not re.search(r"\b(never|don'?t|do not|not)\b.{0,20}pm\s+uninstall",
                                                                     l, re.I):
                    uninstall.append(pkg[:80])
            if DNS_SETUP_RE.search(l) and p.count("/") >= 2:
                dns.append(p)
        if re.match(rules.list_file_re, p):
            header_text += [l for l in added[:40] if l.lstrip().startswith("#")]
            for l in added:
                s = l.strip()
                if not s or s.startswith("#"):
                    continue
                pkg = _list_package(l)
                comment = l.split("#", 1)[1] if "#" in l else ""
                if pkg and UPDATER_RE.search(pkg) and not UPDATER_NOT_FIRMWARE.search(pkg + " " + comment):
                    updaters.append(pkg)
                if pkg and comment and UNTESTED_RE.search(comment):
                    untested.append(pkg)
    if uninstall:
        out["uninstall_steps"] = sorted(set(uninstall))[:6]
    if dns:
        out["private_dns_setup"] = sorted(set(dns))
    if updaters:
        out["firmware_updater_disabled"] = sorted(set(updaters))
    if untested:
        out["untested_entries"] = sorted(set(untested))[:8]
    if scripts:
        out["list_folder_scripts"] = sorted(set(scripts))
    folders = sorted({m.group(1) for f in files if (m := re.match(rules.list_folder_re, f["path"]))})
    if existing_list_folders is not None and folders:
        edits = [x for x in folders if x in existing_list_folders]
        if edits and not [x for x in folders if x not in existing_list_folders]:
            out["edits_existing_list"] = edits
    new = [x for x in folders if existing_list_folders is not None and x not in existing_list_folders]
    if new and examples_readme:
        same = same_product(new, header_text, examples_readme)
        if same:
            out["same_product_on_main"] = same
    return out


def same_product(new_folders: list[str], header_lines: list[str], examples_readme: str) -> dict:
    """{identifier: [folders on main whose README row names it]} for product/build ids in the new list's header
    and model-number tokens in the new folder's name."""
    ids = set(PRODUCT_RE.findall("\n".join(header_lines)))
    for f in new_folders:
        ids |= {t for t in f.split("-") if MODEL_TOKEN_RE.match(t) and not t.startswith(("android", "google"))}
    rows = {}
    for line in examples_readme.splitlines():
        m = re.match(r"^\|\s*`([^`/]+)/?`", line)
        if m:
            rows[m.group(1)] = line
        else:
            for dm in re.finditer(r"\[[^\]]*\]\(\.\./(docs/devices/[^)]+)\)", line):
                rows.setdefault(dm.group(1), line)
    out = {}
    for t in sorted(ids):
        hits = [folder for folder, line in rows.items()
                if folder not in new_folders and re.search(rf"(?<![A-Za-z0-9]){re.escape(t)}(?![A-Za-z0-9])", line, re.I)]
        if hits:
            out[t] = sorted(hits)[:4]
    return out


def hub_facts(files: list[dict], rules: RepoRules, *, theme_folders_on_main: set | None = None,
              addon_folders_on_main: set | None = None) -> dict:
    """themes/<name>/ needs a real-TV screenshot; addons/<name>/ is its own app that never touches launcher/."""
    out: dict = {}
    paths = [f["path"] for f in files]
    themes = sorted({p.split("/")[1] for p in paths if p.startswith(rules.theme_prefix) and p.count("/") >= 2})
    if themes:
        out["theme_folders"] = themes
        new = [t for t in themes if theme_folders_on_main is None or t not in theme_folders_on_main]
        missing = [t for t in new if not any(re.match(rf"^{re.escape(rules.theme_prefix)}{re.escape(t)}/screenshot\.(jpe?g|png)$", p)
                                             for p in paths)]
        if missing:
            out["theme_missing_screenshot"] = missing
    addons = sorted({p.split("/")[1] for p in paths if p.startswith(rules.addon_prefix) and p.count("/") >= 2})
    if addons:
        out["addon_folders"] = addons
        if any(p.startswith(rules.core_prefix) for p in paths):
            out["addon_touches_launcher"] = True
        for a in addons:
            readme = next((f for f in files if f["path"] == f"{rules.addon_prefix}{a}/README.md"), None)
            if addon_folders_on_main is not None and a in addon_folders_on_main:
                continue
            if not readme or not re.search(r"^\+#+\s*Permissions", readme.get("patch", ""), re.M | re.I):
                out.setdefault("addon_readme_missing_permissions", []).append(a)
    return out


IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif")
ROOT_FILES_OK = re.compile(r"^(README[\w.-]*\.md|LICENSE.*|CONTRIBUTING\.md|SHOWCASE\.md|PROMPT\.md|CHANGELOG\.md|"
                           r"\.gitignore|\.gitattributes|\.editorconfig|SECURITY\.md|CODE_OF_CONDUCT\.md)$")


def stray_files(files: list[dict], rules: RepoRules) -> dict:
    """Files dropped on merge (#518, #407, #640): images nothing in the PR links to, and stray files at the root."""
    added = [f for f in files if f.get("status") == "added"]
    text = "\n".join("\n".join(_added_lines(f.get("patch", ""))) for f in files)
    images = [f["path"] for f in added if f["path"].lower().endswith(IMAGE_EXT)
              and not f["path"].startswith((rules.core_prefix, rules.theme_prefix, rules.addon_prefix))
              and f["path"].rsplit("/", 1)[-1] not in text]
    root = [f["path"] for f in added if "/" not in f["path"] and not ROOT_FILES_OK.match(f["path"])]
    out = {}
    if images:
        out["unlinked_images"] = sorted(images)[:6]
    if root:
        out["stray_root_files"] = sorted(root)[:6]
    return out


def compute_v4(snapshot: dict, rules: RepoRules | None = None, *, existing_list_folders: set | None = None,
               other_open_list_folders: dict | None = None, main_locales: list[str] | None = None,
               examples_readme: str = "", theme_folders_on_main: set | None = None,
               addon_folders_on_main: set | None = None, conflicts_with_main: bool | None = None,
               ci_failed: list[str] | None = None, apk_bytes: int | None = None,
               apk_gate_bytes: int | None = None) -> dict:
    """v3's facts plus the v4 ones. Everything is computed from the PR as data and from main; nothing is run."""
    rules = rules or RepoRules()
    fx = compute(snapshot, rules, existing_list_folders=existing_list_folders,
                 other_open_list_folders=other_open_list_folders, locale_count=len(main_locales or []))
    files = snapshot.get("files") or []
    paths = [f["path"] for f in files]
    fx["always_maintainer_paths"] = sorted({p for p in paths for s in rules.always_maintainer_paths if p.startswith(s)})
    fx.update(core_facts(files, rules, main_locales=main_locales))
    fx.update(list_facts(files, rules, existing_list_folders=existing_list_folders, examples_readme=examples_readme))
    fx.update(hub_facts(files, rules, theme_folders_on_main=theme_folders_on_main,
                        addon_folders_on_main=addon_folders_on_main))
    fx.update(stray_files(files, rules))
    if conflicts_with_main is not None:
        fx["conflicts_with_main"] = conflicts_with_main
    if ci_failed:
        fx["ci_failed"] = ci_failed
    if apk_bytes:
        fx["apk_bytes"] = apk_bytes
        if apk_gate_bytes:
            fx["apk_gate_bytes"] = apk_gate_bytes
            fx["apk_over_gate"] = apk_bytes >= apk_gate_bytes
    return fx


# ---------- v4.1: duplicates of other open PRs and of recent work on main ----------

SHARED_FILES = {".gitignore", ".gitattributes", "README.md", "examples/README.md", "SHOWCASE.md", "README.zh-CN.md", "addons/README.md",
                "themes/README.md", "docs/TROUBLESHOOTING.md", "CONTRIBUTING.md", "AGENTS.md", "PROMPT.md",
                "launcher/app/src/main/java/com/gathin/tvhome/Config.java",
                "launcher/app/src/main/java/com/gathin/tvhome/MainActivity.java",
                "launcher/app/src/main/res/values/config.xml", "launcher/app/src/main/res/values/strings.xml"}
ISSUE_RE = re.compile(r"(?<![\w/])#(\d{1,6})\b")
TITLE_WORD_RE = re.compile(r"[a-z0-9][a-z0-9_.-]{2,}")
TITLE_STOP = {"the", "and", "for", "with", "from", "into", "add", "adds", "fix", "fixes", "launcher", "docs",
              "examples", "list", "debloat", "tools", "when", "not", "its", "this", "that", "only"}


def _meaningful(path: str) -> bool:
    return path not in SHARED_FILES and not re.search(r"/values-[^/]+/strings\.xml$", path)


def title_words(title: str) -> set[str]:
    return {w for w in TITLE_WORD_RE.findall((title or "").lower()) if w not in TITLE_STOP}


CLOSING_RE = re.compile(r"\b(?:fix(?:es|ed)?|close[sd]?|resolve[sd]?|addresse?s?|for)\s+#(\d{1,6})\b", re.I)


def issue_refs(pr: dict) -> set[int]:
    """The issue a PR is about: any #N in its title, or "fixes/closes/resolves/for #N" in its body (a body's
    passing mention of another PR is not enough)."""
    refs = {int(n) for n in ISSUE_RE.findall(pr.get("title") or "")}
    refs |= {int(n) for n in CLOSING_RE.findall(pr.get("body") or "")}
    refs.discard(pr.get("pr") or pr.get("number") or -1)
    return refs


def added_lines_of(file_patches: list[dict]) -> set[str]:
    return {l.strip() for f in file_patches or [] if _meaningful(f["path"])
            for l in _added_lines(f.get("patch", "")) if len(l.strip()) > 12}


def duplicate_facts(me: dict, others: list[dict], *, recent_commits: list[dict] | None = None,
                    main_texts: dict | None = None) -> dict:
    """Possible duplicates for one PR.

    me / others: {"pr", "title", "body", "created_at", "files": [paths], "added": {lines}} (others: PRs open when
    this one was reviewed, plus PRs merged in the last 7 days with "merged": True). Of two open PRs doing the
    same, only the later one is the duplicate; a merged one makes this one a duplicate whatever its age. A PR
    stacked on another ("contained": its commits are part of this PR) is a series, not a duplicate.
    Strong = shares a meaningful file AND (the same referenced issue, a near-identical title, or most of the
    same added lines)."""
    out: dict = {}
    mine = {p for p in me["files"] if _meaningful(p)}
    my_added = me.get("added") or added_lines_of(me.get("file_patches"))
    refs, words = issue_refs(me), title_words(me["title"])
    dups = []
    for o in others:
        if o["pr"] == me["pr"] or o.get("contained") or (not o.get("merged") and o["created_at"] >= me["created_at"]):
            continue
        shared = sorted(mine & {p for p in o.get("files", []) if _meaningful(p)})
        same_issue = sorted(refs & issue_refs(o))
        ow = title_words(o["title"])
        jacc = len(words & ow) / len(words | ow) if words and ow else 0
        overlap = len(my_added & set(o.get("added") or ())) / len(my_added) if my_added else 0
        if not (same_issue or jacc >= 0.5 or (shared and overlap >= 0.5)):
            continue
        strong = bool(shared) and (bool(same_issue) or jacc >= 0.6 or overlap >= 0.5)
        why = "; ".join(x for x in ("already merged" if o.get("merged") else "",
                                    f"same issue #{same_issue[0]}" if same_issue else "",
                                    "a near-identical title" if jacc >= 0.5 else "",
                                    f"{overlap:.0%} of the same added lines" if overlap >= 0.5 else "",
                                    ("same files: " + ", ".join(shared[:3])) if shared else "") if x)
        dups.append({"pr": o["pr"], "title": o["title"][:90], "why": why, "strong": strong,
                     "merged": bool(o.get("merged"))})
    if dups:
        out["possible_duplicates"] = sorted(dups, key=lambda d: (not d["strong"], d["pr"]))[:4]
    for c in recent_commits or []:
        shared = sorted(mine & {p for p in c.get("files", []) if _meaningful(p)})
        same_issue = refs & {int(n) for n in ISSUE_RE.findall(c.get("message", ""))}
        if shared and same_issue:
            out.setdefault("recent_main_commits", []).append(
                {"sha": c["sha"][:8], "why": f"same issue #{sorted(same_issue)[0]}, same files: {', '.join(shared[:3])}"})
    if main_texts:
        total = found = 0
        for f in me.get("file_patches") or []:
            if not _meaningful(f["path"]) or f["path"] not in main_texts or main_texts[f["path"]] is None:
                continue
            added = [l.strip() for l in _added_lines(f.get("patch", "")) if len(l.strip()) > 12]
            total += len(added)
            found += sum(1 for a in added if a in main_texts[f["path"]])
        if total >= 3 and found / total >= 0.9:
            commit = (out.get("recent_main_commits") or [{}])[0].get("sha", "")
            out["already_on_main_live"] = {"share": round(found / total, 2), "commit": commit}
    return out
