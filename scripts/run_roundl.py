import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""Round L (PRs #543+) through Claude Opus 5.5 on 0G PC, to render a real queue and dry-run /approve."""
from maintainer_bot import backtest, ledger
rows = backtest.prepare('data/cleanyourtv', '/Users/gathin/.superset/worktrees/tv-vibehack/caramel-awe-67357739')
L = ledger.Ledger('runs/ledger.jsonl', 25.0)
rules = open('examples/cleanyourtv/MAINTAINER.md').read()
rl = [r for r in rows if r['pr'] >= 543]
print(len(rl), 'round L PRs')
res = backtest.run(rl, data_dir='data/cleanyourtv', run_dir='runs/roundL-opus', model='claude-opus-5.5', rules_md=rules, ledger=L, workers=6)
print(backtest.metrics(res)['exact_agreement'])
