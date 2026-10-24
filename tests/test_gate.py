"""The launch gate, the wave size cap, main's CI around a wave, and the counts patch check."""
import unittest

from maintainer_bot.phase2 import commands, gate, queue as q
from maintainer_bot.phase2.cli import check_counts_patch
from maintainer_bot.phase2.executor import Config, Executor
from tests.fake_github import FakeApi


def f(name, patch="+x", old=None):
    return {"filename": name, "previous_filename": old, "status": "renamed" if old else "modified", "patch": patch}


GREEN = {"state": "success", "failed": [], "pending": []}
RED = {"state": "failure", "failed": ["Launcher build and unit tests"], "pending": []}
RUNNING = {"state": "pending", "failed": [], "pending": ["Launcher build and unit tests"]}


class Gate(unittest.TestCase):
    def test_inside(self):
        for files in ([f("examples/tcl-55c728/debloat.txt"), f("examples/README.md")],
                      [f("examples/tcl-55c728/config.json"), f("examples/tcl-55c728/home.jpg")],
                      [f("docs/devices/tcl-55c728.md"), f("docs/devices/tcl-home.png")],
                      [f("themes/amber/config.json"), f("themes/amber/screenshot.jpg")],
                      [f("SHOWCASE.md")],
                      [f("README.md", "@@ -1,2 +1,3 @@\n | TV | OS |\n+| TCL C | Android 12 |\n-| Old | x |\n+\n")],
                      [f("launcher/app/src/main/res/values-de/strings.xml")],
                      [f("launcher/app/src/main/res/values-zh-rCN/strings.xml")],
                      [f("launcher/app/src/main/res/values-b+sr+Latn/strings.xml")]):
            self.assertEqual(gate.check(files), "", files)

    def test_outside(self):
        cases = {
            "launcher/app/src/main/java/com/gathin/tvhome/MainActivity.java": "changes launcher/",
            "launcher/app/src/main/res/values/strings.xml": "changes launcher/",      # English source strings
            "launcher/app/src/main/res/values-night/strings.xml": "changes launcher/",
            "launcher/app/src/main/res/values-de/config.xml": "changes launcher/",
            "addons/clock/app/build.gradle": "changes addons/",
            "tools/readme_stats.py": "changes tools/",
            "tools/readme_card.py": "changes tools/",
            "PROMPT.md": "changes PROMPT.md",
            ".github/workflows/ci.yml": "changes .github/",
            "examples/anker/restore.sh": "is not a list, note or picture",
            "examples/anker/build.py": "is not a list, note or picture",
            "docs/page.html": "is not a list, note or picture",
            "examples/../tools/x.txt": "changes examples/../tools/x.txt",
            "README.ja.md": "changes README.ja.md",
        }
        for path, why in cases.items():
            self.assertIn(why, gate.check([f("examples/a/debloat.txt"), f(path)]), path)

    def test_readme_brand_line(self):
        bump = ("@@ -9 +9 @@\n-**TCL** 57 · **Sony** 31 · **Amazon Fire TV** 7 ·\n"
                "+**TCL** 58 · **Sony** 31 · **Amazon Fire TV** 7 ·\n-Acer · OK. · PRISM+ ·\n+Acer · KTC · OK. · PRISM+ ·\n")
        self.assertEqual(gate.check([f("README.md", bump)]), "")
        for line in ("+Hello world", "+**TCL** 3 · <img src=x onerror=alert(1)>", "+[TCL](https://x.example) ·",
                     "+Install it, then press OK ·"):
            self.assertIn("outside the table rows", gate.check([f("README.md", "@@ -1 +1 @@\n" + line)]), line)

    def test_readme_outside_the_tables(self):
        self.assertIn("outside the table rows",
                      gate.check([f("README.md", "@@ -1 +1 @@\n-Old intro\n+New intro, with a link\n")]))
        self.assertIn("outside the table rows", gate.check([f("README.md", None)]))  # no patch: fail closed

    def test_rename_out_of_the_launcher(self):
        self.assertIn("changes launcher/", gate.check([f("examples/x/notes.md",
                                                           old="launcher/app/src/main/AndroidManifest.xml")]))

    def test_empty_and_too_many(self):
        self.assertEqual(gate.check([]), "no files")
        self.assertIn("files", gate.check([f(f"examples/x{i}/debloat.txt") for i in range(300)]))

    def test_fix_edits(self):
        self.assertEqual(gate.edits_reason([{"path": "README.md", "search": "| TCL B |",
                                             "replace": "| TCL B |\n| TCL C |"}]), "")
        self.assertIn("table rows", gate.edits_reason([{"path": "README.md", "search": "intro", "replace": "x"}]))
        self.assertIn("launcher/", gate.edits_reason([{"path": "launcher/a.java", "search": "a", "replace": "b"}]))


