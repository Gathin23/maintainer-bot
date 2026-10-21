import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""v3 runs. Usage: run_v3.py dev <rules file> <run dir> | test <rules file> <run dir> | probe <n>

dev: a fixed stratified 90-PR sample of the TRAIN split (rounds before 21 Oct) for tuning.
test: every PR in the TEST split (21 Oct: rounds K and L), run once with the final rules.
"""
import json
from maintainer_bot import backtest, ledger, v3

GIT = os.environ.get('MB_GIT_DIR', '../cleanyourtv')
CAP = 41.0
MODEL, CRITIC, SECOND = 'claude-opus-5.5', 'claude-opus-5.5', 'glm-5.3-flash'

mode = sys.argv[1]
rows, ctx = v3.load('data/cleanyourtv', GIT)
L = ledger.Ledger('runs/ledger.jsonl', CAP)
by = {r['pr']: r for r in rows}
if mode == 'probe':
    n = int(sys.argv[2])
    pick = [r for r in rows if r['split'] == 'train' and r['family'] != 'accept'][:n]
    before = L.spent
    res = v3.run(pick, ctx, run_dir='runs/v3-probe', rules_md=open('examples/cleanyourtv/MAINTAINER.md').read(),
                 model=MODEL, critic_model=CRITIC, second_model=SECOND, ledger=L, workers=4)
    print(json.dumps(res, indent=1)[:3000]); print('cost', round(L.spent - before, 4))
    sys.exit()
rules = open(sys.argv[2]).read()
run_dir = sys.argv[3]
if mode == 'dev':
    train = [r for r in rows if r['split'] == 'train']
    pick = backtest.stratified_sample([{**r, 'truth': r['family']} for r in train], 90)
    pick = [by[p['pr']] for p in pick]
else:
    pick = [r for r in rows if r['split'] == 'test']
print(mode, len(pick), 'PRs; spent so far', round(L.spent, 2))
v3.run(pick, ctx, run_dir=run_dir, rules_md=rules, model=MODEL, critic_model=CRITIC, second_model=None,
       ledger=L, workers=8)
print('second opinions:', v3.add_second(pick, ctx, run_dir=run_dir, rules_md=rules, model=SECOND, ledger=L))
res = v3.run(pick, ctx, run_dir=run_dir, rules_md=rules, model=MODEL, critic_model=CRITIC, second_model=None,
             ledger=L, workers=8)  # reload (no new calls unless something failed)
print('raw', {k: v for k, v in v3.model_only(res).items() if k != 'confusion'})
for row in v3.curve(res, by):
    print(row)
print('spent', round(L.spent, 2))
