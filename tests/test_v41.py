"""v4.1: the fixes from the 22 Oct live runs (Rounds O and Q)."""
import os
import tempfile
import unittest

from maintainer_bot import facts, live, v4
from maintainer_bot.router import ToolCallFailed
from tests.test_live import FakeGH, snap


def f(path, patch="", status="modified"):
    return {"path": path, "additions": sum(1 for l in patch.splitlines() if l.startswith("+")), "deletions": 0,
            "status": status, "patch": patch}


def fx_of(files, **kw):
    return facts.compute_v4({"files": files}, **kw)


def res(verdict, confidence=0.9, **kw):
    return {"verdict": verdict, "confidence": confidence, **kw}


class AddonsTest(unittest.TestCase):
    """#870, #872, #936, #971, #984."""

    def test_the_addon_gradle_wrapper_is_not_a_prebuilt_binary(self):
        fx = fx_of([f("addons/weather/gradle/wrapper/gradle-wrapper.jar", status="added"),
                    f("addons/weather/README.md", "+## Permissions\n+none\n", status="added")])
        self.assertEqual(fx["binary_files"], [])
        for other in ("addons/weather/libs/okhttp.jar", "gradle/wrapper/gradle-wrapper.jar",
                      "addons/weather/app/gradle-wrapper.jar", "addons/weather/app.apk"):
            self.assertEqual(fx_of([f(other, status="added")])["binary_files"], [other])

    def test_never_the_move_to_addons_template_for_an_addon(self):
        fx = fx_of([f("addons/weather/README.md", "+## Permissions\n", status="added")])
        v, why, _ = v4.final(res("addon", 0.9), fx)
        self.assertEqual(v, "hold")
        self.assertIn("already an add-on", why)
        self.assertEqual(v4.final(res("merge", 0.9), fx)[0], "merge")  # judged on its merits
        # a launcher feature that should become an add-on still gets the invitation
        self.assertEqual(v4.final(res("addon", 0.9), fx_of([f("launcher/app/src/main/java/X.java", "+x\n")]))[0],
                         "addon")


class RebaseTest(unittest.TestCase):
    def test_conflicts_are_a_rebase_ask_whatever_the_model_says(self):
        fx = fx_of([f("examples/a/debloat.txt", "+com.a.ads\n")], conflicts_with_main=True)
        fx["conflict_files"] = ["README.md", "examples/README.md"]
        for verdict, conf in (("merge", 0.95), ("merge", 0.3), ("hold", 0.0), ("rework", 0.5)):
            v, why, fix = v4.final(res(verdict, conf), fx)
            self.assertEqual(v, "rework", verdict)
            self.assertIn("rebase onto main", fix)
            self.assertIn("`README.md`", fix)
            self.assertIn("`examples/README.md`", fix)
        self.assertEqual(v4.final(res("close", 0.9), fx)[0], "close")  # closing anyway: no rebase ask

    def test_unknown_files_still_ask(self):
        fx = fx_of([f("tools/theme.sh", "+x\n")], conflicts_with_main=True)
        self.assertEqual(v4.final(res("merge"), fx)[2], "please rebase onto main: it conflicts with main")

    def test_conflict_files_from_two_compares(self):
        class G(FakeGH):
            def get(self, path, **kw):
                if path == "/compare/main...abcdef1234567890":
                    return {"merge_base_commit": {"sha": "base"}}
                if path == "/compare/base...main":
                    return {"files": [{"filename": "README.md"}, {"filename": "tools/x.py"}]}
                return {}
        s = snap(["README.md", "examples/a/debloat.txt"])
        self.assertEqual(live.conflict_files(G(s), s), ["README.md"])


