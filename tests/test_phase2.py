import os
import unittest

from maintainer_bot.phase2 import commands, fixer, gitops, messages, queue as q, sticky
from maintainer_bot.phase2.executor import Config, Executor
from maintainer_bot.phase2.cli import on_comment
from tests.fake_github import FakeApi, sticky_body

SHA = "a" * 40


class CommandParsing(unittest.TestCase):
    def test_approve_all(self):
        c = commands.parse("/approve")
        self.assertTrue(c.approve_all)
        self.assertFalse(c.empty)

    def test_approve_except(self):
        c = commands.parse("/approve except #12 #15")
        self.assertTrue(c.approve_all)
        self.assertEqual(c.excluded, {12, 15})

    def test_approve_only(self):
        c = commands.parse("/approve #3 #4")
        self.assertFalse(c.approve_all)
        self.assertEqual(c.only, {3, 4})

    def test_skip_close_rework_and_notes(self):
        c = commands.parse("/approve\n/skip #9\n/close #7 a duplicate of #6\n/rework #8 keep autopair enabled\n"
                           "please be gentle with #5")
        self.assertEqual(c.skipped, {9})
        self.assertEqual(c.closes, {7: "a duplicate of #6"})
        self.assertEqual(c.reworks, {8: "keep autopair enabled"})
        self.assertEqual(c.notes, ["please be gentle with #5"])

    def test_plain_text_is_never_an_action(self):
        c = commands.parse("approve everything please, merge #4 and close #5")
        self.assertTrue(c.empty)
        self.assertEqual(c.plan({4: {"verdict": "merge"}, 5: {"verdict": "close"}}), {})

    def test_command_must_start_the_line(self):
        self.assertTrue(commands.parse("I think we should /approve later").empty)

    def test_plan(self):
        queue = {1: {"verdict": "merge"}, 2: {"verdict": "merge-with-fix", "fix": "add the row"},
                 3: {"verdict": "rework", "ask": "keep autopair"}, 4: {"verdict": "close", "reason": "dup"},
                 5: {"verdict": "hold"}, 6: {"verdict": "merge"}}
        p = commands.parse("/approve except #6\n/skip #3").plan(queue)
        self.assertEqual(sorted(p), [1, 2, 4])
        self.assertEqual(p[2]["text"], "add the row")
        p = commands.parse("/approve #1\n/close #5 not for the core launcher").plan(queue)
        self.assertEqual(sorted(p), [1, 5])
        self.assertEqual(p[5], {"action": "close", "text": "not for the core launcher", "source": "command"})
        p = commands.parse("/approve").plan(queue)
        self.assertNotIn(5, p)  # needs a maintainer never moves with /approve

    def test_permissions(self):
        self.assertTrue(commands.allowed("Gathin23", "OWNER"))
        self.assertFalse(commands.allowed("someone", "CONTRIBUTOR"))
        self.assertFalse(commands.allowed("someone", "MEMBER"))
        self.assertFalse(commands.allowed("someone", "COLLABORATOR"))
        self.assertTrue(commands.allowed("Helper", "COLLABORATOR", {"helper"}))


class StickyParsing(unittest.TestCase):
    def test_reads_back_the_review(self):
        body = sticky_body(SHA, "merge-with-fix", fix="Add the row to the README table.", priority="p1")
        s = sticky.parse(body, ["bot-suggests:merge-with-fix", "p1"])
        self.assertEqual((s["sha"], s["verdict"], s["priority"]), (SHA[:12], "merge-with-fix", "p1"))
        self.assertEqual(s["fix"], "Add the row to the README table.")
        self.assertTrue(s["reason"].startswith("Thanks for the PR"))

    def test_words_when_labels_were_removed(self):
        self.assertEqual(sticky.parse(sticky_body(SHA, "close"), [])["verdict"], "close")
        self.assertEqual(sticky.parse(sticky_body(SHA, "hold", question="launcher code"), [])["verdict"], "hold")

    def test_no_review(self):
        self.assertIsNone(sticky.parse("nice PR", []))


