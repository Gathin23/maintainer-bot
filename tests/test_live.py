import os
import tempfile
import unittest

from maintainer_bot import facts, live


def snap(paths, title="Add Acme TV list", head="abcdef1234567890", patch="+com.acme.ads\n"):
    return {"pr": 7, "title": title, "author": "someone", "body": "", "created_at": "2026-10-21T00:00:00Z",
            "head_sha": head, "base_ref": "main", "default_branch": "main", "draft": False, "state": "open",
            "labels": ["tv-list", "bot-suggests:close", "help wanted"],
            "files": [{"path": p, "status": "added", "additions": 3, "deletions": 0, "patch": patch, "binary": False}
                      for p in paths]}


class FakeGH:
    def __init__(self, s, sticky=None):
        self.s, self.sticky, self.writes = s, sticky, []

    def __call__(self, repo, dry_run=False, token=None):
        return self

    def get(self, path, **kw):
        return {}

    def paged(self, path, limit=300, **kw):
        if path.endswith("/comments"):
            return [{"id": 99, "body": self.sticky}] if self.sticky else []
        return []

    def write(self, method, path, body=None):
        self.writes.append((method, path, body))
        return {}

    def file_text(self, path, ref):
        return ""


class LiveTest(unittest.TestCase):
    def setUp(self):
        self._orig = (live.GitHub, live.snapshot)

    def tearDown(self):
        live.GitHub, live.snapshot = self._orig

    def _run(self, s, sticky=None, **kw):
        fake = FakeGH(s, sticky)
        live.GitHub = fake
        live.snapshot = lambda gh, n: s
        return live.review("o/r", 7, **kw), fake

    def test_skips_unchanged_commit(self):
        r, fake = self._run(snap(["examples/acme/debloat.txt"]), sticky="<!-- maintainer-bot sha=abcdef123456 v=1 -->")
        self.assertIn("already reviewed", r["skipped"])
        self.assertEqual(fake.writes, [])

    def test_config_paths_only_get_a_maintainer_comment(self):
        r, fake = self._run(snap([".github/workflows/ci.yml", "README.md"]))
        self.assertEqual(r["verdict"], "hold")
        self.assertIn("needs **a maintainer**", r["comment"])
        methods = [w[0] for w in fake.writes]
        self.assertIn("POST", methods)
        # the bot removes only labels it owns (bot-suggests:close), never 'help wanted' or 'tv-list'
        self.assertTrue(any(w[0] == "DELETE" and "bot-suggests" in w[1] for w in fake.writes))
        self.assertFalse(any(w[0] == "DELETE" and ("help" in w[1] or "tv-list" in w[1]) for w in fake.writes))

    def test_daily_cap_stops_before_any_model_call(self):
        with tempfile.TemporaryDirectory() as d:
            from datetime import datetime, timezone
            day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            with open(os.path.join(d, f"ledger-{day}.jsonl"), "w") as f:
                f.write('{"model":"m","in":1,"out":1,"usd":6.0}\n')
            orig = live.repo_context
            live.repo_context = lambda gh, b: {"list_folders": set(), "locale_count": 0}
            try:
                r, fake = self._run(snap(["examples/acme/debloat.txt"]), ledger_path=os.path.join(d, "ledger.jsonl"),
                                    daily_cap=5.0, rules_md="", precedents="")
            finally:
                live.repo_context = orig
            self.assertIn("daily cap", r["skipped"])
            self.assertEqual(fake.writes, [])

    def test_render_hold_and_suggestion(self):
        s = snap(["examples/tcl/debloat.txt"], patch="+com.tcl.autopair\n")
        fx = facts.compute(s, existing_list_folders=set())
        body = live.render(s, verdict="hold", model_verdict="merge", priority="p2",
                           reason="Thanks for the list! @someone it looks clean.", fix="", fx=fx, ptype="tv-list",
                           why_held="a list disables remote-pairing or input packages: com.tcl.autopair", cost=0.01)
        self.assertTrue(body.startswith("<!-- maintainer-bot sha=abcdef123456"))
        self.assertIn("a maintainer decision", body)
        self.assertIn("remote-pairing", body)
        self.assertIn("@​someone", body)  # no pings
        self.assertIn("a maintainer makes the final call", body)
        self.assertIn("runs on [0G Private Computer](https://pc.0g.ai)", body)
        for word in ("Opus", "GLM", "TEE", "sealed", "private inference"):
            self.assertNotIn(word, body)

    def test_labels_are_allow_listed(self):
        s = snap(["examples/acme-google-tv/debloat.txt"], title="Add Acme Google TV list")
        fx = facts.compute(s, existing_list_folders=set())
        self.assertEqual(live.labels_for("tv-list", "merge-with-fix", "p2", fx, s),
                         ["bot-suggests:merge-with-fix", "google-tv", "p2", "tv-list"])
        self.assertEqual(live.labels_for("workflow", "hold", "", fx, s), ["google-tv", "needs-maintainer"])

    def test_clean_strips_html_and_length(self):
        t = live._clean("<script>x</script>" + "word " * 300, limit=50)
        self.assertNotIn("<", t)
        self.assertLessEqual(len(t), 50)


if __name__ == "__main__":
    unittest.main()
