"""PR types and a short checklist per type, put in the prompt so the model checks the right things."""
from __future__ import annotations

CHECKLISTS = {
    "tv-list": """- One TV model per folder under examples/<brand-model>/ with debloat.txt (and notes if needed).
- Not a duplicate: the folder or the same model/firmware is not already on main or in another open PR
  (if it is: close, or fold the notes into the existing list).
- Disables, never uninstalls; no protected packages (TV/input/tuner, keyboard, Bluetooth, Play Store/Services).
- The README TV table and examples/README rows are added (if missing → merge-with-fix: add the rows).
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
    if any(x.startswith("tools/") or x.endswith((".sh", ".ps1", ".py")) for x in p):
        return "tools"
    if not p and paths:
        return "tv-list" if any(x == "examples/README.md" for x in paths) else "docs"
    return "docs"


# kinds the bot never decides alone, whatever it thinks
ALWAYS_MAINTAINER = {"launcher", "workflow"}