def _queue_api():
    api = FakeApi()
    api.add_pr(1, title="Add TCL 50C647 list", sha="1" * 40, verdict="merge", priority="p1")
    api.add_pr(2, title="Add Sony list", sha="2" * 40, verdict="merge-with-fix", fix="Add the README row.")
    api.add_pr(3, title="Add Vu list", sha="3" * 40, verdict="rework", ask="Keep com.tcl.autopair enabled.")
    api.add_pr(4, title="Weather card", sha="4" * 40, verdict="close", reason="Thanks! It needs INTERNET.")
    api.add_pr(5, title="Launcher clock", sha="5" * 40, verdict="hold", question="launcher code",
               labels=["launcher"])
    api.add_pr(6, title="Add Hisense list", sha="6" * 40, verdict="merge", sticky_sha="9" * 40)  # pushed since
    api.add_pr(7, title="WIP", sha="7" * 40)  # not reviewed
    api.add_pr(9, title="Add Onn list", sha="b" * 40, verdict="merge", labels=["on-hold"])
    api.add_pr(10, title="Add Kogan list", sha="c" * 40, verdict="rework", ask="x", labels=["needs-rework"])
    return api


class QueueRendering(unittest.TestCase):
    def test_sections_checkboxes_and_data(self):
        api = _queue_api()
        items, stats = q.collect(api)
        self.assertEqual(sorted(items), [1, 2, 3, 4, 5])
        self.assertEqual(stats["stale"], [6])
        self.assertEqual(stats["unreviewed"], 1)
        self.assertEqual((stats["on_hold"], stats["waiting"]), ([9], [10]))
        body = q.render("2026-10-22", items, stats)
        self.assertIn("### Merge (1)\n- [ ] #1 Add TCL 50C647 list (by someone) · p1", body)
        self.assertIn("- [ ] #2 Add Sony list (by someone) · p2 · fix: Add the README row.", body)
        self.assertIn("ask: Keep com.tcl.autopair enabled.", body)
        self.assertIn("### Needs a maintainer (1)", body)
        self.assertIn("- #5 Launcher clock", body)  # no checkbox
        self.assertNotIn("- [ ] #5", body)
        self.assertNotIn("@someone", body)  # the queue never pings authors
        data = q.read_data(body)
        self.assertEqual(data["items"]["1"], {"sha": "1" * 12, "v": "merge"})
        self.assertIn("runs on [0G Private Computer]", body)

    def test_upsert_creates_then_updates_and_closes_old(self):
        api = _queue_api()
        r = q.upsert(api, "2026-10-21")
        self.assertEqual(r["action"], "created")
        api.comments[r["issue"]].append({"id": 1, "author": "Gathin23", "association": "OWNER",
                                         "body": "check #3 again tomorrow", "created_at": ""})
        r2 = q.upsert(api, "2026-10-22")
        self.assertEqual(r2["action"], "created")
        self.assertEqual(api.issues[r["issue"]]["state"], "closed")
        self.assertIn("check #3 again tomorrow", api.issues[r2["issue"]]["body"])
        self.assertEqual(q.upsert(api, "2026-10-22")["action"], "updated")

    def test_tick(self):
        body = "- [ ] #1 A\n- [ ] #12 B"
        self.assertEqual(q.tick(body, 1, "merged"), "- [x] #1 A · **merged**\n- [ ] #12 B")

    def test_big_queue_stays_under_the_issue_limit(self):
        api = FakeApi()
        for n in range(1, 700):
            api.add_pr(n, title="Add a very long TV list title " * 3, sha=f"{n:040d}", verdict="merge",
                       reason="Thanks! " + "x" * 300)
        items, stats = q.collect(api)
        body = q.render("2026-10-22", items, stats)
        self.assertLessEqual(len(body), q.MAX_BODY)
        self.assertTrue(stats["deferred"])


