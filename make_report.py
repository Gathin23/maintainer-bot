"""Assemble report/backtest.md from the saved runs (no model calls)."""
import json, os, collections
from maintainer_bot import backtest, report, ledger, queue, commands, apply
rows = backtest.prepare('data/cleanyourtv', '/x')
truth = collections.Counter(r['truth'] for r in rows)
L = ledger.Ledger('runs/ledger.jsonl', 25.0)
spend = L.summary()

def run_spend(model, tags):
    tot = 0.0
    for line in open('runs/ledger.jsonl'):
        e = json.loads(line)
        if e['model'] == model and any(e.get('tag', '').startswith(t) for t in tags):
            tot += e['usd']
    return tot

out = ["# maintainer-bot backtest on Gathin23/cleanyourtv", "",
       f"Generated locally, nothing posted to GitHub. All model calls went through the 0G Private Computer router.", "",
       "## Dataset", "",
       f"- **{len(rows)} decided community PRs** (the maintainer's own PRs excluded), replayed in the order they were decided.",
       f"- Truth = what actually happened: " + ", ".join(f"{k} {v}" for k, v in truth.most_common()) + ".",
       "  merge-with-fix = merged with an 'On merge: …' note in the merge commit; rework / hold = the open PR's current label.",
       "- Snapshot = the PR as merged (merge commit's second parent) or its last commit before the decision. Commit dates are author-set, so a few reworked PRs may show a later push.",
       "- Memory = up to 8 similar PRs decided **earlier** (never the PR itself, never later decisions), with the maintainer's merge note or comment as the reason.",
       "- Stratified sample of 120 for model comparison (Claude Opus 5.5 ran on the first 100 of it); Round L = PRs #543+ (decided today).", ""]

out += ["## Headline (rules v2)", ""]
sections = []
per_call = {k: v['usd'] / v['calls'] for k, v in spend.items() if v['calls']}
for name, label in (('claude-opus-5.5', 'Claude Opus 5.5 · 100-PR sample'), ('glm-5.3', 'GLM-5.3 (TEE-sealed) · 120-PR sample'),
                    ('glm-5.3-flash', 'GLM-5.3-flash · 120-PR sample'), ('roundL-opus', 'Claude Opus 5.5 · Round L (today, PRs #543+)')):
    rs = report.load_results(f'runs/{name}/results.jsonl')
    if not any('verdict' in r for r in rs):
        continue
    model = 'claude-opus-5.5' if 'opus' in name else name
    n = sum(1 for r in rs if 'verdict' in r)
    sections.append(report.section(label, rs, n * per_call.get(model, 0)))
for name, label in (('claude-opus-5.5', 'v1 rules, Claude Opus 5.5 · same sample'),):
    rs = report.load_results(f'runs/v1/{name}/results.jsonl')
    if rs:
        sections.append(report.section(label, rs, 0.0).replace('- Spend: $0.00 total, $0.000 per PR', '- (v1 run, before tuning)'))
out += sections

# queue from Round L
rl = {r['pr']: r for r in report.load_results('runs/roundL-opus/results.jsonl') if 'verdict' in r}
out += ["## What the daily queue looks like (Round L, rendered from the bot's own decisions)", "", "<details><summary>Queue issue</summary>", "",
        queue.render(list(rl.values()), model='claude-opus-5.5', day='2026-10-21'), "", "</details>", ""]
appr = commands.parse('/approve except #543\nhold 608')
sel = appr.selected({k: v['verdict'] for k, v in rl.items()}) if appr else {}
acts = apply.plan(sel, rl)
out += ["## Dry-run of `/approve except #543` + `hold 608` on that queue", "",
        f"{len(sel)} PRs selected, {len(acts)} actions (nothing sent):", "", "```", apply.dry_run(acts)[:6000], "```", ""]

# fix dry-run
if os.path.exists('runs/fix-dryrun.json'):
    out += ["## Merge-with-fix, job A dry-run (Claude Opus 5.5 on 0G PC)", "",
            "| PR | maintainer's actual note | bot's fix | proposed edit | validator |", "|---|---|---|---|---|"]
    for e in json.load(open('runs/fix-dryrun.json')):
        ed = e['edits'][0] if e['edits'] else None
        edit = f"{ed['path']}: …{ed['replace'][:70]}…" if ed else "no edit (needs a rebase: escalate)"
        out.append(f"| #{e['pr']} | {e['maintainer_note'][:110].replace('|','/')} | {e['bot_fix'][:110].replace('|','/')} | {edit.replace('|','/').replace(chr(10),' ')} | {'ok' if not e['problems'] else '; '.join(e['problems']).replace('|','/')} |")
    out.append("")

tot = sum(v['usd'] for v in spend.values())
out += ["## Spend", "", "| model | calls | input tokens | output tokens | $ |", "|---|---|---|---|---|"]
for k, v in spend.items():
    out.append(f"| {k} | {v['calls']} | {v['in']:,} | {v['out']:,} | {v['usd']:.2f} |")
out += [f"| **total** | | | | **{tot:.2f}** (cap $25) |", ""]
open('report/backtest.md', 'w').write("\n".join(out))
print('written', round(tot, 2))
