import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""Job A dry-run: propose edits for past merge-with-fix PRs and compare with what the maintainer changed on merge."""
import json, subprocess
from maintainer_bot import backtest, dataset, fix, ledger
G = '/Users/gathin/.superset/worktrees/tv-vibehack/caramel-awe-67357739'
rows = {r['pr']: r for r in backtest.prepare('data/cleanyourtv', G)}
L = ledger.Ledger('runs/ledger.jsonl', 25.0)
bot = {json.loads(l)['pr']: json.loads(l) for l in open('runs/claude-opus-5.5/results.jsonl') if '"verdict"' in l}
picks = [399, 392]
out = []
for n in picks:
    r = rows[n]; snap = dataset.load_snapshot('data/cleanyourtv', n)
    head = f"{r['merge_sha']}^2"
    fix_text = bot[n].get('fix', '')
    ctx = {}
    for p in ('README.md', 'launcher/app/src/main/res/xml/locales_config.xml', 'examples/README.md'):
        if any(w in fix_text for w in (p.split('/')[-1], 'README', 'locale')):
            t = fix.file_at(G, head, p)
            if t:
                needles = [w for w in __import__('re').findall(r'[a-z0-9]+-[a-z0-9-]+|[A-Z][a-z]+', fix_text)][:8]
                ctx[p] = fix.excerpt(t, needles)
    try:
        prop = fix.propose(pr=snap, fix_text=fix_text, diff=dataset.trim_diff(snap['files']), context_files=ctx,
                           model='claude-opus-5.5', ledger=L, tag=f'fix:{n}')
        problems = fix.validate(prop.get('edits', []), G, head)
    except Exception as e:
        prop, problems = {'edits': [], 'summary': f'error: {e}'}, ['call failed']
    actual = subprocess.run(['git', 'diff', '--stat', f'{head}', r['merge_sha']], cwd=G, capture_output=True, text=True).stdout.strip().splitlines()[-1:]
    out.append({'pr': n, 'bot_fix': fix_text, 'maintainer_note': r.get('fix', '')[:300], 'edits': prop.get('edits', []),
                'summary': prop.get('summary', ''), 'problems': problems})
    print(n, 'edits', len(prop.get('edits', [])), 'problems', problems)
prev = {e['pr']: e for e in json.load(open('runs/fix-dryrun.json'))}
prev.update({e['pr']: e for e in out})
json.dump(list(prev.values()), open('runs/fix-dryrun.json', 'w'), indent=1)
