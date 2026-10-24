"""End-to-end simulation of one /approve batch: a real bare git repo plays the GitHub remote, FakeApi plays the
REST API (merges really happen in the bare repo), and a fake model proposes the small fix.

The fake repo is a small CleanYourTV: its TV tables are generated from examples/*/tv.json by a copy of the repo's
tools/gen_tables.py. Batch: 3 merges (two lists that add only their folder and tv.json, and one older list PR
whose rows in the README tables move into its tv.json on a bot branch), 1 merge with a fix (the fix adds the
missing tv.json), 1 rework, 1 close, 1 held PR left alone, then the README counts PR that regenerates the tables. A pre-receive hook in the bare repo rejects any push to main that isn't a "GitHub" merge, which proves
the bot never pushes to the default branch itself.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

from maintainer_bot.ledger import Ledger
from maintainer_bot.phase2 import commands, queue as q
from maintainer_bot.phase2.cli import counts_pr, counts_runner
from maintainer_bot.phase2.executor import Config, Executor
from maintainer_bot.phase2.gitops import Git
from tests.fake_github import FakeApi

HERE = os.path.dirname(os.path.abspath(__file__))
COUNTS = os.path.join(os.path.dirname(HERE), "examples", "cleanyourtv", "update_counts.py")
GEN_TABLES = os.path.join(HERE, "fixtures", "cleanyourtv_gen_tables.py")

README = textwrap.dedent("""\
    # Mini

    <p><img src="docs/card.jpg" alt="4 TV models · 3 brands · 2 languages · 429 KB launcher. Before and after."></p>

    Tested lists from contributors, one folder per model in [`examples/`](examples/):

    <!-- tv-brands:start: generated -->
    <!-- tv-brands:end -->

    <details>
    <summary>The full list</summary>

    <!-- tv-table:start: generated -->
    <!-- tv-table:end -->

    </details>

    ## Features

    | Feature | |
    |---|---|
    | **2 languages** | Follows the TV's language |

    | You have | |
    |---|---|
    | **Built something on top?** | Add it to SHOWCASE.md, where two projects live. |
    """)

EXAMPLES = textwrap.dedent("""\
    # Examples

    <!-- tv-table:start: generated -->
    <!-- tv-table:end -->

    Notes for models that have no tested list yet:

    - [Old K](../docs/devices/old-k.md): a one-day report
    """)


def tv_json(tv, brand, os_="Android 11", notes="x"):
    return json.dumps({"tv": tv, "os": os_, "brand": brand, "notes": notes}, indent=2) + "\n"


SEED_LISTS = {"sony-a": ("Sony A", "Sony", "Android 9"), "tcl-b": ("TCL B", "TCL", "Android 11"),
              "tcl-d": ("TCL D", "TCL", "Android 11"), "xiaomi-f": ("Xiaomi F", "Xiaomi", "Android 9")}

STATS = 'STATS = [("4", "TV MODELS"), ("3", "BRANDS"), ("2", "LANGUAGES"), ("429 KB", "LAUNCHER")]\n'

HOOK = """#!/bin/sh
while read old new ref; do
  if [ "$ref" = "refs/heads/main" ] && [ -z "$FAKE_GH_MERGE" ]; then
    echo "only GitHub merges may update main" >&2; exit 1
  fi
