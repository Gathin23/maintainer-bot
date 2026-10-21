import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""Live dry-run of the v3 policy on open PRs (no GitHub writes).

Usage: run_live.py <scope.json> <run dir>

scope.json is a list of {"pr": n, ...}. Every past decision is available as precedent (they were all made
before now). Facts and batch context are computed against origin/main as it is today and the other open PRs
in scope. Output: <run dir>/results.jsonl (raw model output) and <run dir>/bot.json (final policy verdicts).
"""
import json
import re
import subprocess
from datetime import datetime, timezone

from maintainer_bot import batch, checklists, dataset, facts as facts_mod, ledger, memory, v3

GIT = '/Users/gathin/.superset/worktrees/tv-vibehack/caramel-awe-67357739'
REPO = 'Gathin23/cleanyourtv'
CAP = 56.0
MODEL, CRITIC, SECOND = 'claude-opus-5.5', 'claude-opus-5.5', 'glm-5.3-flash'
THRESHOLD = 0.65

scope_path, run_dir = sys.argv[1], sys.argv[2]
os.makedirs(run_dir, exist_ok=True)
scope = json.load(open(scope_path))

hist, ctx = v3.load('data/cleanyourtv', GIT)
now = datetime.now(timezone.utc).isoformat()
main = subprocess.run(['git', '-C', GIT, 'rev-parse', 'origin/main'], capture_output=True, text=True).stdout.strip()
folders = dataset.list_folders_at_commit(GIT, main)
locales = dataset.locale_count_at_commit(GIT, main)

live = []
for s in scope:
    n = s['pr']
    p = dataset.gh_json(['pr', 'view', str(n), '-R', REPO, '--json', 'number,title,author,createdAt,body'])
    head = f'refs/pr/{n}'
    base = subprocess.run(['git', '-C', GIT, 'merge-base', 'origin/main', head], capture_output=True,
                          text=True).stdout.strip()
    files = dataset.pr_files_from_git(GIT, base, head)
    snap = {'pr': n, 'title': p['title'], 'author': p['author']['login'], 'created_at': p['createdAt'],
            'body': (p.get('body') or '')[:4000], 'files': files}
    live.append({'pr': n, 'title': p['title'], 'author': p['author']['login'], 'created_at': p['createdAt'],
                 'decided_at': now, 'truth': None, 'family': '?', 'split': 'live', 'fix': '', 'maintainer_note': '',
                 'batch_dependent': False, '_snap': snap})

pr_folders = {r['pr']: sorted({m.group(1) for f in r['_snap']['files']
                               if (m := re.match(r'^examples/([^/]+)/', f['path']))}) for r in live}
for r in live:
    snap = r.pop('_snap')
    others = {}
    for o in live:
        if o['pr'] != r['pr'] and len(pr_folders[o['pr']]) <= 3:
            for fo in pr_folders[o['pr']]:
                others.setdefault(fo, []).append(o['pr'])
    fx = facts_mod.compute(snap, existing_list_folders=folders, other_open_list_folders=others,
                           locale_count=locales)
    tw = memory._words(r['title'])
    fx['similar_titles_open_at_the_time'] = [o['pr'] for o in live if o['pr'] != r['pr'] and tw and
                                             len(tw & memory._words(o['title'])) / max(1, len(tw | memory._words(o['title']))) >= 0.5][:5]
    r['facts'] = fx
    r['top_dirs'] = fx['top_dirs']
    r['type'] = checklists.pr_type([f['path'] for f in snap['files']], r['title'])
    ctx['snaps'][r['pr']] = snap
    ctx['files'][r['pr']] = [f['path'] for f in snap['files']]
    ctx['titles'][r['pr']] = r['title']
    ctx['bodies'][r['pr']] = snap['body']

# precedent index over past decisions plus the live PRs (live PRs are never returned: decided_at == now)
from maintainer_bot import retrieval
ctx['index'] = retrieval.Index(hist + live, ctx['files'], ctx['bodies'])
open_rows = [{**o, 'decided_at': '9999'} for o in live]
for r in live:
    out = {}
    ov = batch.open_overlaps({**r, 'decided_at': now}, open_rows, ctx['files'], ctx['titles'])
    if ov:
        out['other_open_prs_touching_the_same_files'] = ov
    aom = batch.already_on_main(ctx['snaps'][r['pr']]['files'], GIT, main)
    if aom:
        out['already_on_main'] = aom
    r['batch'] = out

rules = open('examples/cleanyourtv/MAINTAINER.md').read()
L = ledger.Ledger('runs/ledger.jsonl', CAP)
print('live', len(live), 'PRs; spent so far', round(L.spent, 2))
res = v3.run(live, ctx, run_dir=run_dir, rules_md=rules, model=MODEL, critic_model=CRITIC, second_model=SECOND,
             ledger=L, workers=8)
by = {r['pr']: r for r in live}
bot = []
for e in res:
    v, why = v3.final(e, by[e['pr']]['facts'], threshold=THRESHOLD, use_critic=True, use_second=True)
    bot.append({'pr': e['pr'], 'type': e['type'], 'model_verdict': e['verdict'], 'confidence': e['confidence'],
                'verdict': v if v != 'hold' else 'hold', 'decided_alone': v != 'hold',
                'escalation_reason': why, 'fix': e.get('fix', ''), 'reason': '; '.join(e.get('reasons') or []),
                'critic': e.get('critic'), 'second': e.get('second'), 'precedent': e.get('precedent', '')})
json.dump(sorted(bot, key=lambda b: b['pr']), open(os.path.join(run_dir, 'bot.json'), 'w'), indent=1)
print('done', len(bot), 'of', len(live), '; spent', round(L.spent, 2))