def _executor(api, **kw):
    return Executor(api, Config(sleep=lambda s: None, log=lambda s: None, **kw))


def _issue(api, date="2026-10-22"):
    q.upsert(api, date)
    return max(api.issues)


class ExecutorDecisions(unittest.TestCase):
    def test_merge_rework_close_and_skips(self):
        api = _queue_api()
        n = _issue(api)
        res = _executor(api).run(n, commands.parse("/approve"))
        out = {o["pr"]: o for o in res["outcomes"]}
        self.assertEqual(out[1]["status"], "done")
        self.assertIn(("merge", 1, "1" * 40, "Merge PR #1: Add TCL 50C647 list"), api.calls)
        self.assertEqual(out[3]["status"], "done")
        self.assertIn("needs-rework", api.prs[3]["labels"])
        self.assertEqual(api.prs[4]["state"], "closed")
        self.assertNotIn(5, out)  # needs a maintainer: untouched
        self.assertNotIn(6, out)  # stale: never queued
        self.assertEqual(out[2]["status"], "skipped")  # merge-with-fix without a git checkout
        thanks = api.comments[1][-1]["body"]
        self.assertIn("Great to have the TCL 50C647 on the list.", thanks)
        self.assertIn("runs on [0G Private Computer]", thanks)
        self.assertIn("- [x] #1 ", api.issues[n]["body"])
        self.assertIn("Batch for the maintainer's approval", api.comments[n][-1]["body"])

    def test_head_changed_after_queue_is_skipped(self):
        api = _queue_api()
        n = _issue(api)
        api.prs[1]["head_sha"] = "8" * 40  # the author pushed after the queue was built
        res = _executor(api).run(n, commands.parse("/approve #1"))
        self.assertEqual(res["outcomes"][0]["status"], "skipped")
        self.assertIn("new commits", res["outcomes"][0]["detail"])
        self.assertFalse([c for c in api.calls if c[0] == "merge"])

    def test_red_ci_stops_the_batch(self):
        api = _queue_api()
        api.add_pr(8, title="Add Vu 2 list", sha="8" * 40, verdict="merge", priority="p3")
        n = _issue(api)
        api.check_state["1" * 40] = {"state": "failure", "failed": ["Lists, tools and docs"], "pending": []}
        res = _executor(api).run(n, commands.parse("/approve"))
        self.assertIn("checks failing on #1", res["stopped"])
        self.assertFalse([c for c in api.calls if c[0] == "merge"])  # #8 comes after #1 and never runs
        self.assertIn("**Stopped at #1", api.comments[n][-1]["body"])

    def test_pending_checks_skip_for_today(self):
        api = _queue_api()
        n = _issue(api)
        api.check_state["1" * 40] = {"state": "pending", "failed": [], "pending": ["Launcher build (needs approval)"]}
        res = _executor(api).run(n, commands.parse("/approve #1"))
        self.assertEqual(res["outcomes"][0]["status"], "skipped")
        self.assertFalse(res["stopped"])

    def test_never_merges_maintainer_only_prs(self):
        api = FakeApi()
        api.add_pr(1, title="Add list", sha="1" * 40, verdict="merge", labels=["launcher"])
        api.add_pr(2, title="CI tweak", sha="2" * 40, verdict="merge", paths=[".github/workflows/ci.yml"])
        api.add_pr(3, title="Rules", sha="3" * 40, verdict="merge", paths=[".github/maintainer/MAINTAINER.md"])
        n = _issue(api)
        res = _executor(api).run(n, commands.parse("/approve"))
        self.assertEqual([o["status"] for o in res["outcomes"]], ["skipped"] * 3)
        self.assertFalse([c for c in api.calls if c[0] == "merge"])

    def test_launcher_label_blocks_only_a_v1_review(self):
        api = FakeApi()
        api.add_pr(1, title="launcher: dock_glass", sha="1" * 40, verdict="merge", labels=["launcher"], version=2,
                   paths=["launcher/app/src/main/res/values/config.xml"])
        api.add_pr(2, title="launcher: old review", sha="2" * 40, verdict="merge", labels=["launcher"],
                   paths=["launcher/app/src/main/res/values/config.xml"])
        n = _issue(api)
        res = _executor(api).run(n, commands.parse("/approve"))
        out = {o["pr"]: o for o in res["outcomes"]}
        self.assertEqual(out[1]["status"], "done")
        self.assertEqual(out[2]["status"], "skipped")
        self.assertIn("maintainer only", out[2]["detail"])

    def test_showcase_addon_and_theme(self):
        api = FakeApi()
        api.add_pr(1, title="launcher: weather card", sha="1" * 40, verdict="showcase", version=2,
                   data={"m": "showcase", "specific": "the weather card's careful layout"})
        api.add_pr(2, title="launcher: screen time", sha="2" * 40, verdict="addon", version=2,
                   data={"m": "addon", "specific": "the counting tests", "fix": "screen-time"})
        api.add_pr(3, title="launcher: amber look", sha="3" * 40, verdict="theme", version=2,
                   data={"m": "theme", "specific": "the warm amber palette", "fix": "amber"})
        n = _issue(api)
        body = api.issues[n]["body"]
        self.assertIn("### Close, and offer a SHOWCASE row for the fork (1)", body)
        self.assertIn("### Close, and invite it as an add-on (1)", body)
        self.assertIn("### Move to themes/ (1)", body)
        cfg_link = "https://github.com/o/r/blob/main/CONTRIBUTING.md#where-does-my-idea-go"
        res = Executor(api, Config(sleep=lambda s: None, log=lambda s: None, where_link=cfg_link)).run(
            n, commands.parse("/approve"))
        self.assertEqual({o["pr"]: o["status"] for o in res["outcomes"]}, {1: "done", 2: "done", 3: "done"})
        self.assertEqual(api.prs[1]["state"], "closed")
        self.assertIn("Thank you for this, the weather card's careful layout!", api.comments[1][-1]["body"])
        self.assertIn("SHOWCASE.md", api.comments[1][-1]["body"])
        self.assertIn(cfg_link, api.comments[1][-1]["body"])
        self.assertEqual(api.prs[2]["state"], "closed")
        self.assertIn("addons/screen-time/", api.comments[2][-1]["body"])
        self.assertEqual(api.prs[3]["state"], "open")
        self.assertIn("needs-rework", api.prs[3]["labels"])
        self.assertIn("themes/amber/", api.comments[3][-1]["body"])
        self.assertFalse([c for c in api.calls if c[0] == "merge"])

    def test_close_command_moves_a_held_pr(self):
        api = _queue_api()
        n = _issue(api)
        _executor(api).run(n, commands.parse("/close #5 the launcher stays offline"))
        self.assertEqual(api.prs[5]["state"], "closed")
        self.assertIn("The launcher stays offline.", api.comments[5][-1]["body"])

    def test_suggestion_changed_since_queue(self):
        api = _queue_api()
        n = _issue(api)
        api.prs[1]["labels"] = ["bot-suggests:rework"]  # re-labelled after the queue was built
        res = _executor(api).run(n, commands.parse("/approve #1"))
        self.assertIn("suggestion is now rework", res["outcomes"][0]["detail"])

    def test_dry_run_writes_nothing(self):
        api = _queue_api()
        n = _issue(api)
        before = (len(api.calls), api.issues[n]["body"])
        res = _executor(api, dry_run=True).run(n, commands.parse("/approve"))
        self.assertEqual((len(api.calls), api.issues[n]["body"]), before)
        self.assertTrue(all(o["status"] in ("would", "skipped") for o in res["outcomes"]))


