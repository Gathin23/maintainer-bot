"""Deterministic facts about a PR (no AI). They feed the labels, the decision prompt and the hard overrides.

Everything here works on a plain snapshot dict so it can be unit-tested and replayed in the backtest:
    {"files": [{"path": str, "additions": int, "deletions": int, "patch": str}], "title": str, ...}
The repo-specific knobs (which folders mean which label, which packages are protected) come from the config.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

BINARY_EXT = (".apk", ".aab", ".so", ".jar", ".aar", ".dex", ".exe", ".dll", ".bin", ".zip")


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
    # paths whose changes always need the maintainer
    sensitive_paths: tuple = (".github/", "PROMPT.md", "tools/disable", "tools/restore", "launcher/app/build.gradle",
                              ".opencodereview/", ".github/maintainer/")
    manifest_path: str = "launcher/app/src/main/AndroidManifest.xml"
    strings_base: str = "launcher/app/src/main/res/values/strings.xml"
    strings_locale_re: str = r"^launcher/app/src/main/res/values-[^/]+/strings\.xml$"


# Packages that pair the remote or handle text input. Disabling them can leave a TV with no way to re-pair the
# Bluetooth remote or to type the Wi-Fi password again, so a list that does it always goes to the maintainer.
PAIRING_INPUT_RE = re.compile(r"autopair|bt_?rcu|rcu_?pair|remote_?pair|btpair|bluetooth.*pair|pair.*bluetooth|"
                              r"inputmethod|\.ime(\.|$)|_ime$|\.ime_|keyboard", re.I)
PKG_RE = re.compile(r"\b([a-zA-Z][a-zA-Z0-9_]*(?:\.[a-zA-Z0-9_]+)+)\b")
HIDE_RE = re.compile(r"\bpm\s+(hide|block)\b|^\s*(hide|block)\s+[a-zA-Z]", re.I)
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

    protected_hits = []
    for f in files:
        if not re.match(rules.list_file_re, f["path"]):
            continue
        for line in _added_lines(f.get("patch", "")):
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            pkg = s.split()[0]
            if pkg in rules.protected_packages or any(k in pkg.lower() for k in rules.protected_keywords):
                protected_hits.append(pkg)

    pairing_input = []
    hide_lines, has_undo = [], False
    for f in files:
        if not f["path"].startswith("examples/"):
            continue
        added = _added_lines(f.get("patch", ""))
        if any(UNDO_RE.search(l) for l in added):
            has_undo = True
        for line in added:
            if HIDE_RE.search(line.split("#", 1)[0]):
                hide_lines.append(line.strip()[:80])
            if not re.match(rules.list_file_re, f["path"]):
                continue
            pkg = _list_package(line)
            if pkg and PAIRING_INPUT_RE.search(pkg) and pkg not in rules.protected_packages:
                pairing_input.append(pkg)
    hide_without_undo = sorted(set(hide_lines)) if hide_lines and not has_undo else []

    adds_internet = any(f["path"] == rules.manifest_path and "android.permission.INTERNET" in "\n".join(
        _added_lines(f.get("patch", ""))) for f in files)
    binaries = [p for p in paths if p.lower().endswith(BINARY_EXT)]
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