class RebaseAskShownTest(unittest.TestCase):
    def test_the_rebase_ask_and_files_are_in_the_comment(self):
        s = snap(["tools/theme.sh"])
        s["mergeable"] = False
        fake = FakeGH(s)
        orig = (live.GitHub, live.snapshot, live.repo_context, live.v4.judge, live.conflict_files)
        live.GitHub, live.snapshot = fake, (lambda gh, n: s)
        live.repo_context = lambda gh, b: {"list_folders": set(), "locales": []}
        live.conflict_files = lambda gh, snap: ["tools/theme.sh"]
        live.v4.judge = lambda *a, **k: {"verdict": "rework", "confidence": 0.8, "fix": "add a test", "reasons": [],
                                         "comment": "Thanks for the fix!", "specific": "the fix"}
        try:
            with tempfile.TemporaryDirectory() as d:
                r = live.review("o/r", 7, rules_md="", precedents="", ledger_path=os.path.join(d, "l.jsonl"))
        finally:
            live.GitHub, live.snapshot, live.repo_context, live.v4.judge, live.conflict_files = orig
        self.assertEqual(r["verdict"], "rework")
        self.assertIn("please rebase onto main: it conflicts with main in `tools/theme.sh`. Also: add a test", r["comment"])


class LeanTest(unittest.TestCase):
    def test_lean_from_the_model_or_the_second_opinion(self):
        self.assertEqual(v4.lean(res("merge-with-fix", 0.72)), ("merge", 0.72))
        self.assertEqual(v4.lean(res("showcase", 0.6)), ("close", 0.6))
        self.assertEqual(v4.lean(res("theme", 0.6)), ("rework", 0.6))
        self.assertEqual(v4.lean(res("hold", 0.0, second={"verdict": "rework", "confidence": 0.8})), ("rework", 0.8))
        self.assertIsNone(v4.lean(res("hold", 0.0)))

    def test_label_and_first_line(self):
        s = snap(["launcher/app/src/main/java/X.java"])
        fx = facts.compute_v4(s)
        body = live.render(s, verdict="hold", model_verdict="merge", priority="", reason="Thanks!", fix="",
                           why_held="confidence 0.72 is below 0.75", fx=fx, ptype="launcher", cost=0,
                           leaning=("merge", 0.72))
        self.assertEqual(body.splitlines()[1],
                         "**maintainer-bot review** · this one needs **a maintainer decision** · Leans: merge (72%)")
        labels = live.labels_for("launcher", "hold", "", fx, s, lean=("merge", 0.72))
        self.assertIn("bot-leans:merge", labels)
        self.assertIn("needs-maintainer", labels)
        self.assertNotIn("bot-leans:merge", live.labels_for("launcher", "merge", "p2", fx, s, lean=("merge", 0.9)))
        self.assertIn("bot-leans:merge", live.BOT_OWNED)  # removed again once the PR stops being held


