"""Long-context research blocks (no network) and the cache-aware cost record."""
import os
import tempfile
import unittest
from unittest import mock

from maintainer_bot import longctx, router
from maintainer_bot.ledger import Ledger, Price


def snap(body="", files=None):
    return {"pr": 900, "title": "examples: fix for #850", "body": body,
            "files": files or [{"path": "examples/x/debloat.txt", "status": "added", "additions": 2, "deletions": 0,
                                "patch": "+pm disable-user --user 0 com.a\n+pm disable-user --user 0 com.b"}]}


class FullDiff(unittest.TestCase):
    def test_every_file_and_line_until_the_cap(self):
        s = snap(files=[{"path": f"f{i}.txt", "status": "added", "additions": 1, "deletions": 0,
                         "patch": "+" + "x" * 1000} for i in range(10)])
        d = longctx.full_diff(s)
        self.assertEqual(d.count("### f"), 10)
        self.assertIn("more chars cut", longctx.full_diff(s, cap=3000))

    def test_binary_files_are_named_not_dumped(self):
        s = snap(files=[{"path": "a.png", "binary": True, "status": "added"}])
        self.assertIn("(binary)", longctx.full_diff(s))


class Issues(unittest.TestCase):
    def setUp(self):
        longctx.ISSUE_CACHE.clear()

    def test_only_what_existed_before_the_decision(self):
        longctx.ISSUE_CACHE["Gathin23/cleanyourtv#850"] = {
            "title": "Remote stops working", "body": "after the list", "is_pr": False,
            "created_at": "2026-10-20T00:00:00Z",
            "comments": [{"at": "2026-10-20T01:00:00Z", "by": "a", "body": "same here"},
                         {"at": "2026-10-23T01:00:00Z", "by": "Gathin23", "body": "fixed by #900, merged"}]}
        out = longctx.block_issues({"pr": 900, "decided_at": "2026-10-22T00:00:00Z"}, snap())
        self.assertIn("same here", out)
        self.assertNotIn("merged", out)

    def test_an_issue_opened_after_the_decision_is_left_out(self):
        longctx.ISSUE_CACHE["Gathin23/cleanyourtv#850"] = {"title": "later", "body": "", "is_pr": False,
                                                           "created_at": "2026-10-25T00:00:00Z", "comments": []}
        self.assertEqual(longctx.block_issues({"pr": 900, "decided_at": "2026-10-22T00:00:00Z"}, snap()), "")

    def test_the_pr_itself_and_far_later_numbers_are_ignored(self):
        s = snap(body="see #900 and #5000")
        s["title"] = "x"
        with mock.patch.object(longctx, "_issue") as fetch:
            longctx.block_issues({"pr": 900, "decided_at": "2026-10-22T00:00:00Z"}, s)
        fetch.assert_not_called()


class CacheCost(unittest.TestCase):
    def test_cache_tokens_are_priced(self):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(router, "price", return_value=Price(4e-6, 2e-5)), \
                mock.patch.object(router, "model_info", return_value={"pricing_usd": {"cache_write": "0.000005"}}):
            router._INFO.clear()
            L = Ledger(os.path.join(d, "l.jsonl"), 10)
            usd = router.record_usage(L, "m", {"input_tokens": 500, "output_tokens": 1000,
                                               "cache_creation_input_tokens": 1000, "cache_read_input_tokens": 70000})
            want = 500 * 4e-6 + 1000 * 2e-5 + 1000 * 5e-6 + 70000 * 4e-7
            self.assertAlmostEqual(usd, want, places=9)
            self.assertAlmostEqual(L.spent, want, places=9)

    def test_without_cache_tokens_nothing_changes(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(router, "price", return_value=Price(1e-6, 2e-6)):
            L = Ledger(os.path.join(d, "l.jsonl"), 10)
            self.assertAlmostEqual(router.record_usage(L, "m", {"input_tokens": 100, "output_tokens": 10}),
                                   100e-6 + 20e-6)


if __name__ == "__main__":
    unittest.main()
