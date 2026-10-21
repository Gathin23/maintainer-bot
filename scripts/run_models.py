import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""Backtest runs: glm-5.3-flash on everything, glm-5.3 and claude-opus-5.5 on one fixed stratified sample."""
import sys
from maintainer_bot import backtest, ledger
rows = backtest.prepare('data/cleanyourtv', os.environ.get('MB_GIT_DIR', '../cleanyourtv'))
L = ledger.Ledger('runs/ledger.jsonl', 25.0)
rules = open('examples/cleanyourtv/MAINTAINER.md').read()
sample = backtest.stratified_sample(rows, 120)
which = sys.argv[1]
if which == 'flash':
    res = backtest.run(sample, data_dir='data/cleanyourtv', run_dir='runs/glm-5.3-flash', model='glm-5.3-flash', rules_md=rules, ledger=L, workers=28)
elif which == 'glm':
    res = backtest.run(sample, data_dir='data/cleanyourtv', run_dir='runs/glm-5.3', model='glm-5.3', rules_md=rules, ledger=L, workers=12)
elif which == 'opus':
    res = backtest.run(sample[:100], data_dir='data/cleanyourtv', run_dir='runs/claude-opus-5.5', model='claude-opus-5.5', rules_md=rules, ledger=L, workers=6)
m = backtest.metrics(res)
print(which, {k: v for k, v in m.items() if k not in ('safety_misses', 'confusion', 'per_class')}, 'spent', round(L.spent, 2))
