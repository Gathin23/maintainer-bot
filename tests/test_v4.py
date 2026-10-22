import unittest

from maintainer_bot import checklists, facts, live, templates, v4

CFG = "launcher/app/src/main/res/values/config.xml"
STR = "launcher/app/src/main/res/values/strings.xml"
MAN = "launcher/app/src/main/AndroidManifest.xml"
MAIN = "launcher/app/src/main/java/com/gathin/tvhome/MainActivity.java"


def f(path, patch="", add=None, dele=0, status="modified"):
    adds = add if add is not None else sum(1 for l in patch.splitlines() if l.startswith("+"))
    return {"path": path, "additions": adds, "deletions": dele, "status": status, "patch": patch}


def fx_of(files, **kw):
    return facts.compute_v4({"files": files}, **kw)


def res(verdict, confidence=0.9, **kw):
    return {"verdict": verdict, "confidence": confidence, **kw}


class CoreFactsTest(unittest.TestCase):
    def test_new_key_default_and_changed_default(self):
        fx = fx_of([f(CFG, '+    <bool name="dock_glass">false</bool>\n'
                          '-    <bool name="fill_dock">false</bool>\n+    <bool name="fill_dock">true</bool>\n')])
        self.assertEqual(fx["new_config_keys"], [{"name": "dock_glass", "type": "bool", "default": "false"}])
        self.assertEqual(fx["changed_config_defaults"], [{"name": "fill_dock", "old": "false", "new": "true"}])
        self.assertEqual(v4.final(res("merge"), fx)[0], "rework")

    def test_strings_missing_per_locale(self):
        files = [f(STR, '+    <string name="pill_bt">Bluetooth</string>\n+    <string name="k" translatable="false">x</string>\n'),
                 f("launcher/app/src/main/res/values-de/strings.xml", '+    <string name="pill_bt">Bluetooth</string>\n')]
        fx = fx_of(files, main_locales=["de", "fr", "es", "it"])
        self.assertEqual(fx["new_strings"], ["pill_bt"])
        self.assertEqual(fx["locales_missing_new_strings"], ["es", "fr", "it"])
        self.assertEqual(v4.final(res("merge"), fx)[0], "rework")  # 3 missing > 2
        fx2 = fx_of(files, main_locales=["de", "fr"])
        v, why, fix = v4.final(res("merge"), fx2)
        self.assertEqual(v, "merge-with-fix")
        self.assertIn("values-fr", fix)

    def test_permission_and_network_hold_a_merge_but_not_a_showcase(self):
        fx = fx_of([f(MAN, '+<uses-permission android:name="android.permission.INTERNET"/>\n'),
                    f("launcher/app/src/main/java/com/gathin/tvhome/Weather.java",
                      '+        HttpURLConnection c = (HttpURLConnection) new URL(u).openConnection();\n')])
        self.assertEqual(fx["new_permissions"], ["android.permission.INTERNET"])
        self.assertTrue(fx["network_use"])
        self.assertEqual(v4.final(res("merge"), fx)[0], "hold")
        self.assertEqual(v4.final(res("showcase", 0.8), fx)[0], "showcase")

    def test_home_path_needs_high_confidence(self):
        fx = fx_of([f(MAIN, "+    @Override protected void onNewIntent(Intent i) {\n")])
        self.assertTrue(fx["home_path_touched"])
        self.assertEqual(v4.final(res("merge", 0.8), fx)[0], "hold")
        self.assertEqual(v4.final(res("merge", 0.9, critic={"blocker": False}), fx)[0], "merge")

    def test_small_switch_merges_alone(self):
        fx = fx_of([f(CFG, '+    <bool name="show_inputs_pill">true</bool>\n'),
                    f(MAIN, "+        if (!config.showInputsPill) inputs.setVisibility(View.GONE);\n")],
                   conflicts_with_main=False)
        self.assertEqual(fx["core_lines_changed"], 2)
        self.assertEqual(v4.final(res("merge", 0.8), fx), ("merge", "", ""))
        self.assertEqual(v4.final(res("merge", 0.7), fx)[0], "hold")  # core merges need 0.75

    def test_big_change_and_conflicts(self):
        big = fx_of([f(MAIN, "+x\n" * 300)])
        self.assertEqual(v4.final(res("merge"), big)[0], "hold")
        clash = fx_of([f(MAIN, "+x\n")], conflicts_with_main=True)
        v, why, fix = v4.final(res("merge"), clash)
        self.assertEqual(v, "rework")
        self.assertIn("rebase", fix)

    def test_a_rework_on_a_bigger_launcher_change_goes_to_the_maintainer(self):
        big = fx_of([f(MAIN, "+x\n" * 150)])
        self.assertEqual(v4.final(res("rework", 0.8), big)[0], "hold")
        self.assertEqual(v4.final(res("showcase", 0.8), big)[0], "showcase")
        self.assertEqual(v4.final(res("rework", 0.8), big, {"big_core_rework_lines": None})[0], "rework")
        small = fx_of([f(MAIN, "+x\n" * 20)])
        self.assertEqual(v4.final(res("rework", 0.8), small)[0], "rework")

    def test_tests_and_translations_do_not_count_as_core_lines(self):
        fx = fx_of([f("launcher/app/src/test/java/com/gathin/tvhome/XTest.java", "+t\n" * 400),
                    f("launcher/app/src/main/res/values-ru/strings.xml", "+s\n" * 300)])
        self.assertEqual(fx["core_lines_changed"], 0)


