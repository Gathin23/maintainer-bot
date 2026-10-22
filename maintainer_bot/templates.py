"""Kind, short comments for the three "it belongs somewhere else" verdicts: showcase, addon and theme.

Each one thanks the author for something specific (the review's own phrase), says where the idea fits and why the
core stays small, and links the repo's "Where does my idea go?" table. They are written as an invitation, so the
same text works as the phase-1 suggestion and as the comment the bot posts once a maintainer approves.
"""
from __future__ import annotations

import re

WHERE = "{server}/{repo}/blob/{branch}/CONTRIBUTING.md#where-does-my-idea-go"


def where_link(repo: str, branch: str = "main", server: str = "https://github.com") -> str:
    return WHERE.format(server=server, repo=repo, branch=branch)


def _specific(text: str) -> str:
    t = re.sub(r"<[^>]{0,200}>", "", text or "")
    t = re.sub(r"@(?=[A-Za-z0-9-])", "@​", t)
    t = re.sub(r"\s+", " ", t).strip().rstrip(".!")
    if len(t) > 140:
        t = t[:139].rsplit(" ", 1)[0] + "…"
    return t[0].lower() + t[1:] if t[:1].isupper() and not t[1:2].isupper() else t


def _slug(name: str, fallback: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")[:40]
    return s or fallback


def _thanks(specific: str) -> str:
    s = _specific(specific)
    return f"Thank you for this, {s}!" if s else "Thank you for this!"


def showcase(specific: str, link: str) -> str:
    return (f"{_thanks(specific)} The launcher here stays small on purpose (fixes, translations and small switches "
            "that are off by default), so a change this size lives best in your own fork. We'd love to feature it: "
            "add one row for your fork to SHOWCASE.md in a small PR, and people looking for exactly this can find "
            f"it. ([Where does my idea go?]({link}))")


def addon(specific: str, name: str, link: str) -> str:
    folder = _slug(name, "your-addon")
    return (f"{_thanks(specific)} This would make a lovely add-on: its own small app under `addons/{folder}/` "
            "that shows up on Home as a module card and never touches `launcher/`, so it can grow without making "
            "the launcher bigger. Would you send it again there? `addons/README.md` has the steps, and you stay its "
            f"maintainer. ([Where does my idea go?]({link}))")


def theme(specific: str, name: str, link: str) -> str:
    folder = _slug(name, "your-theme")
    return (f"{_thanks(specific)} This is a new look, and looks live in `themes/{folder}/`: a `config.json` (and a "
            "wallpaper if you like) plus a screenshot of Home on a real TV. Could you move it there? Then anyone "
            "can pick it with the theme tools, and Home stays the same for everyone else. "
            f"([Where does my idea go?]({link}))")


def render(kind: str, *, specific: str, name: str = "", link: str) -> str:
    if kind == "showcase":
        return showcase(specific, link)
    if kind == "addon":
        return addon(specific, name, link)
    if kind == "theme":
        return theme(specific, name, link)
    raise ValueError(kind)