done
"""


def sh(cwd, *args, env=None):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                       env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t",
                            "GIT_COMMITTER_EMAIL": "t@x", **(env or {})})
    if r.returncode != 0:
        raise RuntimeError(f"git {args}: {r.stderr}")
    return r.stdout.strip()


def write(root, path, text):
    full = os.path.join(root, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(text)


def edit(root, path, old, new):
    full = os.path.join(root, path)
    with open(full, encoding="utf-8") as f:
        text = f.read()
    assert old in text, (path, old)
    write(root, path, text.replace(old, new, 1))


class E2E(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.tmp.name
        self.bare, seed, self.work = (os.path.join(t, x) for x in ("origin.git", "seed", "work"))
        sh(t, "init", "-q", "--bare", "-b", "main", self.bare)
        write(self.bare, "hooks/pre-receive", HOOK)
        os.chmod(os.path.join(self.bare, "hooks/pre-receive"), 0o755)
        sh(t, "init", "-q", "-b", "main", seed)
        write(seed, "README.md", README)
        write(seed, "examples/README.md", EXAMPLES)
        for f, (name, brand, os_) in SEED_LISTS.items():
            write(seed, f"examples/{f}/debloat.txt", f"# {f}\ncom.example.ads\n")
            write(seed, f"examples/{f}/tv.json", tv_json(name, brand, os_))
        write(seed, "launcher/app/src/main/res/values/strings.xml", "<resources/>\n")
        write(seed, "launcher/app/src/main/res/values-de/strings.xml", "<resources/>\n")
        write(seed, "tools/readme_stats.py", STATS)
        shutil.copy(GEN_TABLES, os.path.join(seed, "tools", "gen_tables.py"))
        subprocess.run([sys.executable, "tools/gen_tables.py"], cwd=seed, check=True, capture_output=True)
        sh(seed, "add", "-A")
        sh(seed, "commit", "-q", "-m", "seed")
        sh(seed, "remote", "add", "origin", self.bare)
        sh(seed, "push", "-q", "origin", "main", env={"FAKE_GH_MERGE": "1"})
        self.seed = seed
        self.api = FakeApi(self.bare)
        self.base = sh(seed, "rev-parse", "HEAD")

    def tearDown(self):
        self.tmp.cleanup()

    def pr(self, n, title, changes, **kw):
        """Branch from the seed commit, apply changes, publish as refs/pull/n/head, register with FakeApi."""
        s = self.seed
        sh(s, "checkout", "-q", "-B", f"pr{n}", self.base)
        for c in changes:
            if len(c) == 2:
                write(s, *c)
            else:
                edit(s, *c)
        sh(s, "add", "-A")
        sh(s, "commit", "-q", "-m", title)
        sha = sh(s, "rev-parse", "HEAD")
        sh(s, "push", "-q", "-f", "origin", f"HEAD:refs/pull/{n}/head")
        paths = sh(s, "diff", "--name-only", f"{self.base}..HEAD").split()
        self.api.add_pr(n, title=title, sha=sha, paths=paths, **kw)
        return sha

    def scenario(self):
        # two lists that add only their folder and tv.json: plain merges
        self.pr(101, "Add Hisense G list", [
            ("examples/hisense-g/debloat.txt", "# Hisense G\ncom.hisense.ads\n"),
            ("examples/hisense-g/tv.json", tv_json("Hisense G", "Hisense")),
        ], verdict="merge", priority="p1")
        self.pr(102, "Add Vu Z list", [
            ("examples/vu-z/debloat.txt", "# Vu Z\ncom.vu.ads\n"),
            ("examples/vu-z/tv.json", tv_json("Vu Z", "Vu", "Android 10")),
        ], verdict="merge")
        # an older list PR: rows in both tables and the brand line, no tv.json
        self.pr(103, "Add Hitachi H list", [
            ("examples/hitachi-h/debloat.txt", "# Hitachi H\ncom.hitachi.ads\n"),
            ("README.md", "|---|---|\n| Sony A |", "|---|---|\n| Hitachi H | Android 9 |\n| Sony A |"),
            ("README.md", "Sony · Xiaomi ·", "Hitachi · Sony · Xiaomi ·"),
            ("examples/README.md", "|---|---|---|---|\n| `sony-a/`",
             "|---|---|---|---|\n| `hitachi-h/` | Hitachi H | Android 9 | Hitachi ads off |\n| `sony-a/`"),
            # a hand-written part of the same file, outside the generated table: kept
            ("examples/README.md", "a one-day report\n", "a one-day report\n- [Hitachi K](../docs/devices/hk.md): notes\n"),
        ], verdict="merge")
        # a showcase PR that edits a prose row of another README table: not a generated section, a plain merge
        self.pr(109, "SHOWCASE: add Glass", [
            ("SHOWCASE.md", "| Glass | a home screen |\n"),
            ("README.md", "where two projects live", "where three projects live"),
        ], verdict="merge")
        # merge with a fix: the list forgot its tv.json
        self.pr(104, "Add TCL C list", [("examples/tcl-c/debloat.txt", "# TCL C\ncom.tcl.ads\n")],
                verdict="merge-with-fix", fix="Add examples/tcl-c/tv.json (TV, OS, brand, notes) for the tables.")
        self.pr(105, "Add Sony Q list", [("examples/sony-q/debloat.txt", "# Sony Q\ncom.sony.remotepair\n")],
                verdict="rework", ask="Keep com.sony.remotepair enabled: without it a reset remote can't pair again.")
        self.pr(106, "Add Sony A list again", [("examples/sony-a2/debloat.txt", "# Sony A\ncom.example.ads\n")],
                verdict="close", reason="Thanks for this! The Sony A is already on the list, so this one is a duplicate.")
        self.pr(107, "Launcher clock", [("launcher/Clock.java", "class C {}\n")], verdict="hold",
                question="launcher code", labels=["launcher"])
        # a merge suggestion outside the wave's paths: listed for the maintainer, never touched by /approve
        self.pr(108, "Weather card", [("launcher/Weather.java", "class W {}\n")], verdict="merge", version=2)

    def run_batch(self, propose=None):
        q.upsert(self.api, "2026-10-22")
        issue = max(self.api.issues)
        sh(self.tmp.name, "clone", "-q", self.bare, self.work)
        ledger = Ledger(os.path.join(self.tmp.name, "ledger.jsonl"), 5.0)
        cfg = Config(approver="Gathin23", git=Git(self.work), propose=propose, ledger=ledger,
                     counts=counts_runner(f"{sys.executable} {COUNTS} ."), sleep=lambda s: None, log=lambda s: None,
                     today="2026-10-22")
        return issue, Executor(self.api, cfg).run(issue, commands.parse("/approve"))

    def test_red_ci_on_a_bot_branch_stops_the_batch(self):
        self.scenario()
        self.api.red_branches = {"bot/merge-103"}
        issue, res = self.run_batch()
        self.assertTrue(res["stopped"].startswith("#103: CI on bot PR #"), res["stopped"])
        self.assertEqual(sorted(res["merged"]), [101, 102])
        self.assertFalse(self.api.pr(103)["merged"])
        self.assertNotIn(104, {o["pr"] for o in res["outcomes"]})  # never attempted
        self.assertEqual(res["counts"]["status"], "merged")  # the counts PR still covers what did merge
        self.assertIn("**Stopped at #103", self.api.comments[issue][-1]["body"])

    def test_full_batch(self):
        self.scenario()
        q.upsert(self.api, "2026-10-22")
        issue = max(self.api.issues)
        body = self.api.issues[issue]["body"]
        for n in (101, 102, 103, 104, 105, 106, 109):
            self.assertIn(f"- [ ] #{n} ", body)
        self.assertIn("- #107 Launcher clock", body)
        self.assertIn("- #108 Weather card (by someone) · p2 · suggests merge · changes launcher/Weather.java", body)

        sh(self.tmp.name, "clone", "-q", self.bare, self.work)  # what actions/checkout gives the job
        proposals = []

        def fake_propose(**kw):
            proposals.append(kw)
            self.assertIn("examples/tcl-c/debloat.txt", kw["context_files"])
            return {"edits": [{"path": "examples/tcl-c/tv.json", "search": "",
                               "replace": tv_json("TCL C", "TCL", "Android 12")}],
                    "summary": "On merge: added examples/tcl-c/tv.json for the README tables"}

        self.api.check_state[self.api.prs[104]["head_sha"]] = {"state": "failure", "failed": ["Lists, tools and docs"],
                                                                 "pending": []}  # red until the fix adds tv.json
        ledger = Ledger(os.path.join(self.tmp.name, "ledger.jsonl"), 5.0)
        cfg = Config(approver="Gathin23", git=Git(self.work), propose=fake_propose, ledger=ledger,
                     counts=counts_runner(f"{sys.executable} {COUNTS} ."), sleep=lambda s: None, log=lambda s: None,
                     today="2026-10-22")
        res = Executor(self.api, cfg).run(issue, commands.parse("/approve\nlooks good"))

        out = {o["pr"]: o for o in res["outcomes"]}
        self.assertEqual(res["stopped"], "", res["audit"])
        self.assertEqual({n: out[n]["status"] for n in out},
                         {101: "done", 102: "done", 103: "done", 104: "done", 105: "done", 106: "done", 109: "done"})
        self.assertNotIn(107, out)
        self.assertNotIn(108, out)
        self.assertEqual(sorted(res["merged"]), [101, 102, 103, 104, 109])
        self.assertEqual(len(proposals), 1)

        # main: one merge commit per PR on the first-parent line, then the counts PR
        log = sh(self.bare, "log", "--first-parent", "--format=%s", "main").splitlines()
        self.assertEqual(log[:6], ["README counts after today's merges", "Merge PR #104: Add TCL C list",
                                   "Merge PR #109: SHOWCASE: add Glass", "Merge PR #103: Add Hitachi H list",
                                   "Merge PR #102: Add Vu Z list", "Merge PR #101: Add Hisense G list"])
        self.assertIn("On merge: added examples/tcl-c/tv.json", sh(self.bare, "log", "--format=%B", "-n", "40", "main"))
        # bot branches went through PRs; the originals are marked merged because their heads are on main
        bot_prs = [c for c in self.api.calls if c[0] == "create_pr"]
        self.assertEqual([c[2] for c in bot_prs], ["bot/merge-103", "bot/merge-104", "bot/counts-2026-10-22"])
        self.assertTrue(bot_prs[1][3].startswith("Merge #104 with fix: "))
        for n in (101, 102, 103, 104, 109):
            self.assertTrue(self.api.pr(n)["merged"], n)
            self.assertIn("Merged, thank", self.api.comments[n][-1]["body"])
        self.assertIn("On merge: Added examples/tcl-c/tv.json for the README tables. (through #",
                      self.api.comments[104][-1]["body"])

        # #103's rows became its tv.json on the bot branch; its README edits did not reach main as such
        hitachi = json.loads(sh(self.bare, "show", "main:examples/hitachi-h/tv.json"))
        self.assertEqual(hitachi, {"tv": "Hitachi H", "os": "Android 9", "brand": "Hitachi", "notes": "Hitachi ads off"})
        body103 = next(p["body"] for p in self.api.prs.values() if p.get("head_ref") == "bot/merge-103")
        self.assertIn("examples/hitachi-h/tv.json", body103)

        # the tree on main after the counts PR: every list's row once, in alphabetical order; counts regenerated
        readme = sh(self.bare, "show", "main:README.md")
        rows = ["| Hisense G | Android 11 |", "| Hitachi H | Android 9 |", "| Sony A | Android 9 |",
                "| TCL B | Android 11 |", "| TCL C | Android 12 |", "| TCL D | Android 11 |", "| Vu Z | Android 10 |",
                "| Xiaomi F | Android 9 |"]
        self.assertIn("|---|---|\n" + "\n".join(rows) + "\n", readme)
        self.assertIn('alt="8 TV models · 6 brands · 2 languages · 429 KB launcher.', readme)
        self.assertIn("**TCL** 3 ·\nHisense · Hitachi · Sony · Vu · Xiaomi ·", readme)
        ex = sh(self.bare, "show", "main:examples/README.md")
        self.assertEqual(ex.count("| `hitachi-h/` | Hitachi H | Android 9 | Hitachi ads off |"), 1)
        self.assertEqual(ex.count("| `hisense-g/` |"), 1)
        # hand-written parts of both files kept: #103's note line, #109's prose row (merged without a bot branch)
        self.assertIn("- [Old K](../docs/devices/old-k.md): a one-day report\n- [Hitachi K](../docs/devices/hk.md): notes",
                      ex)
        self.assertIn("where three projects live", readme)
        self.assertIn('("8", "TV MODELS"), ("6", "BRANDS")', sh(self.bare, "show", "main:tools/readme_stats.py"))
        counts_body = next(p["body"] for p in self.api.prs.values() if p.get("head_ref") == "bot/counts-2026-10-22")
        self.assertIn("please check the spelling): Hisense, Hitachi, Vu.", counts_body)

        # rework, close, held
        self.assertIn("needs-rework", self.api.prs[105]["labels"])
        self.assertIn("Keep com.sony.remotepair enabled", self.api.comments[105][-1]["body"])
        self.assertEqual(self.api.prs[105]["state"], "open")
        self.assertEqual(self.api.prs[106]["state"], "closed")
        self.assertIn("already on the list", self.api.comments[106][-1]["body"])
        self.assertEqual(self.api.prs[107]["state"], "open")
        self.assertEqual(len(self.api.comments[107]), 1)  # only the review
        self.assertEqual((self.api.prs[108]["state"], len(self.api.comments[108])), ("open", 1))

        # the queue issue: ticked, with an audit log
        body = self.api.issues[issue]["body"]
        for n in (101, 102, 103, 104, 105, 106, 109):
            self.assertIn(f"- [x] #{n} ", body)
        audit = self.api.comments[issue][-1]["body"]
        self.assertIn("5 merged", audit)
        self.assertIn("README counts: #", audit)
        self.assertIn("merged (8 TV models · 6 brands · 2 languages)", audit)
        self.assertIn("“looks good”", audit)
        self.assertEqual(set(self.api.deleted), {"bot/merge-103", "bot/merge-104", "bot/counts-2026-10-22"})

    def test_counts_in_jobs_of_their_own(self):
        """The workflow's split: the act job runs no counts; a job without credentials runs the repo's counts
        tools and makes a patch; the counts-pr job checks the patch and opens the counts PR."""
        self.scenario()
        q.upsert(self.api, "2026-10-22")
        issue = max(self.api.issues)
        sh(self.tmp.name, "clone", "-q", self.bare, self.work)
        note = "README counts: a separate job redraws them."
        cfg = Config(approver="Gathin23", git=Git(self.work), propose=None, sleep=lambda s: None, log=lambda s: None,
                     today="2026-10-22", counts_note=note)
        res = Executor(self.api, cfg).run(issue, commands.parse("/approve except #104"))
        self.assertEqual(sorted(res["merged"]), [101, 102, 103, 109])
        self.assertIsNone(res["counts"])
        self.assertIn(note, self.api.comments[issue][-1]["body"])

        # the counts job: a plain clone (no push access needed), the counts script, a binary patch
        plain, out = os.path.join(self.tmp.name, "plain"), os.path.join(self.tmp.name, "counts")
        os.makedirs(out)
        sh(self.tmp.name, "clone", "-q", self.bare, plain)
        r = subprocess.run([sys.executable, COUNTS, plain], capture_output=True, text=True, check=True)
        write(out, "counts.json", r.stdout.strip().splitlines()[-1])
        write(out, "counts.patch", sh(plain, "diff", "--binary") + "\n")

        # the counts-pr job: its own checkout with push access
        work2 = os.path.join(self.tmp.name, "work2")
        sh(self.tmp.name, "clone", "-q", self.bare, work2)
        r = counts_pr("o/r", work2, out, res["merged"], api=self.api,
                      cfg={"sleep": lambda s: None, "log": lambda s: None, "today": "2026-10-22"})
        self.assertEqual(r["status"], "merged", r)
        self.assertEqual(sh(self.bare, "log", "-1", "--format=%s", "main"), "README counts after today's merges")
        self.assertIn('alt="7 TV models · 6 brands', sh(self.bare, "show", "main:README.md"))

        # a patch that reaches past the counts files is refused before anything is applied
        write(out, "counts.patch", "diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml\n+x\n")
        r = counts_pr("o/r", work2, out, [101], api=self.api, cfg={"sleep": lambda s: None, "log": lambda s: None})
        self.assertEqual(r["status"], "refused")

    def test_bot_cannot_push_main(self):
        sh(self.tmp.name, "clone", "-q", self.bare, self.work)
        g = Git(self.work)
        with self.assertRaises(Exception):
            g.push("main")


if __name__ == "__main__":
    unittest.main()