class FixLimits(unittest.TestCase):
    files = {"README.md": "| A | x |\n| C | y |\n", ".github/workflows/ci.yml": "on: push\n"}

    def read(self, p):
        return self.files.get(p)

    def test_ok(self):
        self.assertEqual(fixer.validate([{"path": "README.md", "search": "| C | y |", "replace": "| B | z |\n| C | y |"}],
                                        self.read), [])

    def test_too_many_lines(self):
        big = "\n".join(f"| R{i} |" for i in range(40))
        p = fixer.validate([{"path": "README.md", "search": "| C | y |", "replace": big}], self.read)
        self.assertTrue(any("changed lines" in x for x in p))

    def test_sensitive_and_traversal(self):
        for path in (".github/workflows/ci.yml", "PROMPT.md", "tools/disable.sh", "../etc/passwd", "/etc/passwd"):
            p = fixer.validate([{"path": path, "search": "", "replace": "x"}], self.read)
            self.assertTrue(p, path)

    def test_search_must_be_unique(self):
        p = fixer.validate([{"path": "README.md", "search": "|", "replace": "!"}], self.read)
        self.assertTrue(any("found" in x for x in p))

    def test_make_with_fake_model(self):
        prop = lambda **kw: {"edits": [{"path": "README.md", "search": "| C | y |", "replace": "| B |\n| C | y |"}],
                             "summary": "On merge: added the row"}  # noqa: E731
        r = fixer.make(pr=1, title="t", fix_text="add the README row", paths=["README.md"], diff="", read=self.read,
                       propose=prop, model="m", ledger=None)
        self.assertEqual((r["problems"], r["summary"]), ([], "added the row"))


