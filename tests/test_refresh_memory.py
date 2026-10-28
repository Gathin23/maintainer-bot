"""The memory refresh: round notes -> precedents.jsonl and the MAINTAINER.md policy block."""
import json
import os
import tempfile
import unittest

from maintainer_bot import memory_refresh as mr

BUCKETS = """# Round X decisions

| Bucket | Count | |
|---|---|---|
| Merge as is | 1 | lists |

## Calls I'm least sure of

1. **#10 a launcher switch: merge.** It is small.

## Merge as is (1)

| PR | Title (author) | What it does | Why |
|---|---|---|---|
| #10 | Launcher: a switch (@alice) | adds an off-by-default key. | small, tested. |

## Merge with a fix folded in (1)

| PR | Title (author) | What it does | The fix |
|---|---|---|---|
| #11 | examples: a TV (@bob) | a new folder. | add tv.json |

## Ask (new comment) (1)

| PR | Title (author) | What it does | Why ask |
|---|---|---|---|
| #12 | tools: a fix (@carol) | fixes a thing. | needs a test |

## Close when the 72 h clock ends (skipped if the author pushed since the ask) (1)

| PR | Title (author) | What it does | Recommendation | Why |
|---|---|---|---|---|
| #13 | Launcher: a look tweak (@dan) | a glow colour. | when the clock ends | a look tweak |

## Hold: waiting on us (1)

| PR | Title (author) | What it does | Recommendation | Why |
|---|---|---|---|---|
| #14 | Launcher: Home path (@erin) | changes boot. | - | needs a TV run |

## Wait: ask already out or draft, no new comment (1)

| PR | Title (author) | What it does | Recommendation | Why |
|---|---|---|---|---|
| #15 | a draft (@fay) | draft. | wait | - |

## Drafted comments

### Merge as is

#10:
Merged, thanks @alice!
"""

REVIEW = """# Round Y, reviewer A: 3 PRs

| PR | verdict | head SHA reviewed | author | one-line what | one-line why |
|---|---|---|---|---|---|
| #20 | MERGE | abc123 | @a | a list | tested |
| #21 | MERGE+FIX | def456 | @b | a note | typo |
| #22 | ASK | 0123ab | @c | a tool | needs tests |
| #23 | HOLD | 4567cd | @d | Home path | your run |

## ASK drafts

#22:
Thanks @c, could you add a test?

#24: no new comment. The earlier ask covers it.

## CLOSE drafts (post each only after its deadline)

#25 (after 28 Oct 05:26 UTC):
Thanks @e, closing this for now.
"""

APPLIED = """# Round Y applied

## Applied

| # | PR | merge SHA | author | fix folded in |
|---|---|---|---|---|
| 1 | #20 a list | 16b67e75 | @a | |
| 2 | #21 a note | 057e75f8 | @b | Fixed the typo. |
| | README tables, counts and card | 9f086119 | | regenerated |

## Held for Gathin (nothing posted)

### The ten launcher switches

All ten are off by default.

1. **#30 `clock_format`**: a clock row.
2. **#31 `tile_names`, #32 `dock_size`**: look switches.

Standing asks with nothing new to post:
- #40, #41: 28 Oct 17:46 UTC

## Asks and closes drafted, not posted

#26 (@g, a folder, ASK):
Thanks @g, could you fold this into the existing folder?

#27 (@h, an empty list, CLOSE):
Thanks @h, there's nothing to merge here.
"""

ROUND_AA = """# Round AA

- **Merged 3:**
  - 2 with the bot's merge label: #50, #51.
  - 1 where our ask was answered: #52 (showcase row, one line).
- **Skipped from the bot's merge set (1 of 4):**
  - Launcher: #53.
- Fold-ins (in the merge commits):
  - #50: the set keeps the notes index line.

## First asks (2, labelled needs-rework)

- #60: fold into tcl-55ep640.
- #61: rebase (#1519 has landed).

## Stale (proposed, not closed)

- **#62** (Sony): the fold-in ask went out with no reply.
"""