class ListFactsTest(unittest.TestCase):
    def test_uninstall_steps_rework(self):
        fx = fx_of([f("examples/moto/debloat.txt", "+#     pm uninstall --user 0 com.google.android.katniss\n"),
                    f("examples/moto/restore.sh", '+  tv "pm uninstall com.gathin.tvhome"\n')],
                   existing_list_folders=set())
        self.assertEqual(fx["uninstall_steps"], ["com.google.android.katniss"])  # the launcher itself is fine
        self.assertEqual(v4.final(res("merge"), fx)[0], "rework")

    def test_uninstall_mention_is_not_a_step(self):
        fx = fx_of([f("examples/a/debloat.txt", "+# T-Cast comes back even after `pm uninstall`\n")],
                   existing_list_folders=set())
        self.assertNotIn("uninstall_steps", fx)

    def test_dns_setup_and_scripts_are_fixed_on_merge(self):
        fx = fx_of([f("examples/a/README.md", "+`settings put global private_dns_specifier dns.adguard-dns.com`\n"),
                    f("examples/a/debloat.txt", "+# Private DNS with dns.adguard-dns.com works here\n+com.a.ads\n"),
                    f("examples/a/install.sh", "+echo\n")], existing_list_folders=set())
        self.assertEqual(fx["private_dns_setup"], ["examples/a/README.md"])  # the "works" note is fine
        self.assertEqual(fx["list_folder_scripts"], ["examples/a/install.sh"])
        v, why, fix = v4.final(res("merge"), fx)
        self.assertEqual(v, "merge-with-fix")
        self.assertIn("Private DNS", fix)
        self.assertIn("install.sh", fix)
        self.assertEqual(v4.final(res("merge"), fx, {"dns_rule": "rework"})[0], "rework")

    def test_untested_entries_commented_out(self):
        fx = fx_of([f("examples/p/debloat.txt", "+org.droidtv.eum      # not tested yet with HDMI\n+org.ok.ads\n")],
                   existing_list_folders=set())
        self.assertEqual(fx["untested_entries"], ["org.droidtv.eum"])
        self.assertIn("untested", v4.final(res("merge"), fx)[2])

    def test_same_product_on_main(self):
        readme = ("| Folder | TV | OS | Notes |\n|---|---|---|---|\n"
                  "| `tcl-q7c-google-tv/` | TCL Q7C (G08, G08_4K_GB, MediaTek) | Google TV 14 | ... |\n")
        fx = fx_of([f("examples/tcl-55c745/debloat.txt", "+# TCL 55C745, product G08_4K_GB, UTT2.250416.001 AU02\n+com.tcl.ads\n")],
                   existing_list_folders={"tcl-q7c-google-tv"}, examples_readme=readme)
        self.assertEqual(fx["same_product_on_main"], {"G08_4K_GB": ["tcl-q7c-google-tv"]})
        self.assertEqual(v4.final(res("merge", 0.7), fx)[0], "hold")  # a judgement call below 0.75
        self.assertEqual(v4.final(res("rework", 0.7), fx)[0], "hold")  # "fold it in" is a judgement call too
        self.assertEqual(v4.final(res("rework", 0.8), fx)[0], "rework")
        self.assertEqual(v4.final(res("merge", 0.8), fx)[0], "merge")

    def test_edit_existing_list_only_when_very_confident(self):
        fx = fx_of([f("examples/mi/debloat.txt", "+com.mi.ads\n")], existing_list_folders={"mi"})
        self.assertEqual(fx["edits_existing_list"], ["mi"])
        self.assertEqual(v4.final(res("merge", 0.8), fx)[0], "hold")
        self.assertEqual(v4.final(res("merge", 0.9), fx)[0], "merge")

    def test_stray_files_dropped_on_merge(self):
        fx = fx_of([f("debloat_philips.txt", "+x\n", status="added"),
                    f("docs/shot.png", "", add=0, status="added"),
                    f("docs/linked.png", "", add=0, status="added"),
                    f("docs/a.md", "+![x](linked.png)\n")])
        self.assertEqual(fx["stray_root_files"], ["debloat_philips.txt"])
        self.assertEqual(fx["unlinked_images"], ["docs/shot.png"])
        self.assertIn("nothing links to", v4.final(res("merge"), fx)[2])


