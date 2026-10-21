import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""Rule mining: one model call over the TRAIN disagreements → candidate rules for MAINTAINER.md.

Usage: mine_rules.py <run dir> <rules file> <out json>
Only train-split PRs are used, so the test split stays untouched.
"""
import json
from maintainer_bot import ledger, v3
from maintainer_bot.router import call_tool

GIT = '/Users/gathin/.superset/worktrees/tv-vibehack/caramel-awe-67357739'
run_dir, rules_path, out_path = sys.argv[1:4]
rows, ctx = v3.load('data/cleanyourtv', GIT)
by = {r['pr']: r for r in rows}
res = [json.loads(l) for l in open(os.path.join(run_dir, 'results.jsonl')) if l.strip()]
res = [r for r in res if 'error' not in r and by[r['pr']]['split'] == 'train']
dis = [r for r in res if v3.family(r['verdict']) != r['family']]
print(len(res), 'judged;', len(dis), 'disagreements')
lines = []
for r in dis:
    row = by[r['pr']]
    note = (row.get('maintainer_note') or row.get('fix') or '').replace('\n', ' ')[:400]
    lines.append(f"- #{r['pr']} [{row['type']}] {row['title'][:100]}\n  maintainer: {row['truth']} — {note or '(no note)'}\n"
                 f"  bot: {r['verdict']} (conf {r['confidence']:.2f}) — {'; '.join(r['reasons'])[:300]}\n"
                 f"  facts: {json.dumps({k: v for k, v in row['facts'].items() if v not in ([], {}, 0, False, None) and k in ('duplicate_of_merged_folder', 'competing_open_prs', 'similar_titles_open_at_the_time', 'sensitive_paths', 'size', 'locales_with_strings', 'new_launcher_strings')})}"
                 f" batch: {json.dumps(row['batch'])[:300]}")
TOOL = {"name": "propose_rules", "description": "Propose new or corrected review rules.",
        "input_schema": {"type": "object", "properties": {"rules": {"type": "array", "items": {"type": "object", "properties": {
            "rule": {"type": "string", "description": "one rule, written for MAINTAINER.md, general (no PR numbers)"},
            "why": {"type": "string"}, "evidence_prs": {"type": "array", "items": {"type": "integer"}},
            "general": {"type": "boolean", "description": "true if it would apply to future PRs, false if it only explains these cases"}},
            "required": ["rule", "why", "evidence_prs", "general"]}}}, "required": ["rules"]}}
user = f"""Below are the current review rules of an open-source repo and the cases where a bot's decision disagreed
with the human maintainer. Find the patterns in what the maintainer did that the rules don't capture (or capture
wrongly), and propose at most 10 short, general rules that would make the bot decide like the maintainer.
Do not propose rules that only fit one PR. Do not loosen safety rules.

## Current rules
{open(rules_path).read()}

## Disagreements
{chr(10).join(lines)}
"""
L = ledger.Ledger('runs/ledger.jsonl', 41.0)
out = call_tool(model='claude-opus-5.5', system='You improve code-review rules from evidence. Call propose_rules once.',
                user=user, tool=TOOL, ledger=L, max_tokens=6000, tag='v3-mine')
json.dump({"disagreements": len(dis), "judged": len(res), **out}, open(out_path, 'w'), indent=1)
for r in out.get('rules', []):
    print(('GENERAL ' if r.get('general') else 'specific') + ' | ' + r['rule'] + ' | ' + str(r.get('evidence_prs')))
print('spent', round(L.spent, 2))
