import json
import os
import tempfile
import unittest

from maintainer_bot import apply, commands, facts, ledger, memory, queue


def f(path, add=1, dele=0, status="modified", patch=""):
    return {"path": path, "additions": add, "deletions": dele, "status": status, "patch": patch}


class FactsTest(unittest.TestCase):
    def test_labels_and_size(self):
        fx = facts.compute({"files": [f("examples/acme-tv/debloat.txt", 30, 0, "added"), f("README.md", 1)]},
                           existing_list_folders=set())
        self.assertEqual(fx["labels"], ["docs", "tv-list"])
        self.assertEqual(fx["size"], "size/S")
        self.assertEqual(fx["new_list_folders"], ["acme-tv"])

    def test_duplicate_folder(self):
        fx = facts.compute({"files": [f("examples/acme-tv/debloat.txt", 5, 0, "added")]},
                           existing_list_folders={"acme-tv"})
        self.assertEqual(fx["duplicate_of_merged_folder"], ["acme-tv"])
        self.assertIn("already exists", facts.merge_blockers(fx)[0])
        self.assertEqual(facts.apply_overrides("merge", fx)[0], "rework")
        self.assertEqual(facts.apply_overrides("close", fx), ("close", ""))

    def test_protected_package_forces_rework(self):
        patch = "+++ b/x\n+com.android.vending\n+# com.google.android.gms is kept\n+com.acme.ads\n"
        fx = facts.compute({"files": [f("examples/acme-tv/debloat.txt", patch=patch)]})
        self.assertEqual(fx["protected_packages_disabled"], ["com.android.vending"])
        self.assertEqual(facts.hard_overrides(fx)[0], "rework")
        self.assertEqual(facts.apply_overrides("hold", fx), ("hold", ""))  # never upgrades

    def test_setupwraith_and_factory_are_allowed(self):
        patch = "+com.google.android.tungsten.setupwraith\n+com.acme.factorymenu\n"
        fx = facts.compute({"files": [f("examples/acme-tv/debloat.txt", patch=patch)]})
        self.assertEqual(fx["protected_packages_disabled"], [])

    def test_sensitive_binary_internet(self):
        self.assertEqual(facts.hard_overrides(facts.compute({"files": [f(".github/workflows/ci.yml")]}))[0], "hold")
        self.assertEqual(facts.hard_overrides(facts.compute({"files": [f("dist/app-release.apk")]}))[0], "hold")
        manifest = f("launcher/app/src/main/AndroidManifest.xml",
                     patch='+<uses-permission android:name="android.permission.INTERNET"/>')
        self.assertEqual(facts.hard_overrides(facts.compute({"files": [manifest]}))[0], "hold")

    def test_strings_in_too_few_locales(self):
        files = [f("launcher/app/src/main/res/values/strings.xml", patch='+<string name="x">X</string>'),
                 f("launcher/app/src/main/res/values-de/strings.xml")]
        fx = facts.compute({"files": files}, locale_count=20)
        self.assertTrue(facts.strings_gap(fx))
        fx_all = facts.compute({"files": files}, locale_count=1)
        self.assertFalse(facts.strings_gap(fx_all))


class LedgerTest(unittest.TestCase):
    def test_cap_and_resume(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "l.jsonl")
            L = ledger.Ledger(p, cap_usd=0.01)
            price = ledger.Price(prompt=1e-6, completion=2e-6)
            L.record(model="m", input_tokens=4000, output_tokens=1000, price=price)
            self.assertAlmostEqual(L.spent, 0.006)
            L.check()
            L.record(model="m", input_tokens=4000, output_tokens=1000, price=price)
            with self.assertRaises(ledger.BudgetExceeded):
                L.check()
            self.assertAlmostEqual(ledger.Ledger(p, 1).spent, 0.012)  # survives a restart
            self.assertEqual(L.summary()["m"]["calls"], 2)


class CommandsTest(unittest.TestCase):
    proposed = {1: "merge", 2: "merge-with-fix", 3: "rework", 4: "close", 5: "hold"}

    def test_approve_all_skips_hold(self):
        a = commands.parse("/approve")
        self.assertEqual(a.selected(self.proposed), {1: "merge", 2: "merge-with-fix", 3: "rework", 4: "close"})

    def test_except_and_overrides(self):
        a = commands.parse("/approve except #2 #4\nmerge 5, hold 1")
        self.assertEqual(a.selected(self.proposed), {3: "rework", 5: "merge"})

    def test_only_listed(self):
        self.assertEqual(commands.parse("/approve #1 #3").selected(self.proposed), {1: "merge", 3: "rework"})

    def test_slash_overrides(self):
        a = commands.parse("/close #1\n/hold #3")
        self.assertEqual(a.selected(self.proposed), {1: "close"})

    def test_outsiders_and_chatter_ignored(self):
        self.assertIsNone(commands.parse("/approve", "CONTRIBUTOR"))
        self.assertIsNone(commands.parse("looks good to me"))


