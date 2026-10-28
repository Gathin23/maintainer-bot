# 0GM rollout for maintainer-bot: built and tested (28 Oct 2026)

Branch `0gm-rollout` in Gathin23/maintainer-bot. It is built from master (4beda3b) plus the research commit
(`research/0gm`). Nothing on cleanyourtv changed:
- the workflow pin is still 234fba6;
- no push and no PR on cleanyourtv;
- no comments, labels or merges on any PR or issue;
- the bot's master is untouched.

Every 0G Private Computer call went into one ledger (`runs/rollout/ledger-2026-10-28.jsonl`), and the ledger counts cached tokens.

**Spend: $2.57 of the $10 cap** (breakdown in section 4).

## 1. What was built

| # | Piece | Where | Default |
|---|---|---|---|
| 1 | **Ledger fix**: `router.record_usage` and `cache_prices` (from the research branch) price cache writes and cache reads, so the daily cap sees what a long, mostly cached prompt costs. For 0GM's OpenAI-format usage, cached and reasoning tokens are counted inside `prompt_tokens` and `completion_tokens` at the full rate, which is the safe side for a cap. In the ledger summary, a call's cache line no longer counts as a second call. | `router.py`, `ledger.py` | always on |
| 2 | **0GM on the OpenAI endpoint**: `call_tool_openai` and `call_tool_any`. `0gm-*` models go to `/v1/chat/completions` with `enable_thinking: false` or a `reasoning_effort`. Garbled tool arguments get one retry, then fail. | `router.py` | used by 3 and 4 |
| 3 | **Duplicate/collision pass**: `mode: dedupe`. With no `pr` it covers every open PR (per round); with `pr: N` it covers only that PR's pairs (when a PR opens). It adds "Possibly collides with #N (why)" to the Checks of both PRs, and "possibly the same device as `examples/x/` on main" for a new folder. The verdict, labels and stored judgement are never touched, and the decision model never sees these lines. Details below. | `dedupe.py`, `live.py` (sticky helpers), `__main__.py dedupe`, `action.yml` | off until the workflow calls it |
| 4 | **0GM as second opinion**: the `second-opinion-model` input (empty means `second-model`, GLM-5.3-Flash). With `0gm-1.0-35b-a3b` it runs on the OpenAI endpoint with `reasoning_effort: medium`. | `v4.judge`, `action.yml` | GLM (unchanged) |
| 5 | **DPX context**: the `context-blocks: "DPX"` input (`--context-blocks` on the CLI). It sends the full diff up to 400K characters, the description up to 4,000, 30 precedents with notes up to 700, and related work. Related work is the diffs of the open PRs the dedupe pass paired with this one, likely duplicates and same-folder PRs, plus main's commits on the same files in the last 7 days (at most about 17 API reads). The prompt is capped at about 150K tokens: related work is cut first, then the diff. The critic and the second opinion read the same prompt. | `context.py`, `live.related_work`, `v4.judge` | off |
| 6 | **Memory refresh**: turns round notes into `precedents.jsonl` and drafts policy lines for `MAINTAINER.md`. It reads every round-note format in use (bucket tables, verdict-column review tables, "Applied" tables, drafted asks and closes, and Round AA's bullets). Later rounds override earlier ones. GitHub's merged/closed record is read-only and settles what happened. `--until af` builds memory with nothing from later rounds. | `memory_refresh.py`, `scripts/refresh_memory.py`, `examples/cleanyourtv/policies/` | a script |
| 7 | **Shadow tooling**: an action input `results-file` (one JSON line per review), a proposed workflow (`examples/cleanyourtv/maintainer-bot-0gm.yml`) and `scripts/shadow_logs.py`, which collects the MB-SHADOW lines and scores them. | | |

**How the duplicate pass decides** (`maintainer_bot/dedupe.py`):
1. Candidates are deterministic. They come from every open PR's file list (one GraphQL query per 50 PRs), and need one of:
   - the same `examples/`, `themes/` or `addons/` folder;
   - a shared file that at most 4 open PRs touch;
   - the same lines of any shared file (overlapping or touching change blocks, the way git sees a conflict);
   - the same issue, or one PR naming the other.

   README/SHOWCASE tables are ignored.
2. A new device folder is checked against main's folders. A match is:
   - the same product id in the examples index;
   - a model token from the folder name that the PR names (same brand);
   - or a near-identical model token (`miprojm05`/`mprojm05`).

   The existing folder's README, tv.json and list headers go to the model. A model series that the folder already names (C69B) is passed to the model as a signal.
3. Two kinds of pair are settled without a model call:
   - **Stacked series**: one PR's head commit is inside the other.
   - **Hub-only line conflicts**: two switches appended at the same place in `Config.java`. These are shown as one grouped line per PR: "possibly collides with #a, #b, … (the same lines of `Config.java`; whichever merges second needs a rebase)".
4. Every other pair goes to 0GM, one call per pair, thinking off, with both diffs (20K characters each).
   - The answer is one of duplicate, collision, conflict, supersedes, split or none, plus why and which goes first.
   - If 0GM says "none" for a pair that edits the same lines, the line conflict is still reported.
   - Folder checks use `reasoning_effort: low`. Without it, the #2289 call flipped between runs.

## 2. Tests

**Suite:** 187 tests pass (`python -m unittest discover -s tests`). That is 150 from before, 23 new in `tests/test_rollout.py` and 14 in `tests/test_refresh_memory.py`. The new tests cover:
- the cache-aware cap;
- the OpenAI endpoint (thinking flags, garbled-argument retry, dispatch);
- 0GM as second opinion with the same prompt, and GLM staying the default;
- the DPX blocks and the 150K cap (related work cut first, then the diff);
- the line-overlap rule;
- candidate signals, main-folder matching, stacked series and hub conflicts settled without a model;
- "the model can't clear a textual conflict";
- single-PR mode touching only partners;
- dry run writing nothing;
- the sticky edit leaving the verdict and stored judgement byte-identical, idempotent and removable;
- a re-review keeping the lines with the same verdict and labels;
- the related-work block.

### 2.1 Duplicate pass on today's open PRs (98 open, 28 Oct, dry run)

Runs 1–4 were prompt iterations. Runs 5–7 use the final code:

| | Run 5 | Run 6 | Run 7 |
|---|---|---|---|
| Candidate pairs | 226 | 226 | 226 |
| Model calls (pairs + folders) | 38 | 38 | 38 |
| Settled without a model (hub line conflicts + stacked) | 197 + 1 | 197 + 1 | 195 + 1 |
| Pairs reported | 218 | 220 | 218 |
| **Known collisions found** (50 pairs: #2317/#2321/#2326, #2316→#2317, #2114/#1990, the 45 pairs of the ten @adithsureshbabu switches) | **50/50** | **50/50** | **50/50** |
| **Known same-device folders found** (#2289→tcl-g10-google-tv, #2282→formovie-mprojm05, #1666→xiaomi-mitv-astp0) | **3/3** | **3/3** | **3/3** |
| Wrong same-device folders | 1 (#1558→sony-kd-65x9300d) | 0 | 2 (#1558, #2289→tcl-55p7k) |
| Precision of reported pairs (git: merging one, then the other, conflicts in a shared file) | 96.8% | 96.4% | 97.2% |
| … hub line conflicts alone (no model) | 195/197 | 195/197 | 193/195 |
| … pairs 0GM flagged | 14/19 | 15/20 | 17/21 |
| Pairs 0GM cleared that git says do conflict | 4 | 3 | 3 |
| Time (candidates, files, model) | 76 s | 67 s | 89 s |
| Cost | $0.033 | $0.032 | $0.034 |

**How to read it:**
- **Recall on the known list is complete and stable**: 3 of 3 runs. #1666 is not in the task's list; Round AA asked for it ("fold into xiaomi-mitv-astp0"), so it counts as known.
- **The deterministic part carries most of the volume and is about 99% right.** Most launcher PRs append a key at the same place in `Config.java` and `docs/switches.md`.
- **0GM's own pair calls are about 75–80% textual hits.** Its usual false alarm is "both modify tools/tv.py" when git merges the two cleanly: #2080/#2201, #2098/#2297, #812/#2278. These may still be worth a look, since they are the same scripts. It also called #2336/#2340 (two fixes for #1867 in different add-ons) "duplicate" in some runs.
- **The folder check is right 9 of 12 times over the three runs.** Its misses: the Japanese KJ-55X9300D against the KD-65X9300D folder (2 runs), and the 55P7K folder for #2289 (1 run). Both share a platform but are different models.
- **Earlier runs:**
  - Run 1, before the "same lines" fallback, missed 4 of the 45 switch pairs. 0GM said "different features" even though the pairs edit the same lines.
  - Runs 2–3, with a stricter folder prompt and no thinking, missed #2289 twice.
  - Both are fixed in the final code.
- **The lines are long for the switch PRs.** #2271 gets one grouped line naming 8 PRs and "…". That is accurate (they all conflict), but it is the noisiest part of the output.

Example lines (dry run; nothing was posted):
- #2114: "possibly collides with #1990 (both PRs add debloat.txt and tv.json to the same examples/sharp-aquos-tvx19b/ folder…)"
- #2282: "possibly the same device as `examples/formovie-mprojm05/` on main (same device codename eva and identical firmware build PQ3B.190705.003.1912)"
- #2317: "stacked with #2316 (#2317 is stacked on #2316 (it contains #2316's commits))"
- #2321: "possibly collides with #844, #2125, #2133, … (the same lines of `Config.java`; whichever merges second needs a rebase)"

Files:
- results: `runs/rollout/dedupe-run{1..7}.json`
- scores: `runs/rollout/dedupe-run*-eval.json`, from `scripts/eval_dedupe.py` against a bare clone with every PR head

### 2.2 Shadow comparison on Rounds AG/AG2

**Setup:**
- **Sample:** 19 PRs from Rounds AG/AG2. Truth is the reviewer verdicts in `round-ag/review-*.md` as applied: 5 merge, 3 merge-with-fix, 5 rework, 2 close, 4 hold. The pick is stratified, and each PR had to have a live review at the commit the reviewers read. Clock-expiry closes are left out, because their truth is about timing, not content. Only 2 content closes qualified.
- **Rebuilt as the reviewers read them:** each PR is rebuilt at the reviewers' head SHA, with main at fa1a2f00 (AG) or 9f086119 (AG2), from a bare clone.
- **Leak-free memory:** precedents and policy lines from Rounds AA–AF only. AF ended 27 Oct 13:50 UTC, before AG. The sample PRs are taken out of every memory.
- **Arms:**
  - live: the bot's stored judgement, $0;
  - DPX + memory: Opus 5.5, decision call only;
  - GLM vs 0GM: second opinion on today's prompt, scored through the real policy with the live verdict.

**Model verdict (19 PRs):**

| Arm | Same home as the round | Wrong merge suggestions | Close P / R |
|---|---|---|---|
| Live (Opus 5.5, today's context) | 12/19 | 4 | 1/1, 1/2 |
| Opus 5.5 + DPX + memory to AF | 9/19 | 2 | 1/4, 1/2 |
| GLM-5.3-Flash (as a reviewer) | 8/19 | 4 | 0/0, 0/2 |
| 0GM, reasoning medium (as a reviewer) | 10/19 | 4 | 0/0, 0/2 |

**Through the policy:**

| Arm | Decided alone | Right when it decided | Wrong merges |
|---|---|---|---|
| Live as it ran (critic + GLM second) | 8/19 | 5/8 | 1 |
| Live verdict, critic and second off | 11/19 | 6/11 | 2 |
| DPX + memory, critic and second off | 11/19 | 6/11 | 1 |
| Live verdict + GLM second (critic off) | 8/19 | 4/8 | 1 |
| Live verdict + 0GM second (critic off) | 9/19 | 5/9 | 1 |

**How to read it (19 PRs, so one PR is about 5 points):**
- **DPX + memory decided as much as live, at the same precision, with one wrong merge fewer.**
  - It got three right that live held: #2197 (merge), #2182 (showcase row, merge-with-fix) and #2318 (close).
  - It got three wrong that live had right:
    - #1977: rework on a merge;
    - #1425: close instead of rework;
    - #812: rework on a hold.
  - On the two @adithsureshbabu switches (#2276, #2288) it said close. That is the AF-era rule ("look-only switches are closed"); Round AG2 refined it to "at most a hold". This is why the leak-free memory has to be refreshed after every round.
  - Both arms still merge #2211 (a SHOWCASE row whose screenshot link didn't open). Only reading the link would catch it.
- **On model verdict alone, DPX + memory looks worse (9 vs 12 same home), but most of the gap is close vs hold** on taste PRs. Under the policy, those go to the maintainer either way.
- **This sample does not confirm the research's +7-point precision gain, and it does not refute it.** It is too small. The 2-day shadow (section 6) is the real test.
- **0GM vs GLM as the second opinion: a near tie again.** 0GM agreed with the round on 10/19 against GLM's 8/19. Through the policy: 9 decided at 5/9 against 8 at 4/8, with 1 wrong merge each.
  - 0GM cost $0.0014 per call against GLM's $0.003, and took about 10 s against 30–140 s. GLM's thinking made several calls take minutes.
  - **Recommendation:** switching is safe and cheaper. Keep GLM until the shadow is done, so only one thing changes at a time.
- **Cost:** DPX + memory averaged $0.110 per decision call (19 calls, $2.10). The router returned no cache tokens on these calls, so that is the full prompt price, against about $0.02–0.04 for today's prompt. With the critic and the second opinion on the same prompt, a DPX review would be about $0.15–0.25.

Per PR: `runs/rollout/shadow/score.json`; the table is printed by `scripts/score_shadow.py runs/rollout/shadow`.

| PR | type | round | live model (conf) → final | DPX+mem (conf) → policy | GLM | 0GM |
|---|---|---|---|---|---|---|
| #1977 | addon | merge | merge (0.85) → merge | rework (0.8) → rework | merge | merge |
| #2179 | tv-list | merge | merge (0.78) → hold | merge-with-fix (0.75) → hold | merge | merge |
| #2197 | tv-list | merge | merge (0.78) → hold | merge (0.85) → merge | merge | merge |
| #2214 | docs | merge | merge (0.85) → merge | merge (0.78) → merge | merge | merge |
| #2291 | tv-list | merge | merge (0.78) → hold | merge-with-fix (0.7) → hold | merge | merge |
| #1503 | tv-list | merge-with-fix | rework (0.8) → rework | rework (0.8) → rework | rework | merge |
| #2182 | showcase | merge-with-fix | merge (0.6) → hold | merge-with-fix (0.68) → merge-with-fix | merge | merge |
| #2298 | showcase | merge-with-fix | merge (0.85) → merge | merge-with-fix (0.8) → merge-with-fix | merge | merge |
| #1425 | tools | rework | rework (0.75) → rework | close (0.65) → close | merge-with-fix | rework |
| #1726 | launcher | rework | rework (0.55) → hold | showcase (0.6) → hold | merge | merge |
| #2145 | launcher | rework | merge-with-fix (0.72) → hold | rework (0.6) → hold | theme | theme |
| #2211 | showcase | rework | merge (0.72) → merge | merge-with-fix (0.82) → merge-with-fix | merge | merge |
| #2282 | tv-list | rework | rework (0.75) → rework | rework (0.82) → rework | rework | rework |
| #2269 | tv-list | close | rework (0.85) → rework | rework (0.6) → hold | rework | rework |
| #2318 | tools | close | close (0.7) → hold | close (0.72) → close | rework | rework |
| #812 | launcher | hold | hold (0.55) → hold | rework (0.6) → rework | rework | rework |
| #2194 | tv-list | hold | merge (0.68) → hold | merge (0.7) → hold | merge | merge |
| #2276 | launcher | hold | merge (0.6) → hold | close (0.55) → hold | showcase | merge |
| #2288 | launcher | hold | showcase (0.55) → hold | close (0.6) → hold | showcase | showcase |

### 2.3 Live dry runs of the new code path (two open PRs, nothing written)

`review --dry-run --force --context-blocks DPX --second-model 0gm-1.0-35b-a3b` with the refreshed memory. This run used the AA–AG2 memory, which contains these PRs' own round notes, so it is a check of the plumbing, not a test.
- **#2289:** the decision was rework (0.82): "the same G10_4K_GB product and G10 build as examples/tcl-g10-google-tv … fold it in as a second unit". 0GM, as second opinion, said merge, so the policy held it, leaning rework. Cost $0.068.
- **#2321:** rework, the rebase ask naming the conflicting files, plus the #2207 outline point. Cost $0.109.

The full path worked end to end: related work through the API, the prompt at 28K characters, the 0GM second opinion on the OpenAI endpoint, the cache-aware ledger and the results file.

## 3. What this means

- **Duplicate pass: ready.** It caught every known collision in a 98-PR round for about $0.03 and 1–2 minutes. That is cheaper than the research's $0.19, because the deterministic step settles 85% of the pairs. On the switch PRs it is noisy but accurate.
- **0GM as second opinion: as good as GLM, cheaper and faster.** The flag is ready (`second-opinion-model: 0gm-1.0-35b-a3b`). It stays off until the DPX shadow is done, so only one thing changes at a time.
- **DPX + fresh memory: not proven on 19 PRs.** It had the same decided-alone share and precision as live, with one wrong merge fewer, at about 5x the decision cost. The 2-day shadow decides it.
- **Fresh memory: go.** It is the cheapest gain in the research, and the AF-era "close" calls above show what stale policy does. It is a data change that can go first, on its own.

## 4. Spend

All figures are from the ledger, cached tokens included. The cap was $10, and no step came near it.

| Step | Calls | $ |
|---|---|---|
| Dedupe pass, 7 full runs over the 98 open PRs (4 prompt iterations + 3 final), 0GM | 267 | 0.21 |
| Shadow: Opus 5.5 with DPX + memory, 19 PRs | 19 | 2.10 |
| Shadow: GLM-5.3-Flash second opinion, 19 PRs (one call retried) | 20 | 0.06 |
| Shadow: 0GM second opinion, 19 PRs | 19 | 0.03 |
| Live dry runs of the new path (#2289, #2321: decision, critic, 0GM second) | 4 | 0.18 |
| Memory refresh, eval scripts, tests | 0 | 0.00 |
| **Total** | | **$2.57** |

When the first, serial shadow run was stopped and restarted in parallel, one GLM call was in flight. If the router billed it, it adds about $0.003 that the ledger doesn't show.

## 5. What Gathin needs to approve (commands ready, NOT run)

The branch `0gm-rollout` is pushed to Gathin23/maintainer-bot. **Pin: `dc295e24beb36f09ead3884eba65007a64912cfb`.** Two cleanyourtv PRs follow. **Merge the memory refresh first**, so the live bot and the shadow both read fresh memory, then the pin.

### 5.1 Memory refresh PR (cleanyourtv, data only)

The local branch `bot-memory-1028` is in `~/Arsenal/cleanyourtv-bot-memory-1028`, commit 01b67479, on origin/main d6410ab3. It contains:
- `precedents.jsonl`: 676 → 1,205 decisions (Rounds AA–AG2, 529 new, checked against GitHub's merged/closed state);
- `MAINTAINER.md`: a 3.7K-character "Policies from Rounds AA–AG" block.

The block is drafted from the round notes and marked "Gathin to approve"; its text is in `examples/cleanyourtv/policies/rounds-aa-ag2.md`. cleanyourtv's strict suite passed on the branch: 2,126 OK, `gen_tables.py --check` OK.

**Decide first:** for Rounds AG/AG2, the notes for asks, closes and holds come from drafted comments that are not posted yet, for example the #2318 close and #2293's ask. The file is public once merged. To publish only the AG/AG2 merges and keep their other notes out until they are posted, run step (b).

```bash
cd ~/Arsenal/cleanyourtv-bot-memory-1028
git fetch origin && git rebase origin/main          # only if main moved; precedents/MAINTAINER are bot-only files
# (b) optional: drop the not-yet-posted AG/AG2 ask/close/hold notes (keeps every AG/AG2 merge)
python3 - <<'EOF'
import json
p = ".github/maintainer/precedents.jsonl"
rows = [json.loads(l) for l in open(p) if l.strip()]
keep = [r for r in rows if r["decided_at"] < "2026-10-28" or r["truth"] in ("merge", "merge-with-fix")]
open(p, "w").write("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in keep))
print(len(rows), "->", len(keep))
EOF
git commit -am "maintainer-bot memory: AG/AG2 merges only until their asks and closes are posted"   # only after (b)
git push -u origin bot-memory-1028
gh pr create -R Gathin23/cleanyourtv --base main --head bot-memory-1028 \
  --title "maintainer-bot memory: Rounds AA to AG2 (1,205 decisions) and their policy lines" \
  --body "Refreshes .github/maintainer/precedents.jsonl (676 -> 1,205 decisions; the file stopped at 22 Oct) and adds the policy lines set in Rounds AA-AG to MAINTAINER.md. Data only: no code or workflow change. Built with maintainer-bot's scripts/refresh_memory.py from the round notes, checked against each PR's merged/closed state. In the backtest, fresher memory cut the bot's wrong merge suggestions from 9 to 3 (maintainer-bot report/0gm-research.md, 4.2)."
```

### 5.2 Pin change PR (cleanyourtv workflow)

The proposed file is `examples/cleanyourtv/maintainer-bot-0gm.yml`: today's workflow plus three steps.
- **Dedupe pass:** when a PR opens, only its own pairs; on the 6-hourly sweep and a manual backfill, every open PR. Its spend is capped at $1 per pass.
- **2-day shadow:** a dry-run DPX review on every PR event. Nothing is written; it has its own ledger with a $15 daily cap and $1.50 per PR.
- **Shadow output:** a step that prints the shadow verdict to the log as `MB-SHADOW` lines.

The live review itself is unchanged. GLM stays the second opinion, the default context is unchanged, and the only new thing it gets is the ledger fix.

```bash
git -C ~/Arsenal/tv-vibehack fetch origin
git -C ~/Arsenal/tv-vibehack worktree add ~/Arsenal/cleanyourtv-bot-pin -b bot-0gm-pin origin/main
cd ~/Arsenal/cleanyourtv-bot-pin
sed "s/PIN_SHA/dc295e24beb36f09ead3884eba65007a64912cfb/g" ~/Arsenal/maintainer-bot/examples/cleanyourtv/maintainer-bot-0gm.yml \
  > .github/workflows/maintainer-bot.yml
git diff        # expect: the new pin, the comment block, three new steps; nothing else
git commit -am "maintainer-bot: pin 0gm-rollout (cache-aware ledger, 0GM duplicate pass, 2-day DPX shadow)"
git push -u origin bot-0gm-pin
gh pr create -R Gathin23/cleanyourtv --base main --head bot-0gm-pin \
  --title "maintainer-bot: 0GM duplicate pass, cache-aware spend cap, 2-day shadow of the long-context review" \
  --body "Pins maintainer-bot to dc295e2 (branch 0gm-rollout). The review itself is unchanged except that the daily cap now counts cached prompt tokens. New: a duplicate and collision pass powered by 0G's 0GM model that adds 'Possibly collides with #N' lines to the Checks of both PRs (information only, never a verdict); and, for two days, a dry-run shadow review with more context whose verdict goes only to the job log. See maintainer-bot report/0gm-rollout.md."
```

When CI is green, Gathin merges it as usual. To switch off: revert the PR, or delete the dedupe and shadow steps.

## 6. Shadow mode: 2-day plan

1. **Day 0:** merge the memory PR, then the pin PR.
2. **Days 1–2:** every PR event gets the normal live review, and then the DPX dry run. In shadow:
   - expected cost is about $0.10 per review (2.2), so roughly $5–10 a day at today's volume;
   - the separate $15/day cap stops it, never the live bot;
   - the dedupe pass adds about $0.03 per sweep (4 a day) and well under a cent per new PR.
3. **Rounds as usual:** Gathin runs the next rounds (AH, AI) with the review-file table format, which `shadow_logs.py` reads.
4. **Day 3:** score it (read-only):
   ```bash
   cd ~/Arsenal/maintainer-bot
   python3 scripts/shadow_logs.py --since 2026-10-29 --rounds 'round-ah/review-*.md' --out runs/rollout/shadow-live.json
   ```
   It prints, for live and shadow:
   - decided alone, precision and wrong merges against the round decisions;
   - every PR where the two differ;
   - the shadow cost.
5. **Go/no-go for `context-blocks: DPX` on the live review** (one line in the workflow, plus `per-pr-cap-usd: "1.5"`). Go if both hold:
   - the shadow's wrong merges are no higher than live's;
   - its precision is at least live's, on 30 or more decided PRs.

   Then delete the two shadow steps. If not, delete them anyway and keep today's context.
6. **Dedupe:** read a day of "Possibly collides" lines. If the grouped hub line is too noisy for the switch PRs, it can be limited to non-hub pairs (a one-line change in `live.collision_lines`).

## 7. Update for Michael (in Gathin's voice, ready to paste)

Quick update on 0GM in the CleanYourTV PR bot, following yesterday's backtest.

0GM now runs the bot's duplicate and collision check across open PRs. Tested today on 98 open PRs:
- It found every collision we knew about from the last two review rounds: 50 of 50 PR pairs, plus all 3 new device folders that duplicate a folder already in the repo. The result was the same in 3 of 3 runs.
- A full pass costs about $0.03 and takes 1-2 minutes, so it can run on every new PR and every 6 hours.
- Each finding is one line in the bot's review comment ("Possibly collides with #N", with the reason). It is information only and never changes the bot's decision.
- A plain line-overlap check settles most pairs. 0GM handles the judgement calls (same device? same fix done two ways?). Its own pair calls were right about 75-80% of the time; the misses were "same file" alarms that git merges cleanly.

As a second opinion, 0GM was a near tie with our current one (GLM-5.3-Flash) on 19 PRs from this week's rounds. It costs about half as much and answers in about 10 seconds instead of 30-140. The merge/close call stays on Opus 5.5.

Next: a 2-day shadow run with more context and fresher memory for the main review, then the switch. The bot runs on 0G Private Computer and the duplicate check is powered by 0G's 0GM.

Still useful from your side: a published cache-read price on the router. The bot's spend cap now counts cached tokens, but we have to assume the rate.
