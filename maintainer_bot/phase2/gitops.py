"""Local git work for the bot-branch path: PR head (+ main merged in when it conflicts) (+ the small fix).

Runs in a checkout of the base repo whose remote can push (the workflow checks out with the App token).
Only ever pushes bot/* branches. Conflicts are resolved by fixed rules, never by a model:
  - a hunk where both sides are markdown table rows: keep both (the README and examples tables)
  - files the counts step regenerates (card alt text, brand line, languages row, stats strip, card images):
    take main's version, the counts PR redraws them after the batch
  - anything else: give up, the PR stays for a maintainer
"""
from __future__ import annotations

import os
import re
import subprocess

TABLE_FILES = ("README.md", "examples/README.md", "SHOWCASE.md")
REGENERATED = ("tools/readme_stats.py", "docs/stats.png", "docs/card.jpg")
COUNT_LINE = re.compile(r"TV models · \d+ brands|^\*\*.+?\*\* \d+ ·|^\| \*\*\d+ languages\*\* \||projectors$|"
                        r"^[A-Za-z0-9+ ]+( · [A-Za-z0-9+ ]+)* ·$")


class GitError(RuntimeError):
    pass


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def _write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def resolve_text(text: str) -> tuple[str | None, list[str]]:
    """Resolve conflict markers (ours = PR, theirs = main). None when a hunk breaks the rules."""
    out, notes, i = [], [], 0
    lines = text.split("\n")
    while i < len(lines):
        if not lines[i].startswith("<<<<<<< "):
            out.append(lines[i])
            i += 1
            continue
        ours, theirs, j = [], [], i + 1
        while j < len(lines) and not lines[j].startswith(("=======", "||||||| ")):
            ours.append(lines[j]); j += 1
        if j < len(lines) and lines[j].startswith("||||||| "):  # diff3 base section: skip it
            while j < len(lines) and not lines[j].startswith("======="):
                j += 1
        j += 1
        while j < len(lines) and not lines[j].startswith(">>>>>>> "):
            theirs.append(lines[j]); j += 1
        if j >= len(lines):
            return None, notes
        both = [l for l in ours + theirs if l.strip()]
        if both and all(l.startswith("|") for l in both):
            out += theirs + [l for l in ours if l not in theirs]
            notes.append("kept both sides' table rows")
        elif both and all(COUNT_LINE.search(l) for l in both):
            out += theirs
            notes.append("took main's count lines (the counts PR updates them)")
        else:
            return None, notes
        i = j + 1
    return "\n".join(out), notes


class Git:
    def __init__(self, workdir: str, base: str = "main", remote: str = "origin",
                 author: tuple[str, str] = ("maintainer-bot", "maintainer-bot@users.noreply.github.com")):
        self.dir, self.base, self.remote, self.author = workdir, base, remote, author

    def run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        env = {**os.environ, "GIT_AUTHOR_NAME": self.author[0], "GIT_AUTHOR_EMAIL": self.author[1],
               "GIT_COMMITTER_NAME": self.author[0], "GIT_COMMITTER_EMAIL": self.author[1],
               "GIT_TERMINAL_PROMPT": "0"}
        r = subprocess.run(["git", *args], cwd=self.dir, capture_output=True, text=True, env=env)
        if check and r.returncode != 0:
            raise GitError(f"git {args[0]}: {(r.stderr or r.stdout).strip()[:300]}")
        return r

    def fetch_pr(self, n: int, sha: str) -> None:
        self.run("fetch", "-q", self.remote, self.base, f"+refs/pull/{n}/head:refs/remotes/{self.remote}/pr/{n}")
        got = self.run("rev-parse", f"{self.remote}/pr/{n}").stdout.strip()
        if got != sha:
            raise GitError(f"PR head is {got[:12]}, expected {sha[:12]}")

    def prepare(self, n: int, sha: str, title: str) -> dict:
        """Branch bot/merge-n at the PR head; merge main in only if the two conflict. Returns what happened."""
        self.fetch_pr(n, sha)
        branch = f"bot/merge-{n}"
        self.run("checkout", "-q", "-f", "-B", branch, sha)
        main = f"{self.remote}/{self.base}"
        if self.run("merge-base", "--is-ancestor", main, "HEAD", check=False).returncode == 0:
            return {"branch": branch, "merged_main": False, "resolved": []}
        clean = self.run("merge-tree", "--write-tree", main, "HEAD", check=False).returncode == 0
        if clean:
            return {"branch": branch, "merged_main": False, "resolved": []}
        r = self.run("merge", "--no-ff", "--no-edit", "-m", f"Merge main into #{n} ({title[:60]})", main, check=False)
        resolved = []
        if r.returncode != 0:
            for path in self.run("diff", "--name-only", "--diff-filter=U").stdout.split():
                if path in REGENERATED:
                    self.run("checkout", "--theirs", "--", path)
                    resolved.append(f"{path}: main's version (regenerated by the counts PR)")
                elif path in TABLE_FILES:
                    full = os.path.join(self.dir, path)
                    text, notes = resolve_text(_read(full))
                    if text is None:
                        self.run("merge", "--abort", check=False)
                        raise GitError(f"conflict in {path} outside the tables")
                    _write(full, text)
                    resolved.append(f"{path}: " + ", ".join(sorted(set(notes))))
                else:
                    self.run("merge", "--abort", check=False)
                    raise GitError(f"conflict in {path}")
                self.run("add", "--", path)
            self.run("commit", "-q", "--no-edit")
        return {"branch": branch, "merged_main": True, "resolved": resolved}

    def read(self, path: str) -> str | None:
        r = self.run("show", f"HEAD:{path}", check=False)
        return r.stdout if r.returncode == 0 else None

    def apply_edits(self, edits: list[dict], message: str) -> None:
        for e in edits:
            full = os.path.join(self.dir, e["path"])
            text = _read(full) if os.path.exists(full) else ""
            if e["search"]:
                if text.count(e["search"]) != 1:
                    raise GitError(f"{e['path']}: search text is not unique on the merge branch")
                text = text.replace(e["search"], e["replace"], 1)
            else:
                text = e["replace"]
            _write(full, text)
            self.run("add", "--", e["path"])
        self.run("commit", "-q", "-m", message)

    def head(self) -> str:
        return self.run("rev-parse", "HEAD").stdout.strip()

    def push(self, branch: str) -> str:
        if not branch.startswith("bot/"):
            raise GitError("the bot only pushes bot/* branches")
        self.run("push", "-q", "-f", self.remote, f"HEAD:refs/heads/{branch}")
        return self.head()

    def fresh_base(self, branch: str) -> None:
        self.run("fetch", "-q", self.remote, self.base)
        self.run("checkout", "-q", "-f", "-B", branch, f"{self.remote}/{self.base}")
        self.run("clean", "-qfd")

    def dirty(self) -> list[str]:
        return [l[3:] for l in self.run("status", "--porcelain").stdout.splitlines() if l.strip()]

    def commit_all(self, message: str) -> None:
        self.run("add", "-A")
        self.run("commit", "-q", "-m", message)