class MemoryQueueApplyTest(unittest.TestCase):
    def test_no_leakage(self):
        hist = [{"pr": 1, "truth": "merge", "title": "acme tv list", "decided_at": "2026-10-18", "top_dirs": ["examples"]},
                {"pr": 2, "truth": "close", "title": "acme tv list", "decided_at": "2026-10-20", "top_dirs": ["examples"]},
                {"pr": 3, "truth": "rework", "title": "acme tv list", "decided_at": "2026-10-19", "top_dirs": ["examples"]}]
        target = {"pr": 3, "title": "acme tv list", "decided_at": "2026-10-19", "top_dirs": ["examples"]}
        self.assertEqual([h["pr"] for h in memory.similar(target, hist)], [1])

    def test_queue_and_plan(self):
        ds = [{"pr": 7, "verdict": "merge", "title": "A", "reasons": ["ok"], "priority": "p2", "type": "docs"},
              {"pr": 8, "verdict": "hold", "title": "B", "reasons": ["needs a TV"], "priority": "p1", "type": "launcher"}]
        md = queue.render(ds, day="2026-10-21")
        self.assertIn("✅ Merge (1)", md)
        self.assertIn("🤔 Needs you (1)", md)
        self.assertIn("runs on 0G Private Computer", md)
        for claim in ("sealed", "TEE", "private inference", "glm", "opus"):
            self.assertNotIn(claim, md)
        acts = apply.plan({7: "merge"}, {d["pr"]: d for d in ds})
        self.assertEqual([a.kind for a in acts], ["merge", "comment"])


class V3Test(unittest.TestCase):
    def test_pr_type(self):
        from maintainer_bot import checklists
        self.assertEqual(checklists.pr_type(["examples/acme-x/debloat.txt", "README.md", "examples/README.md"]), "tv-list")
        self.assertEqual(checklists.pr_type(["launcher/app/src/main/java/A.java", "README.md"]), "launcher")
        self.assertEqual(checklists.pr_type([".github/workflows/ci.yml"]), "workflow")
        self.assertEqual(checklists.pr_type(["SHOWCASE.md"]), "showcase")
        self.assertEqual(checklists.pr_type(["tools/tv.py"]), "tools")
        self.assertEqual(checklists.pr_type(["docs/REMOTE.md"]), "docs")

    def test_open_overlaps_ignores_shared_tables(self):
        from maintainer_bot import batch
        rows = [{"pr": 1, "created_at": "a1", "decided_at": "a5"}, {"pr": 2, "created_at": "a2", "decided_at": "a9"},
                {"pr": 3, "created_at": "a2", "decided_at": "a9"}]
        files = {1: ["README.md", "examples/x/debloat.txt"], 2: ["README.md"], 3: ["examples/x/debloat.txt"]}
        ov = batch.open_overlaps(rows[0], rows, files, {2: "B", 3: "C"})
        self.assertEqual([o["pr"] for o in ov], [3])

    def test_retrieval_no_leakage(self):
        from maintainer_bot import retrieval
        rows = [{"pr": 1, "truth": "merge", "title": "acme tv list", "decided_at": "2026-10-18"},
                {"pr": 2, "truth": "close", "title": "acme tv list", "decided_at": "2026-10-20"},
                {"pr": 3, "truth": "rework", "title": "acme tv list", "decided_at": "2026-10-19"}]
        idx = retrieval.Index(rows, {1: [], 2: [], 3: []}, {})
        self.assertEqual([r["pr"] for r in idx.similar(rows[2])], [1])

    def test_policy_gates(self):
        from maintainer_bot import v3
        base = {"pr": 1, "type": "tv-list", "verdict": "merge", "confidence": 0.9, "reasons": []}
        kw = dict(threshold=0.8, use_critic=True, use_second=True)
        self.assertEqual(v3.final(base, {}, **kw)[0], "merge")
        self.assertEqual(v3.final({**base, "type": "launcher"}, {}, **kw)[0], "hold")
        self.assertEqual(v3.final({**base, "confidence": 0.5}, {}, **kw)[0], "hold")
        self.assertEqual(v3.final({**base, "critic": {"blocker": True, "rule": "dup"}}, {}, **kw)[0], "hold")
        self.assertEqual(v3.final({**base, "second": {"verdict": "close"}}, {}, **kw)[0], "hold")
        self.assertEqual(v3.final({**base, "second": {"verdict": "merge-with-fix"}}, {}, **kw)[0], "merge")
        self.assertEqual(v3.final(base, {"binary_files": ["a.apk"]}, **kw)[0], "hold")


if __name__ == "__main__":
    unittest.main()
