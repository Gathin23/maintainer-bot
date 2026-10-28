"""The 0GM rollout: cache-aware ledger, the OpenAI endpoint for 0GM, the second-opinion switch, the DPX context
flag, and the duplicate/collision pass (no network: the router and GitHub are faked)."""
import json
import os
import tempfile
import unittest
from unittest import mock

from maintainer_bot import context, dedupe, facts, live, retrieval, router, v4
from maintainer_bot.ledger import Ledger, Price


class Resp:
    def __init__(self, status, body):
        self.status_code, self._body = status, body
        self.text = json.dumps(body)

    def json(self):
        return self._body


def oa_answer(args, usage=None, finish="tool_calls"):
    return Resp(200, {"choices": [{"finish_reason": finish, "message": {"tool_calls": [
        {"function": {"name": "t", "arguments": args}}]}}],
        "usage": usage or {"prompt_tokens": 1000, "completion_tokens": 200,
                           "prompt_tokens_details": {"cached_tokens": 800}}})


TOOL = {"name": "t", "description": "d", "input_schema": {"type": "object", "properties": {}}}


class Ledgers(unittest.TestCase):
    def test_openai_usage_counts_cached_and_reasoning_tokens(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(router, "price", return_value=Price(1e-7, 5e-7)):
            L = Ledger(os.path.join(d, "l.jsonl"), 10)
            usd = router.record_openai_usage(L, "0gm-1.0-35b-a3b", {
                "prompt_tokens": 10_000, "completion_tokens": 900, "reasoning_tokens": 700,
                "prompt_tokens_details": {"cached_tokens": 9_000}})
            self.assertAlmostEqual(usd, 10_000 * 1e-7 + 900 * 5e-7)   # cached at the full prompt rate: no undercount

    def test_the_daily_cap_sees_cache_tokens(self):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(router, "price", return_value=Price(4e-6, 2e-5)), \
                mock.patch.object(router, "model_info", return_value={"pricing_usd": {"cache_write": "0.000005"}}):
            router._INFO.clear()
            path = os.path.join(d, "l.jsonl")
            L = Ledger(path, 0.30)
            # a long Opus prompt that comes back almost all cached: 300 + 1,000 written + 70,000 read
            router.record_usage(L, "claude-opus-5.5", {"input_tokens": 300, "output_tokens": 2000,
                                                       "cache_creation_input_tokens": 1000,
                                                       "cache_read_input_tokens": 70_000})
            # input/output only would be $0.0412: under the cap; with the cache it is $0.0742
            self.assertGreater(Ledger(path, 0.30).spent, 0.07)
            L2 = Ledger(path, 0.07)
            with self.assertRaises(Exception):
                L2.check()
            self.assertEqual(Ledger(path, 1).summary()["claude-opus-5.5"]["calls"], 1)  # the cache line is no call


class OpenAIEndpoint(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        self.L = Ledger(os.path.join(self.d.name, "l.jsonl"), 10)
        for target, value in ((router, "api_key"), (router, "price"), (router.time, "sleep")):
            p = mock.patch.object(target, value, return_value="k" if value == "api_key" else
                                  (Price(1e-7, 5e-7) if value == "price" else None))
            p.start()
            self.addCleanup(p.stop)

    def test_thinking_off_by_default_and_effort_when_asked(self):
        with mock.patch.object(router.requests, "post", return_value=oa_answer('{"verdict": "merge"}')) as post:
            out = router.call_tool_openai(model="0gm-1.0-35b-a3b", system="s", user="u", tool=TOOL, ledger=self.L)
            body = json.loads(post.call_args.kwargs["data"])
            self.assertEqual(out, {"verdict": "merge"})
            self.assertEqual(body["chat_template_kwargs"], {"enable_thinking": False})
            self.assertTrue(post.call_args.args[0].endswith("/v1/chat/completions"))
            router.call_tool_openai(model="0gm-1.0-35b-a3b", system="s", user="u", tool=TOOL, ledger=self.L,
                                    thinking="medium")
            body = json.loads(post.call_args.kwargs["data"])
            self.assertEqual(body["reasoning_effort"], "medium")
            self.assertNotIn("chat_template_kwargs", body)
        self.assertGreater(self.L.spent, 0)

    def test_garbled_arguments_are_retried_once_then_fail(self):
        with mock.patch.object(router.requests, "post", return_value=oa_answer('{"answer": "391 n product"')) as post:
            with self.assertRaises(router.ToolCallFailed):
                router.call_tool_openai(model="0gm-1.0-35b-a3b", system="s", user="u", tool=TOOL, ledger=self.L)
            self.assertEqual(post.call_count, 2)

    def test_dispatch(self):
        with mock.patch.object(router, "call_tool_openai", return_value={"x": 1}) as oa, \
                mock.patch.object(router, "call_tool", return_value={"y": 2}) as an:
            self.assertEqual(router.call_tool_any(model="0gm-1.0-35b-a3b", system="", user="", tool=TOOL,
                                                  ledger=self.L, thinking="medium"), {"x": 1})
            self.assertEqual(oa.call_args.kwargs["thinking"], "medium")
            self.assertEqual(router.call_tool_any(model="glm-5.3-flash", system="", user="", tool=TOOL,
                                                  ledger=self.L, thinking="medium"), {"y": 2})
            self.assertNotIn("thinking", an.call_args.kwargs)


def row(n=900, ptype="tv-list"):
    return {"pr": n, "title": "Add Acme TV list", "decided_at": "2026-10-28T00:00:00Z", "truth": None,
            "type": ptype, "facts": {"size": "S", "additions": 3, "deletions": 0, "files": 1}, "batch": {}}


def psnap(n=900, patch="+com.acme.ads\n", body="b" * 5000):
    return {"pr": n, "title": "Add Acme TV list", "author": "a", "body": body,
            "files": [{"path": "examples/acme/debloat.txt", "status": "added", "additions": 1, "deletions": 0,
                       "patch": patch}]}


def index(n_hist=40):
    hist = [{"pr": i, "title": f"Add Acme TV list {i}", "truth": "merge", "decided_at": "2026-10-20T00:00:00Z",
             "maintainer_note": "n" * 900, "fix": ""} for i in range(1, n_hist + 1)]
    files = {i: ["examples/acme/debloat.txt"] for i in range(1, n_hist + 1)}
    files[900] = ["examples/acme/debloat.txt"]
    return retrieval.Index(hist + [row()], files, {})


class Context(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(context.parse("dpx"), "DPX")
        self.assertEqual(context.parse("X,D"), "DX")
        self.assertEqual(context.parse("FRI"), "")
        self.assertEqual(context.parse(None), "")

    def test_today_vs_dpx(self):
        big = "+" + "x" * 50_000
        r, s = row(), psnap(patch=big)
        today, used5, _ = context.build(r, s, "RULES", index(), "")
        self.assertIn("more chars", today)
        self.assertNotIn("x" * 7000, today)
        self.assertEqual(len(used5), 5)
        dpx, used30, info = context.build(r, s, "RULES", index(), "DPX", related="### Open PR #901: other")
        self.assertIn("## Diff (full)", dpx)
        self.assertIn("x" * 50_000, dpx)
        self.assertIn("b" * 4000, dpx)
        self.assertNotIn("b" * 4001, dpx)
        self.assertEqual(len(used30), 30)
        self.assertIn("n" * 700, dpx)
        self.assertNotIn("n" * 701, dpx)
        self.assertIn("### Open PR #901", dpx)
        self.assertFalse(info["diff_cut"])

    def test_the_prompt_cap_cuts_related_work_then_the_diff(self):
        huge = "+" + "y" * 390_000
        r, s = row(), psnap(patch=huge)
        user, _, info = context.build(r, s, "RULES", index(), "DPX", related="z" * 100_000)
        self.assertTrue(info["related_cut"])
        self.assertTrue(info["diff_cut"])
        self.assertLessEqual(len(user), context.PROMPT_TOKEN_CAP * context.CHARS_PER_TOKEN)
        self.assertNotIn("zzzz", user)

    def test_judge_with_blocks_and_0gm_second_opinion(self):
        calls = []

        def fake_call(**kw):
            calls.append(("anthropic", kw))
            return {"verdict": "merge", "confidence": 0.9, "reasons": ["ok"]}

        def fake_any(**kw):
            calls.append(("any", kw))
            return {"verdict": "merge", "confidence": 0.8}
        with mock.patch.object(v4, "call_tool", side_effect=fake_call), \
                mock.patch.object(v4, "call_tool_any", side_effect=fake_any):
            out = v4.judge(row(), psnap(), index(), rules_md="R", model="claude-opus-5.5", critic_model=None,
                           second_model="0gm-1.0-35b-a3b", ledger=None, blocks="DPX", related="REL")
        self.assertEqual(out["context"]["blocks"], "DPX")
        self.assertIn(context.LONG_NOTE.strip()[:40], calls[0][1]["system"])
        self.assertIn("## Diff (full)", calls[0][1]["user"])
        second = calls[-1][1]
        self.assertEqual(calls[-1][0], "any")
        self.assertEqual(second["model"], "0gm-1.0-35b-a3b")
        self.assertEqual(second["thinking"], "medium")
        self.assertEqual(second["user"], calls[0][1]["user"])     # the same prompt as the decision
        self.assertEqual(out["second"]["verdict"], "merge")

    def test_default_second_opinion_is_unchanged(self):
        seen = []
        with mock.patch.object(v4, "call_tool", return_value={"verdict": "merge", "confidence": 0.9}), \
                mock.patch.object(v4, "call_tool_any", side_effect=lambda **kw: seen.append(kw) or {"verdict": "merge"}):
            out = v4.judge(row(), psnap(), index(), rules_md="R", model="claude-opus-5.5", critic_model=None,
                           second_model="glm-5.3-flash", ledger=None)
        self.assertEqual(seen[0]["model"], "glm-5.3-flash")
        self.assertIsNone(seen[0]["thinking"])
        self.assertNotIn("context", out)


def patch_of(*hunks):
    return "\n".join(hunks)


class Lines(unittest.TestCase):
    def test_change_blocks(self):
        p = "@@ -10,4 +10,5 @@ x\n a\n-b\n+B\n+C\n c\n d"
        self.assertEqual(dedupe.change_blocks(p), [(11, 11)])
        self.assertEqual(dedupe.change_blocks("@@ -0,0 +1,2 @@\n+a\n+b"), [(1, 0)])

    def test_same_spot_insertions_conflict_and_far_edits_do_not(self):
        a = "@@ -270,3 +270,4 @@\n x\n y\n+NEW_A\n z"
        b = "@@ -270,3 +270,4 @@\n x\n y\n+NEW_B\n z"
        far = "@@ -10,3 +10,4 @@\n x\n y\n+NEW_C\n z"
        self.assertIsNotNone(dedupe.same_lines(a, b))
        self.assertIsNone(dedupe.same_lines(a, far))

    def test_adjacent_change_conflicts(self):
        a = "@@ -5,3 +5,3 @@\n x\n-y\n+Y\n z"          # changes line 6
        b = "@@ -5,3 +5,4 @@\n x\n y\n+NEW\n z"        # inserts before line 7
        self.assertIsNotNone(dedupe.same_lines(a, b))


def pr(n, paths, title="t", body="", head=None):
    return {"pr": n, "title": title, "body": body, "created_at": f"2026-10-{n % 28 + 1:02d}T00:00:00Z", "draft": False,
            "head_sha": head or f"sha{n}", "author": f"u{n}", "paths": paths}


class Candidates(unittest.TestCase):
    def test_signals(self):
        hub = "launcher/app/src/main/java/com/gathin/tvhome/Config.java"
        prs = [pr(1, ["examples/sharp-x/debloat.txt"]), pr(2, ["examples/sharp-x/tv.json", "README.md"]),
               pr(3, ["tools/tv.py", hub]), pr(4, ["tools/tv.py", hub]),
               pr(5, [hub], body="fixes #77"), pr(6, [hub], title="also for #77"), pr(7, [hub]),
               pr(8, ["README.md"]), pr(9, ["README.md"])]
        got = {(c["a"], c["b"]): c["signals"] for c in dedupe.candidate_pairs(prs)}
        self.assertIn("same folder examples/sharp-x/", got[(1, 2)])
        self.assertTrue(any(s.startswith("same files: tools/tv.py") for s in got[(3, 4)]))
        self.assertIn("same issue #77", got[(5, 6)])
        self.assertEqual(got[(5, 7)], ["hub files: " + hub])           # only a hub: lines decide later
        self.assertNotIn((8, 9), got)                                    # README tables are merged mechanically
        only = dedupe.candidate_pairs(prs, only=6)
        self.assertTrue(only and all(6 in (c["a"], c["b"]) for c in only))

    def test_main_folders(self):
        p = pr(1, ["examples/xiaomi-miprojm05/debloat.txt"], title="Xiaomi MiProjM05")
        got = dedupe.main_folder_candidates(p, ["xiaomi-miprojm05"], {"formovie-mprojm05", "tcl-g10-google-tv"},
                                            "", "")
        self.assertEqual([g["folder"] for g in got], ["formovie-mprojm05"])
        p2 = pr(2, ["examples/tcl-55c69b/debloat.txt"], title="TCL 55C69B (G10, Realtek)")
        got = dedupe.main_folder_candidates(p2, ["tcl-55c69b"], {"formovie-mprojm05", "tcl-g10-google-tv"}, "", "")
        self.assertEqual([g["folder"] for g in got], ["tcl-g10-google-tv"])
        self.assertEqual(dedupe.series_named("tcl-55c69b", "| TCL 65C69B (EU) | unit 2 |"), ["C69B"])
        self.assertEqual(dedupe.series_named("tcl-55p7k", "| TCL 65C69B (EU) |"), [])


class FakeGH:
    """open PRs through GraphQL, files, commits, stickies; records writes."""

    def __init__(self, prs, files, commits=None, stickies=None, dry_run=False):
        self.repo, self.dry_run = "o/r", dry_run
        self.prs, self.files, self.commits = prs, files, commits or {}
        self.stickies = stickies or {}
        self.writes = []

    def graphql(self, q, v):
        return {"data": {"repository": {"pullRequests": {"pageInfo": {"hasNextPage": False}, "nodes": [
            {"number": p["pr"], "title": p["title"], "body": p["body"], "createdAt": p["created_at"],
             "isDraft": False, "headRefOid": p["head_sha"], "author": {"login": p["author"]},
             "files": {"nodes": [{"path": x} for x in p["paths"]]}} for p in self.prs]}}}}

    def get(self, path, **kw):
        if path == "":
            return {"default_branch": "main"}
        if path.startswith("/git/trees/"):
            return {"tree": [{"path": "examples/formovie-mprojm05/README.md"}]}
        return {}

    def paged(self, path, limit=300, **kw):
        n = int(path.split("/")[2])
        if path.endswith("/files"):
            return [{"filename": f, "patch": p, "status": "modified"} for f, p in self.files[n].items()]
        if path.endswith("/commits"):
            return [{"sha": s} for s in self.commits.get(n, [f"sha{n}"])]
        if path.endswith("/comments"):
            return [{"id": 1000 + n, "body": self.stickies[n]}] if n in self.stickies else []
        return []

    def file_text(self, path, ref):
        return ""

    def write(self, method, path, body=None):
        self.writes.append((method, path, body))
        return {}


STICKY = ("<!-- maintainer-bot sha=abc123 v=2 -->\n**maintainer-bot review** · suggests **merge** (p2)\n\nThanks!\n\n"
          "<details><summary>Checks</summary>\n\n- **OK**: no protected packages disabled\n- Size: S\n\n</details>\n\n"
          "This is a suggestion.\n\n" + live.FOOTER + "\n" + live.write_data({"m": "merge", "final": "merge"}))


class Pass(unittest.TestCase):
    def setUp(self):
        hub = "launcher/app/src/main/java/com/gathin/tvhome/Config.java"
        ins = "@@ -270,3 +270,4 @@\n x\n y\n+K_{}\n z"
        self.prs = [pr(1, [hub, "a.java"]), pr(2, [hub]), pr(3, [hub]), pr(4, [hub]), pr(5, [hub]),
                    pr(6, ["tools/tv.py"]), pr(7, ["tools/tv.py"], body="stacked on #6", head="sha7"),
                    pr(8, ["examples/x/debloat.txt"]), pr(9, ["examples/x/tv.json"])]
        self.files = {n: {hub: ins.format(n)} for n in (2, 3, 4, 5)}
        self.files[1] = {hub: ins.format(1), "a.java": "@@ -1 +1 @@\n-a\n+b"}
        self.files[6] = {"tools/tv.py": "@@ -1,3 +1,4 @@\n a\n+x\n b\n c"}
        self.files[7] = {"tools/tv.py": "@@ -1,3 +1,4 @@\n a\n+x\n b\n c"}
        self.files[8] = {"examples/x/debloat.txt": "@@ -0,0 +1 @@\n+a"}
        self.files[9] = {"examples/x/tv.json": "@@ -0,0 +1 @@\n+{}"}
        self.commits = {6: ["sha6"], 7: ["sha6", "sha7"]}

    def run_pass(self, answer, only=None, gh=None):
        gh = gh or FakeGH(self.prs, self.files, self.commits)
        asked = []

        def fake_any(**kw):
            asked.append(kw)
            return answer
        with tempfile.TemporaryDirectory() as d, mock.patch.object(dedupe, "call_tool_any", side_effect=fake_any):
            res = dedupe.run(gh, ledger=Ledger(os.path.join(d, "l.jsonl"), 1), only=only, log=lambda s: None,
                             workers=2)
        return res, asked

    def test_hub_conflicts_and_stacks_need_no_model(self):
        res, asked = self.run_pass({"kind": "collision", "why": "same folder"})
        kinds = {(c["a"], c["b"]): c["result"] for c in res["pairs"]}
        self.assertTrue(kinds[(2, 3)]["hub"])
        self.assertEqual(kinds[(6, 7)]["kind"], "stacked")
        self.assertEqual(kinds[(8, 9)]["kind"], "collision")          # same folder: the model's call
        self.assertEqual(len(asked), 1)
        self.assertEqual(asked[0]["model"], "0gm-1.0-35b-a3b")
        self.assertIn("#8", asked[0]["user"])
        self.assertIn("#9", asked[0]["user"])
        lines = live.collision_lines(res["per_pr"][2])
        self.assertEqual(len([l for l in lines if "same lines of `Config.java`" in l]), 1)  # one line, many PRs
        self.assertIn("#1, #3, #4, #5", lines[0])

    def test_the_model_cannot_clear_a_textual_conflict(self):
        prs = [pr(1, ["tools/a.py"]), pr(2, ["tools/a.py"])]
        files = {1: {"tools/a.py": "@@ -5,2 +5,3 @@\n x\n+A\n y"}, 2: {"tools/a.py": "@@ -5,2 +5,3 @@\n x\n+B\n y"}}
        res, asked = self.run_pass({"kind": "none", "why": "different features"}, gh=FakeGH(prs, files))
        self.assertEqual(len(asked), 1)
        r = res["pairs"][0]["result"]
        self.assertEqual((r["kind"], r["source"]), ("conflict", "lines"))

    def test_single_pr_mode_and_apply_touch_only_that_pr_and_partners(self):
        stickies = {n: STICKY for n in range(1, 10)}
        old = live.set_collisions(STICKY, [{"pr": 3, "kind": "conflict", "why": "x", "hub": True},
                                           {"pr": 1, "kind": "collision", "why": "older finding"}])
        stickies[2] = old
        gh = FakeGH(self.prs, self.files, self.commits, stickies)
        res, asked = self.run_pass({"kind": "none", "why": ""}, only=5, gh=gh)
        self.assertTrue(all(5 in (c["a"], c["b"]) for c in res["pairs"]))
        self.assertEqual(asked, [])
        written = dedupe.apply(gh, res)
        self.assertEqual(sorted(w["pr"] for w in written), [1, 2, 3, 4, 5])
        body2 = next(w[2]["body"] for w in gh.writes if w[1] == "/issues/comments/1002")
        kept = live.read_collisions(body2)
        self.assertEqual(sorted(x["pr"] for x in kept), [1, 3, 5])    # #2 keeps what it says about #1 and #3
        self.assertEqual(live.read_data(body2), live.read_data(STICKY))   # the stored judgement is untouched

    def test_dry_run_writes_nothing(self):
        gh = FakeGH(self.prs, self.files, self.commits, {n: STICKY for n in range(1, 10)}, dry_run=True)
        res, _ = self.run_pass({"kind": "collision", "why": "w"}, gh=gh)
        gh.write = lambda *a, **k: self.fail("a dry run must not write")
        live_write = live.GitHub.write
        out = dedupe.apply(type("D", (), {"dry_run": True, "paged": gh.paged, "write": lambda s, *a, **k: {}})(), res)
        self.assertTrue(all(w["action"] in ("dry run", "unchanged", "no review comment yet") for w in out))
        self.assertIs(live.GitHub.write, live_write)


class Sticky(unittest.TestCase):
    ITEMS = [{"pr": 12, "kind": "collision", "why": "both add examples/x/", "first": 12},
             {"pr": 13, "kind": "none"},
             {"pr": 14, "kind": "conflict", "why": "same lines of `Config.java`", "hub": True},
             {"folder": "examples/tcl-g10-google-tv", "kind": "same-device", "why": "a C69B unit is already there"}]

    def test_lines_go_in_checks_and_nothing_else_changes(self):
        body = live.set_collisions(STICKY, self.ITEMS)
        self.assertIn("- **Note**: possibly collides with #12 (both add examples/x/; #12 first)", body)
        self.assertIn("possibly the same device as `examples/tcl-g10-google-tv/` on main", body)
        self.assertIn("possibly collides with #14 (the same lines of `Config.java`", body)
        self.assertNotIn("#13", body.split(live.COLLIDE_MARK)[0])      # a cleared pair gets no line
        self.assertEqual(body.split("<details>")[0], STICKY.split("<details>")[0])   # verdict text untouched
        self.assertEqual(live.read_data(body), live.read_data(STICKY))
        self.assertEqual(live.read_collisions(body), self.ITEMS)
        self.assertEqual(live.set_collisions(body, self.ITEMS), body)   # idempotent
        self.assertEqual(live.set_collisions(body, []), STICKY)         # and removable

    def test_a_comment_without_checks_gets_a_checks_block(self):
        bare = "<!-- maintainer-bot sha=abc v=2 -->\nneeds a maintainer\n\n" + live.FOOTER
        body = live.set_collisions(bare, self.ITEMS[:1])
        self.assertLess(body.index("<details><summary>Checks</summary>"), body.index("<sub>"))

    def test_a_new_review_keeps_the_lines_and_the_same_verdict(self):
        s = {"pr": 7, "title": "Add Acme TV list", "author": "someone", "body": "", "created_at": "2026-10-21T00:00:00Z",
             "head_sha": "1234567890abcdef", "base_ref": "main", "default_branch": "main", "draft": False,
             "state": "open", "labels": [], "files": [{"path": "examples/acme/debloat.txt", "status": "added",
                                                         "additions": 1, "deletions": 0, "patch": "+com.acme.ads\n",
                                                         "binary": False}]}
        data = live.write_data({"m": "merge", "c": 0.9, "crit": 0, "sec": "merge", "diff": live.diff_hash(s),
                                "p": "p2", "reason": "Thanks!", "fix": "", "specific": "", "final": "merge"})
        plain = "<!-- maintainer-bot sha=abcdef123456 v=2 -->\n" + data
        results = []
        for sticky in (plain, live.set_collisions(plain, self.ITEMS)):
            fake = type("G", (), {})()
            fake.get = lambda path, **kw: {}
            fake.paged = lambda path, limit=300, _s=sticky, **kw: ([{"id": 9, "body": _s}]
                                                                   if path.endswith("/comments") else [])
            fake.write = lambda *a, **k: {}
            fake.file_text = lambda *a: ""
            fake.dry_run = True
            with mock.patch.object(live, "GitHub", lambda *a, **k: fake), \
                    mock.patch.object(live, "snapshot", lambda gh, n: s), \
                    mock.patch.object(live, "repo_context", lambda gh, b: {
                        "list_folders": set(), "locales": [], "themes": set(), "addons": set(),
                        "examples_readme": ""}):
                results.append(live.review("o/r", 7, dry_run=True))
        a, b = results
        self.assertEqual((a["verdict"], a["labels"]), (b["verdict"], b["labels"]))
        self.assertNotIn("possibly collides", a["comment"])
        self.assertIn("possibly collides with #12", b["comment"])
        self.assertEqual(live.read_collisions(b["comment"]), self.ITEMS)


class Related(unittest.TestCase):
    def test_related_work_reads_partner_diffs_and_mains_week(self):
        s = {"pr": 7, "default_branch": "main",
             "files": [{"path": "tools/tv.py", "patch": "+x"}, {"path": "README.md", "patch": "+row"}]}
        fx = {"collisions": [{"pr": 8, "kind": "none"}, {"pr": 9, "kind": "conflict"}],
              "possible_duplicates": [{"pr": 10, "merged": True}]}

        class G:
            def get(self, path, **kw):
                if path == "/pulls/8":
                    return {"state": "open", "title": "tv.py: retry"}
                if path == "/pulls/9":
                    return {"state": "closed", "title": "gone"}
                if path.startswith("/commits?"):
                    return [{"sha": "abcdef1234"}] if "tools%2Ftv.py" in path else []
                if path == "/commits/abcdef1234":
                    return {"commit": {"message": "tv.py: timeout\n\nbody"},
                            "files": [{"filename": "tools/tv.py", "patch": "+timeout"},
                                      {"filename": "other.py", "patch": "+nope"}]}
                return {}

            def paged(self, path, limit=100, **kw):
                return [{"filename": "tools/tv.py", "patch": "+retry"}]
        out = live.related_work(G(), s, fx)
        self.assertIn("### Open PR #8: tv.py: retry (shares tools/tv.py)", out)
        self.assertIn("+retry", out)
        self.assertNotIn("#9", out)       # closed since
        self.assertNotIn("#10", out)      # merged: main's commits cover it
        self.assertIn("Merged on main this week: abcdef12 tv.py: timeout", out)
        self.assertNotIn("+nope", out)


if __name__ == "__main__":
    unittest.main()