def _wave(n_prs, **cfg):
    api = FakeApi()
    for i in range(1, n_prs + 1):
        api.add_pr(i, title=f"Add list {i}", sha=f"{i:040d}", verdict="merge")
    q.upsert(api, "2026-10-27")
    issue = max(api.issues)
    ex = Executor(api, Config(sleep=lambda s: None, log=lambda s: None, **cfg))
    return api, issue, ex


class Queue(unittest.TestCase):
    def test_outside_items_have_no_checkbox(self):
        api = FakeApi()
        api.add_pr(1, title="Add TCL list", sha="1" * 40, verdict="merge")
        api.add_pr(2, title="Launcher: clock size", sha="2" * 40, verdict="merge",
                   paths=["launcher/app/src/main/java/Clock.java"])
        items, stats = q.collect(api)
        self.assertEqual((items[1]["outside"], items[2]["outside"]), ("", "changes launcher/app/src/main/java/Clock.java"))
        body = q.render("2026-10-27", items, stats)
        self.assertIn("- [ ] #1 Add TCL list", body)
        self.assertIn("### For a maintainer: outside the wave's paths (1)", body)
        self.assertIn("- #2 Launcher: clock size (by someone) · p2 · suggests merge · changes launcher/", body)
        self.assertNotIn("- [ ] #2", body)
        self.assertEqual(q.read_data(body)["items"]["2"]["o"], 1)

    def test_close_still_moves_an_outside_pr(self):
        api = FakeApi()
        api.add_pr(2, title="Launcher: clock size", sha="2" * 40, verdict="merge", paths=["launcher/Clock.java"])
        q.upsert(api, "2026-10-27")
        issue = max(api.issues)
        res = Executor(api, Config(sleep=lambda s: None, log=lambda s: None)).run(
            issue, commands.parse("/approve\n/close #2 the clock stays as it is"))
        self.assertEqual([(o["pr"], o["status"]) for o in res["outcomes"]], [(2, "done")])
        self.assertEqual(api.prs[2]["state"], "closed")


class WaveSize(unittest.TestCase):
    def test_cap(self):
        api, issue, ex = _wave(30, max_wave=25)
        res = ex.run(issue, commands.parse("/approve"))
        done = [o["pr"] for o in res["outcomes"] if o["status"] == "done"]
        capped = [o for o in res["outcomes"] if "wave size cap" in o["detail"]]
        self.assertEqual((len(done), len(capped)), (25, 5))
        self.assertEqual(len([c for c in api.calls if c[0] == "merge"]), 25)
        # the next /approve on the same issue picks up the rest
        res = Executor(api, Config(sleep=lambda s: None, log=lambda s: None)).run(issue, commands.parse("/approve"))
        self.assertEqual(len([o for o in res["outcomes"] if o["status"] == "done"]), 5)

    def test_skips_do_not_use_the_cap(self):
        api, issue, ex = _wave(4, max_wave=3)
        api.check_state["1".zfill(40)] = RUNNING  # #1 is skipped for today
        res = ex.run(issue, commands.parse("/approve"))
        self.assertEqual([(o["pr"], o["status"]) for o in res["outcomes"]],
                         [(1, "skipped"), (2, "done"), (3, "done"), (4, "done")])

    def test_dry_run_reports_the_cap(self):
        api, issue, ex = _wave(4, max_wave=2, dry_run=True)
        res = ex.run(issue, commands.parse("/approve"))
        self.assertEqual([o["status"] for o in res["outcomes"]], ["would", "would", "skipped", "skipped"])