class DuplicatesTest(unittest.TestCase):
    """#842/#873 (same issue #832), #924/#947 (the same one-line fix), #927 (already on main)."""

    def pr(self, n, title, files, body="", created="2026-10-22T10:00:00Z"):
        return {"pr": n, "title": title, "body": body, "created_at": created, "files": files}

    def test_the_later_of_two_fixes_for_one_issue(self):
        a = self.pr(842, "tools: write theme files through the ThemeProvider before cp (#832)", ["tools/theme.sh"],
                    created="2026-10-22T09:00:00Z")
        b = self.pr(873, "theme.sh: push through ThemeProvider", ["tools/theme.sh", "README.md"], body="Fixes #832")
        fx = facts.duplicate_facts(b, [a])
        self.assertTrue(fx["possible_duplicates"][0]["strong"])
        self.assertEqual(fx["possible_duplicates"][0]["pr"], 842)
        self.assertEqual(facts.duplicate_facts(a, [b]), {})  # the earlier one is not the duplicate
        v, why, _ = v4.final(res("merge", 0.9), fx)
        self.assertEqual(v, "hold")
        self.assertIn("duplicate of #842", why)
        self.assertEqual(v4.final(res("close", 0.8), fx)[0], "close")

    def test_same_title_same_file(self):
        a = self.pr(924, "b64push: check md5 before replacing the file", ["tools/b64push.py"],
                    created="2026-10-22T09:00:00Z")
        b = self.pr(947, "b64push: check md5 before replacing the file on the TV", ["tools/b64push.py"])
        self.assertTrue(facts.duplicate_facts(b, [a])["possible_duplicates"][0]["strong"])

    def test_shared_table_files_alone_are_not_a_duplicate(self):
        a = self.pr(1, "Add TCL 55C745 list", ["examples/tcl-55c745/debloat.txt", "README.md"], created="0")
        b = self.pr(2, "Add Sony KD-55X list", ["examples/sony-kd-55x/debloat.txt", "README.md"])
        self.assertEqual(facts.duplicate_facts(b, [a]), {})

    def test_weak_overlap_is_only_a_note(self):
        a = self.pr(1, "Home guard: count the factory launcher", ["tools/disable.sh"], body="for #884", created="0")
        b = self.pr(2, "Home guard: explain the factory launcher in TROUBLESHOOTING", ["docs/devices/mi.md"],
                    body="see #884")
        fx = facts.duplicate_facts(b, [a])
        self.assertFalse(fx["possible_duplicates"][0]["strong"])
        self.assertEqual(v4.final(res("merge", 0.9), fx)[0], "merge")

    def test_already_on_main(self):
        me = {**self.pr(927, "b64push: fix", ["tools/b64push.py"]),
              "file_patches": [f("tools/b64push.py", "+    digest = hashlib.md5(data).hexdigest()\n"
                                                     "+    if digest != remote_md5(path):\n"
                                                     "+        raise SystemExit('md5 mismatch')\n")]}
        main = "x\n    digest = hashlib.md5(data).hexdigest()\n    if digest != remote_md5(path):\n" \
               "        raise SystemExit('md5 mismatch')\n"
        fx = facts.duplicate_facts(me, [], main_texts={"tools/b64push.py": main})
        self.assertEqual(fx["already_on_main_live"]["share"], 1.0)
        self.assertIn("already on main", v4.final(res("rework", 0.9), fx)[1])


class NoInventedFlagsTest(unittest.TestCase):
    """#982 got a pm hide flag from a wrapped README sentence. Hard flags fire only on text in the diff."""

    def test_prose_is_not_pm_hide(self):
        fx = fx_of([f("examples/grundig-kunyang/README.md",
                      "+Private DNS hides trackers, but it does not\n+  block YouTube ads. Undo: `settings put`.\n"
                      "+  hide the ads row in settings\n")])
        self.assertEqual(fx["hide_without_undo"], [])
        self.assertNotIn("hide_without_undo", fx["evidence"])

    def test_real_pm_hide_is_still_caught(self):
        for path, line in (("examples/a/debloat.txt", "+# Use `pm hide` instead: disable-user is denied\n"),
                           ("examples/a/README.md", "+adb shell pm hide com.a.ads\n"),
                           ("examples/a/debloat.txt", "+hide com.a.ads\n")):
            self.assertTrue(fx_of([f(path, line)])["hide_without_undo"], line)

    def test_no_permission_or_network_from_comments(self):
        fx = fx_of([f("launcher/app/src/main/AndroidManifest.xml",
                      '+<!-- <uses-permission android:name="android.permission.INTERNET"/> -->\n'),
                    f("launcher/app/src/main/java/com/gathin/tvhome/X.java",
                      "+    // never use HttpURLConnection here\n+     * no WebView, no java.net.URL\n")])
        self.assertFalse(fx.get("new_permissions"))
        self.assertFalse(fx.get("network_use"))
        self.assertFalse(fx["adds_internet_permission"])

    def test_every_hard_flag_quotes_a_line_of_the_diff(self):
        patch = ("+com.android.vending\n+com.tcl.autopair\n+com.android.permissioncontroller\n"
                 "+# applied with pm hide com.x.y\n")
        files = [f("examples/a/debloat.txt", patch),
                 f("launcher/app/src/main/AndroidManifest.xml",
                   '+<uses-permission android:name="android.permission.INTERNET"/>\n')]
        fx = fx_of(files)
        text = "\n".join(x["patch"] for x in files)
        for key in ("protected_packages_disabled", "pairing_or_input_packages_disabled", "core_packages_disabled",
                    "hide_without_undo", "adds_internet_permission"):
            self.assertTrue(fx[key], key)
            self.assertIn(fx["evidence"][key], text, key)
        self.assertEqual(fx_of([f("examples/a/debloat.txt", "+com.a.ads\n")])["evidence"], {})


