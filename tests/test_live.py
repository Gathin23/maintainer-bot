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
        sticky = "<!-- maintainer-bot sha=abcdef123456 v=2 -->\n" + live.write_data({"m": "merge", "diff": "x"})
        r, fake = self._run(snap(["examples/acme/debloat.txt"]), sticky=sticky)
        self.assertIn("already reviewed", r["skipped"])
        self.assertEqual(fake.writes, [])

    def test_a_v1_review_is_done_again_once(self):
        orig = live.repo_context
        live.repo_context = lambda gh, b: {"list_folders": set(), "locales": []}
        try:
            with tempfile.TemporaryDirectory() as d:
                from datetime import datetime, timezone
                day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                with open(os.path.join(d, f"ledger-{day}.jsonl"), "w") as f:
                    f.write('{"model":"m","in":1,"out":1,"usd":6.0}\n')
                r, fake = self._run(snap(["examples/acme/debloat.txt"]),
                                    sticky="<!-- maintainer-bot sha=abcdef123456 v=1 -->",
                                    ledger_path=os.path.join(d, "ledger.jsonl"), daily_cap=5.0, rules_md="",
                                    precedents="")
        finally:
            live.repo_context = orig
        self.assertIn("daily cap", r["skipped"])  # it got as far as the model (stopped by the cap here)

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

    def _ctx(self):
        orig = live.repo_context
        live.repo_context = lambda gh, b: {"list_folders": set(), "locale_count": 0, "locales": [],
                                           "themes": set(), "addons": set(), "examples_readme": ""}
        self.addCleanup(lambda: setattr(live, "repo_context", orig))
        judge = live.v4.judge

        def no_model(*a, **k):
            raise AssertionError("a re-review with the same changes must not call a model")
        live.v4.judge = no_model
        self.addCleanup(lambda: setattr(live.v4, "judge", judge))

    def test_rereview_same_changes_without_a_model(self):
        self._ctx()
        s = snap(["examples/acme/debloat.txt"], head="1234567890abcdef")
        data = live.write_data({"m": "merge", "c": 0.9, "crit": 0, "sec": "merge", "diff": live.diff_hash(s),
                                "p": "p2", "reason": "Thanks! Clean list.", "fix": "", "specific": "", "final": "merge"})
        sticky = "<!-- maintainer-bot sha=abcdef123456 v=2 -->\nold\n" + data
        r, fake = self._run(s, sticky=sticky)
        self.assertTrue(r["re_review"])
        self.assertEqual(r["cost_usd"], 0)
        self.assertEqual(r["verdict"], "merge")
        self.assertIn("sha=1234567890ab", r["comment"])
        self.assertIn("same as at the last review", r["comment"])
        self.assertTrue(any(w[0] == "PATCH" for w in fake.writes))  # the sticky is edited in place

    def test_rereview_policy_runs_again_on_fresh_facts(self):
        self._ctx()
        old = snap(["examples/acme/debloat.txt"])
        s = snap(["examples/acme/debloat.txt"], head="1234567890abcdef", patch="+com.acme.ads\n")
        s["files"][0]["path"] = "examples/acme/debloat.txt"
        data = live.write_data({"m": "merge", "c": 0.9, "crit": 0, "sec": "merge", "diff": live.diff_hash(old),
                                "p": "p2", "reason": "Thanks!", "fix": "", "specific": "", "final": "merge"})
        # the same changes, but main now has the folder: the policy holds the merge as an edit of a list on main
        orig = live.repo_context
        live.repo_context = lambda gh, b: {"list_folders": {"acme"}, "locales": [], "themes": set(), "addons": set(),
                                           "examples_readme": ""}
        try:
            r, fake = self._run(s, sticky="<!-- maintainer-bot sha=abcdef123456 v=2 -->\n" + data)
        finally:
            live.repo_context = orig
        self.assertTrue(r["re_review"])
        self.assertEqual(r["verdict"], "merge")  # 0.9 >= 0.85: still decided
        self.assertIn("edits a list already on main", r["comment"])

    def test_refresh_after_ci_reads_failures_without_a_model(self):
        self._ctx()
        s = snap(["launcher/app/src/main/res/values/config.xml"], head="abcdef1234567890",
                 patch='+    <bool name="dock_glass">false</bool>\n')
        data = live.write_data({"m": "merge", "c": 0.9, "crit": 0, "sec": "merge", "diff": live.diff_hash(s),
                                "p": "p2", "reason": "Thanks!", "fix": "", "specific": "", "final": "merge"})
        orig = live.ci_facts
        live.ci_facts = lambda gh, sha, **kw: {"ci_failed": ["Launcher build and unit tests"]}
        try:
            r, fake = self._run(s, sticky="<!-- maintainer-bot sha=abcdef123456 v=2 -->\n" + data, refresh=True)
        finally:
            live.ci_facts = orig
        self.assertEqual(r["verdict"], "rework")
        self.assertIn("CI fails", r["comment"])
        self.assertIn("after CI finished", r["comment"])
        r2, _ = self._run(s, sticky="<!-- maintainer-bot sha=abcdef123456 v=1 -->", refresh=True)
        self.assertIn("no stored review", r2["skipped"])

    def test_render_showcase_uses_the_template(self):
        s = snap(["launcher/app/src/main/java/com/gathin/tvhome/Weather.java"], title="launcher: weather card")
        fx = facts.compute_v4(s)
        body = live.render(s, verdict="showcase", model_verdict="showcase", priority="p3", reason="", fix="",
                           why_held="", fx=fx, ptype="launcher", cost=0.0,
                           elsewhere=live.templates.render("showcase", specific="the weather card",
                                                           link=live.templates.where_link("o/r")),
                           data={"m": "showcase"})
        self.assertIn("suggests **your own fork, with a row in SHOWCASE.md**", body)
        self.assertIn("where-does-my-idea-go", body)
        self.assertIn("<!-- mb-review ", body)
        self.assertEqual(live.labels_for("launcher", "showcase", "p3", fx, s), ["bot-suggests:showcase", "launcher", "p3"])

    def test_clean_strips_html_and_length(self):
        t = live._clean("<script>x</script>" + "word " * 300, limit=50)
        self.assertNotIn("<", t)
        self.assertLessEqual(len(t), 50)


if __name__ == "__main__":
    unittest.main()