class ParseTest(unittest.TestCase):
    def test_bucket_tables(self):
        d = mr.parse_round_text(BUCKETS)
        self.assertEqual({n: e["truth"] for n, e in d.items()},
                         {10: "merge", 11: "merge-with-fix", 12: "rework", 13: "close", 14: "hold"})
        self.assertEqual(d[10]["title"], "Launcher: a switch")
        self.assertIn("off-by-default", d[10]["maintainer_note"])
        self.assertEqual(d[11]["fix"], "add tv.json")
        self.assertNotIn(15, d)       # a wait bucket is not a decision

    def test_verdict_table_and_drafts(self):
        d = mr.parse_round_text(REVIEW)
        self.assertEqual({n: e["truth"] for n, e in d.items()},
                         {20: "merge", 21: "merge-with-fix", 22: "rework", 23: "hold", 25: "close"})
        self.assertNotIn("abc123", d[20]["maintainer_note"])    # no SHA or author in the note
        self.assertIn("Thanks @c", d[22]["maintainer_note"])    # the drafted ask is the note
        self.assertNotIn(24, d)                                 # "no new comment"

    def test_applied_table_holds_and_drafted_asks(self):
        d = mr.parse_round_text(APPLIED)
        self.assertEqual(d[20]["truth"], "merge")
        self.assertEqual(d[21]["truth"], "merge-with-fix")
        self.assertEqual(d[21]["fix"], "Fixed the typo.")
        self.assertEqual([d[n]["truth"] for n in (30, 31, 32)], ["hold"] * 3)
        self.assertNotIn(40, d)        # standing asks are not new decisions
        self.assertEqual(d[26]["truth"], "rework")
        self.assertEqual(d[27]["truth"], "close")

    def test_round_aa_bullets(self):
        d = mr.parse_round_text(ROUND_AA)
        self.assertEqual(d[50]["truth"], "merge-with-fix")       # merged, with a fold-in
        self.assertEqual(d[51]["truth"], "merge")
        self.assertEqual(d[52]["maintainer_note"], "showcase row, one line")
        self.assertNotIn(53, d)                                  # skipped, not merged
        self.assertEqual(d[60]["truth"], "rework")
        self.assertEqual(d[60]["maintainer_note"], "#60: fold into tcl-55ep640.")
        self.assertNotIn(62, d)                                  # stale is not a decision


class FoldTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        for name, text in (("r1.md", BUCKETS), ("r2a.md", REVIEW), ("r2.md", APPLIED)):
            with open(os.path.join(self.dir, name), "w") as f:
                f.write(text)
        self.rounds = [("r1", ["r1.md"], "2026-10-25T00:00:00Z"), ("r2", ["r2a.md", "r2.md"], "2026-10-26T00:00:00Z")]

    def test_later_round_wins_and_keeps_the_earlier_verdict(self):
        base = [{"pr": 12, "title": "old", "truth": "merge", "decided_at": "2026-10-20T00:00:00Z",
                 "maintainer_note": "", "fix": "", "files": ["a.py"]}]
        rounds = mr.parse_rounds(self.dir, rounds=self.rounds)
        e = mr.fold(base, rounds)
        self.assertEqual(e[12]["truth"], "rework")
        self.assertTrue(e[12]["maintainer_note"].startswith("(earlier: merge)"))
        self.assertEqual(e[12]["files"], ["a.py"])               # files carried over
        # within one round, the review's note survives the applied table's empty cell
        self.assertEqual(e[20]["decided_at"], "2026-10-26T00:00:00Z")
        self.assertIn("tested", e[20]["maintainer_note"])

    def test_until_stops_after_that_round(self):
        rounds = mr.parse_rounds(self.dir, until="r1", rounds=self.rounds)
        self.assertEqual([k for k, _, _ in rounds], ["r1"])
        self.assertNotIn(20, mr.fold([], rounds))

    def test_jsonl_keys_and_order(self):
        e = mr.fold([], mr.parse_rounds(self.dir, rounds=self.rounds))
        rows = [json.loads(l) for l in mr.to_jsonl(e).splitlines()]
        self.assertEqual(set(rows[0]), set(mr.KEYS))
        self.assertEqual(rows, sorted(rows, key=lambda r: r["decided_at"]))