class CorePackagesTest(unittest.TestCase):
    """cleanyourtv #884 (main 22dc48fe): the same block as tools/recovery.py."""
    CORE = ["com.google.android.permissioncontroller", "com.android.packageinstaller", "com.android.ext.services",
            "com.google.android.ext.shared", "com.android.modulemetadata",
            "com.google.android.overlay.modules.ext.services", "com.android.systemui", "com.android.shell",
            "com.android.phone", "com.android.settings", "com.android.tv.settings", "com.android.providers.settings",
            "com.android.providers.media", "android"]
    NOT_CORE = ["com.android.providers.calendar", "com.android.providers.contacts",
                "com.android.providers.userdictionary", "com.android.providers.blockednumber",
                "com.android.settings.intelligence", "com.android.tv.settings.overlay", "com.android.phone.extra",
                "com.google.android.tungsten.setupwraith", "com.android.shell2", "com.example.android.ext.services"]

    def test_core_is_blocked_and_look_alikes_are_not(self):
        for pkg in self.CORE:
            self.assertEqual(fx_of([f("examples/a/debloat.txt", f"+{pkg}  # x\n")])["core_packages_disabled"],
                             [pkg], pkg)
        for pkg in self.NOT_CORE:
            self.assertEqual(fx_of([f("examples/a/debloat.txt", f"+{pkg}\n")])["core_packages_disabled"], [], pkg)
        self.assertEqual(fx_of([f("examples/a/debloat.txt", "+# com.android.systemui stays on\n")])
                         ["core_packages_disabled"], [])
        self.assertEqual(fx_of([f("examples/a/README.md", "+com.android.systemui\n")])["core_packages_disabled"], [])

    def test_a_list_naming_one_is_sent_back(self):
        fx = fx_of([f("examples/a/debloat.txt", "+com.a.ads\n+com.google.android.permissioncontroller\n")])
        for verdict in ("merge", "hold", "rework"):
            v, why, fix = v4.final(res(verdict), fx)
            self.assertEqual(v, "rework")
            self.assertIn("com.google.android.permissioncontroller", fix)
            self.assertIn("#884", fix)


class RefusalTest(unittest.TestCase):
    """#753 and #830: a refusal used to leave the PR with no comment at all."""

    def test_refusal_posts_a_minimal_comment_and_the_label(self):
        s = snap(["examples/tcl-98q9k/debloat.txt"])
        fake = FakeGH(s)
        orig = (live.GitHub, live.snapshot, live.repo_context, live.v4.judge)
        live.GitHub, live.snapshot = fake, (lambda gh, n: s)
        live.repo_context = lambda gh, b: {"list_folders": set(), "locales": []}

        def refuse(*a, **k):
            raise ToolCallFailed("the model declined to review this one")
        live.v4.judge = refuse
        try:
            with tempfile.TemporaryDirectory() as d:
                r = live.review("o/r", 7, rules_md="", precedents="", ledger_path=os.path.join(d, "l.jsonl"))
        finally:
            live.GitHub, live.snapshot, live.repo_context, live.v4.judge = orig
        self.assertEqual(r["verdict"], "hold")
        self.assertIn("Couldn't review this one automatically; it goes to the maintainer.", r["comment"])
        self.assertTrue(any(w[0] == "POST" and w[1].endswith("/comments") for w in fake.writes))
        self.assertTrue(any(w[0] == "POST" and w[1].endswith("/labels") and "needs-maintainer" in w[2]["labels"]
                            for w in fake.writes))


if __name__ == "__main__":
    unittest.main()