class HardHoldsTest(unittest.TestCase):
    def test_always_maintainer_whatever_the_verdict(self):
        for path in ("PROMPT.md", ".github/workflows/ci.yml", "tools/disable.sh", ".github/maintainer/MAINTAINER.md"):
            fx = fx_of([f(path, "+x\n")])
            for v in ("merge", "close", "showcase", "rework"):
                self.assertEqual(v4.final(res(v), fx)[0], "hold", (path, v))

    def test_protected_pairing_and_hide_still_hold(self):
        prot = fx_of([f("examples/a/debloat.txt", "+com.android.vending\n")])
        self.assertEqual(v4.final(res("close"), prot)[0], "hold")
        pair = fx_of([f("examples/a/debloat.txt", "+com.tcl.autopair\n")])
        self.assertEqual(v4.final(res("merge"), pair)[0], "hold")
        self.assertEqual(v4.final(res("rework"), pair)[0], "rework")
        hide = fx_of([f("examples/a/debloat.txt", "+pm hide com.a.ads\n")])
        self.assertEqual(v4.final(res("merge-with-fix"), hide)[0], "hold")

    def test_low_confidence_critic_and_second_opinion(self):
        fx = fx_of([f("examples/new/debloat.txt", "+com.a.ads\n")], existing_list_folders=set())
        self.assertEqual(v4.final(res("merge", 0.6), fx)[0], "hold")
        self.assertEqual(v4.final(res("merge", 0.9, critic={"blocker": True, "rule": "x"}), fx)[0], "hold")
        self.assertEqual(v4.final(res("merge", 0.9, second={"verdict": "close"}), fx)[0], "hold")
        # showcase vs a plain close point the same way: no hold
        self.assertEqual(v4.final(res("showcase", 0.9, second={"verdict": "close"}), fx)[0], "showcase")
        self.assertEqual(v4.final(res("addon", 0.9, second={"verdict": "merge"}), fx)[0], "hold")

    def test_addon_never_touches_launcher(self):
        fx = fx_of([f("addons/clock/README.md", "+# Clock\n+## Permissions\n+none\n", status="added"),
                    f(MAIN, "+x\n")])
        self.assertTrue(fx["addon_touches_launcher"])
        self.assertEqual(v4.final(res("merge"), fx)[0], "rework")

    def test_addon_needs_permissions_heading(self):
        fx = fx_of([f("addons/clock/README.md", "+# Clock\n", status="added"), f("addons/clock/build.gradle", "+x\n")],
                   addon_folders_on_main=set())
        self.assertEqual(fx["addon_readme_missing_permissions"], ["clock"])
        self.assertEqual(checklists.pr_type(["addons/clock/README.md", "addons/README.md"]), "addon")

    def test_theme_needs_a_screenshot(self):
        fx = fx_of([f("themes/ruska/config.json", "+{}\n", status="added")], theme_folders_on_main=set())
        self.assertEqual(fx["theme_missing_screenshot"], ["ruska"])
        self.assertIn("screenshot", v4.final(res("merge"), fx)[2])


class TemplatesTest(unittest.TestCase):
    def test_kind_short_and_linked(self):
        link = templates.where_link("Gathin23/cleanyourtv")
        self.assertTrue(link.endswith("CONTRIBUTING.md#where-does-my-idea-go"))
        for kind in ("showcase", "addon", "theme"):
            t = templates.render(kind, specific="The careful OTA audit @someone <b>x</b>", name="Screen Time!", link=link)
            self.assertTrue(t.startswith("Thank you for this, the careful OTA audit"))
            self.assertIn(link, t)
            self.assertNotIn("<b>", t)
            self.assertNotIn("@someone", t)
            self.assertLess(len(t), 650)
            for word in ("Claude", "AI", "model", "bot"):
                self.assertNotIn(word, t)
        self.assertIn("addons/screen-time/", templates.render("addon", specific="", name="Screen Time!", link=link))
        self.assertIn("themes/your-theme/", templates.render("theme", specific="", name="", link=link))


class StickyDataTest(unittest.TestCase):
    def test_round_trip_and_no_comment_breakout(self):
        d = {"m": "merge", "c": 0.8, "reason": "a --> b <!-- c", "diff": "abc"}
        line = live.write_data(d)
        self.assertEqual(line.count("-->"), 1)
        self.assertEqual(live.read_data("x\n" + line + "\n"), d)

    def test_diff_hash_ignores_context_lines(self):
        a = {"files": [{"path": "x", "patch": "@@ -1 +1 @@\n context\n+new\n"}]}
        b = {"files": [{"path": "x", "patch": "@@ -7 +7 @@\n other context\n+new\n"}]}
        c = {"files": [{"path": "x", "patch": "@@ -1 +1 @@\n+newer\n"}]}
        self.assertEqual(live.diff_hash(a), live.diff_hash(b))
        self.assertNotEqual(live.diff_hash(a), live.diff_hash(c))


if __name__ == "__main__":
    unittest.main()