class GitHubTest(unittest.TestCase):
    def entries(self):
        mk = lambda n, t: {"pr": n, "title": "", "truth": t, "decided_at": "2026-10-26T00:00:00Z",
                           "maintainer_note": "note", "fix": "", "files": []}
        return {1: mk(1, "rework"), 2: mk(2, "rework"), 3: mk(3, "merge"), 4: mk(4, "merge-with-fix"), 5: mk(5, "close")}

    def gh(self):
        g = lambda state, merged, at: {"title": "T", "state": state, "merged": merged, "files": ["x"],
                                       "merged_at": at if merged else "", "closed_at": at}
        return {1: g("MERGED", True, "2026-10-27T00:00:00Z"), 2: g("CLOSED", False, "2026-10-27T00:00:00Z"),
                3: g("OPEN", False, ""), 4: g("MERGED", True, "2026-10-26T01:00:00Z"),
                5: g("CLOSED", False, "2026-10-26T02:00:00Z")}

    def test_github_settles_what_happened(self):
        e = self.entries()
        stats = mr.cross_check(e, self.gh())
        self.assertEqual([e[n]["truth"] for n in range(1, 6)], ["merge", "close", "hold", "merge-with-fix", "close"])
        self.assertTrue(e[1]["maintainer_note"].startswith("(earlier: rework) merged later"))
        self.assertTrue(e[3]["maintainer_note"].startswith("(round said merge; not merged at apply)"))
        self.assertEqual(e[1]["decided_at"], "2026-10-27T00:00:00Z")
        self.assertEqual((e[1]["title"], e[1]["files"]), ("T", ["x"]))
        self.assertEqual((stats["merged_override"], stats["closed_override"], stats["accept_not_merged"]), (1, 1, 1))

    def test_cutoff_ignores_the_future(self):
        e = self.entries()
        mr.cross_check(e, self.gh(), cutoff="2026-10-26T12:00:00Z")
        self.assertEqual(e[1]["truth"], "rework")     # merged after the cutoff: not known yet
        self.assertEqual(e[2]["truth"], "rework")
        self.assertEqual(e[4]["truth"], "merge-with-fix")

    def test_fetch_prs_batches_and_skips_issues(self):
        queries = []

        def fake(q):
            queries.append(q)
            nums = [int(x) for x in __import__("re").findall(r"pullRequest\(number: (\d+)\)", q)]
            return {"repository": {f"p{n}": (None if n == 7 else {
                "number": n, "title": f"PR {n}", "state": "MERGED", "merged": True, "mergedAt": "2026-10-26T00:00:00Z",
                "closedAt": "2026-10-26T00:00:00Z", "files": {"nodes": [{"path": "a"}, {"path": "b"}]}}) for n in nums}}

        got = mr.fetch_prs([5, 6, 7, 8, 6], batch=2, gql=fake)
        self.assertEqual(sorted(got), [5, 6, 8])
        self.assertEqual(len(queries), 2)
        self.assertEqual(got[5]["files"], ["a", "b"])
        self.assertIn('repository(owner: "Gathin23", name: "cleanyourtv")', queries[0])


class PolicyTest(unittest.TestCase):
    def test_block_is_appended_once_and_replaced(self):
        rules = "# Rules\n\n## Lists\n- one\n"
        block = "## Policies from Rounds AA–AG (25–28 Oct)\n- a rule (#1)\n"
        once = mr.apply_policy_block(rules, block)
        self.assertEqual(once.count("## Policies"), 1)
        twice = mr.apply_policy_block(once, block.replace("a rule", "a new rule"))
        self.assertEqual(twice.count("## Policies"), 1)
        self.assertIn("a new rule", twice)
        self.assertIn("## Lists", twice)

    def test_block_in_the_middle_keeps_what_follows(self):
        rules = "# R\n\n## Policies from X\n- old\n\n## Comment style\n- short\n"
        out = mr.apply_policy_block(rules, "## Policies from X\n- new\n")
        self.assertIn("- new", out)
        self.assertNotIn("- old", out)
        self.assertIn("## Comment style\n- short", out)

    def test_candidates_take_least_sure_calls(self):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "round-aa.md"), "w") as f:
            f.write(BUCKETS)
        text = mr.policy_candidates(d, until="aa")
        self.assertIn("## Calls I'm least sure of", text)
        self.assertIn("#10 a launcher switch", text)
        self.assertNotIn("Merged, thanks", text)

    def test_shipped_policy_blocks_fit_the_prompt(self):
        here = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples", "cleanyourtv",
                            "policies")
        for name in ("rounds-aa-ag2.md", "rounds-aa-af.md"):
            with open(os.path.join(here, name), encoding="utf-8") as f:
                text = f.read()
            self.assertLess(len(text), 4000, name)
            self.assertTrue(text.startswith("## Policies from Rounds"), name)
            self.assertIn("Gathin to approve", text)


if __name__ == "__main__":
    unittest.main()
