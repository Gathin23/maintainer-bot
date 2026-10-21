from maintainer_bot import backtest, ledger
rows = backtest.prepare('data/cleanyourtv', '/Users/gathin/.superset/worktrees/tv-vibehack/caramel-awe-67357739')
L = ledger.Ledger('runs/ledger.jsonl', 25.0)
rules = open('examples/cleanyourtv/MAINTAINER.md').read()
res = backtest.run(rows, data_dir='data/cleanyourtv', run_dir='runs/glm-5.3', model='glm-5.3', rules_md=rules, ledger=L, workers=20)
m = backtest.metrics(res)
print({k: v for k, v in m.items() if k not in ('safety_misses', 'confusion', 'per_class')}, 'spent', round(L.spent, 2))