class ConflictRules(unittest.TestCase):
    def test_table_rows_keep_both(self):
        text = "| T |\n<<<<<<< HEAD\n| B pr |\n=======\n| A main |\n>>>>>>> origin/main\nend"
        out, notes = gitops.resolve_text(text)
        self.assertEqual(out, "| T |\n| A main |\n| B pr |\nend")

    def test_count_lines_take_main(self):
        text = ("<<<<<<< HEAD\n**TCL** 41 · **Sony** 22 ·\n=======\n**TCL** 40 · **Sony** 23 ·\n>>>>>>> m\n")
        out, _ = gitops.resolve_text(text)
        self.assertIn("**TCL** 40 · **Sony** 23 ·", out)
        self.assertNotIn("41", out)

    def test_prose_conflict_gives_up(self):
        out, _ = gitops.resolve_text("<<<<<<< HEAD\nSome text\n=======\nOther text\n>>>>>>> m\n")
        self.assertIsNone(out)


class Messages(unittest.TestCase):
    def test_thanks_names_the_fix(self):
        t = messages.thanks(12, "Add Philips 55PUS list", is_list=True, fix_summary="on merge: added the README row",
                            bot_pr=40)
        self.assertIn("On merge: Added the README row. (through #40)", t)
        self.assertNotIn(sticky.MARKER, t)  # never mistaken for the review comment

    def test_close_drops_double_thanks(self):
        t = messages.close(3, "Thanks for the PR! We already have this TV.")
        self.assertIn("Thanks for taking the time on this! We already have this TV.", t)


class CommentEvent(unittest.TestCase):
    def _event(self, tmp, body, assoc="OWNER", login="Gathin23", labels=("maintainer-queue",)):
        import json
        p = os.path.join(tmp, "event.json")
        with open(p, "w") as f:
            json.dump({"issue": {"number": 1, "labels": [{"name": l} for l in labels]},
                       "comment": {"body": body, "author_association": assoc,
                                   "user": {"login": login, "type": "User"}}}, f)
        return p

    def test_non_owner_ignored_silently(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            r = on_comment("o/r", self._event(tmp, "/approve", assoc="CONTRIBUTOR", login="x"))
            self.assertEqual(r, {"ignored": "not an allowed commenter"})
            r = on_comment("o/r", self._event(tmp, "/approve", labels=("bug",)))
            self.assertEqual(r, {"ignored": "not a queue issue"})
            r = on_comment("o/r", self._event(tmp, "looks good, thanks"))
            self.assertEqual(r, {"notes": ["looks good, thanks"]})


if __name__ == "__main__":
    unittest.main()