class MainCI(unittest.TestCase):
    def test_red_main_stops_before_the_wave(self):
        api, issue, ex = _wave(3)
        api.main_checks = [RED]
        res = ex.run(issue, commands.parse("/approve"))
        self.assertEqual(res["outcomes"], [])
        self.assertIn("main's CI failing: Launcher build and unit tests before the wave", res["stopped"])
        self.assertFalse([c for c in api.calls if c[0] == "merge"])
        self.assertIn("**Stopped because main's CI failing", api.comments[issue][-1]["body"])

    def test_waits_for_running_main(self):
        api, issue, ex = _wave(2)
        api.main_checks = [RUNNING, RUNNING, GREEN]
        res = ex.run(issue, commands.parse("/approve"))
        self.assertEqual(res["stopped"], "")
        self.assertEqual(len([c for c in api.calls if c[0] == "merge"]), 2)

    def test_main_timeout_stops(self):
        api, issue, ex = _wave(2, ci_timeout=60, poll=30)
        api.main_checks = [RUNNING]
        res = ex.run(issue, commands.parse("/approve"))
        self.assertIn("main's CI timed out before the wave", res["stopped"])
        self.assertFalse([c for c in api.calls if c[0] == "merge"])

    def test_red_after_merges_stops_the_wave(self):
        api, issue, ex = _wave(6, main_every=2)
        api.main_checks = [GREEN, GREEN, RED]  # before the wave, after 2 merges, after 4 merges
        res = ex.run(issue, commands.parse("/approve"))
        self.assertEqual(len(res["merged"]), 4)
        self.assertIn("main's CI failing: Launcher build and unit tests after 4 merges", res["stopped"])
        self.assertIn("**Stopped because main's CI", api.comments[issue][-1]["body"])

    def test_main_is_checked_after_the_last_merges(self):
        api, issue, ex = _wave(3, main_every=5)
        api.main_checks = [GREEN, RED]
        res = ex.run(issue, commands.parse("/approve"))
        self.assertEqual(len(res["merged"]), 3)
        self.assertIn("after the wave's 3 merges", res["stopped"])
        self.assertEqual(len([c for c in api.calls if c[0] == "main-checks"]), 2)

    def test_a_close_only_wave_still_checks_main_first(self):
        api = FakeApi()
        api.add_pr(1, title="Dup list", sha="1" * 40, verdict="close", reason="A duplicate of #2.")
        q.upsert(api, "2026-10-27")
        issue = max(api.issues)
        res = Executor(api, Config(sleep=lambda s: None, log=lambda s: None)).run(issue, commands.parse("/approve"))
        self.assertEqual(res["stopped"], "")
        self.assertEqual(api.prs[1]["state"], "closed")  # main green by default

    def test_unreadable_main_fails_closed(self):
        api, issue, ex = _wave(1)

        def boom(branch):
            raise RuntimeError("HTTP 502")
        api.branch_sha = boom
        res = ex.run(issue, commands.parse("/approve"))
        self.assertIn("could not be read", res["stopped"])
        self.assertFalse([c for c in api.calls if c[0] == "merge"])

    def test_dry_run_reads_main_once(self):
        api, issue, ex = _wave(2, dry_run=True)
        api.main_checks = [RED]
        res = ex.run(issue, commands.parse("/approve"))
        self.assertEqual(ex.main_state, "failure")
        self.assertIn("main's CI is failing before the wave", res["stopped"])
        self.assertEqual([o["status"] for o in res["outcomes"]], ["would", "would"])  # still listed


class CountsPatch(unittest.TestCase):
    ok = ("diff --git a/README.md b/README.md\n--- a/README.md\n+++ b/README.md\n@@ -1 +1 @@\n-**TCL** 2 ·\n"
          "+**TCL** 3 ·\n"
          "diff --git a/tools/readme_stats.py b/tools/readme_stats.py\n--- a/tools/readme_stats.py\n"
          "+++ b/tools/readme_stats.py\n@@ -15 +15 @@\n-STATS = [(\"4\", \"TV MODELS\")]\n"
          "+STATS = [(\"5\", \"TV MODELS\")]\n\n"
          "diff --git a/docs/card.jpg b/docs/card.jpg\nGIT binary patch\nliteral 10\nzcmV-^\n")

    def test_counts_files_only(self):
        self.assertEqual(check_counts_patch(self.ok), "")
        self.assertEqual(check_counts_patch(""), "")
        self.assertIn("touches .github/workflows/ci.yml",
                      check_counts_patch("diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml\n+x\n"))
        self.assertIn("touches tools/readme_card.py",
                      check_counts_patch("diff --git a/tools/readme_card.py b/tools/readme_card.py\n+x\n"))
        self.assertIn("touches README.md",  # a rename is not a counts change
                      check_counts_patch("diff --git a/README.md b/docs/card.jpg\n"))

    def test_stats_line_only(self):
        bad = self.ok.replace('+STATS = [("5", "TV MODELS")]', '+import os; os.system("curl evil")')
        self.assertIn("beyond the STATS line", check_counts_patch(bad))


if __name__ == "__main__":
    unittest.main()
