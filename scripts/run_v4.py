import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""v4 backtest runs on today's decisions (data/cleanyourtv-v4). Usage:

    run_v4.py probe 789 806 525      a few PRs, printed in full (to check the prompt before spending more)
    run_v4.py train                  every train PR (decided before 21 Oct 23:30 UTC)
    run_v4.py test                   every test PR (22 Oct), run once with the policy fixed on train

All spend goes to runs/ledger-v4.jsonl with a hard cap of $15.
"""
import json

from maintainer_bot import ledger, v4

GIT = os.environ["MB_GIT_DIR"]
CAP = 15.0
MODEL, CRITIC, SECOND = "claude-opus-5.5", "claude-sonnet-5", "glm-5.3-flash"
RULES = open("examples/cleanyourtv/MAINTAINER.md", encoding="utf-8").read()

rows, snaps, index = v4.load("data/cleanyourtv-v4", GIT, "data/cleanyourtv")
L = ledger.Ledger("runs/ledger-v4.jsonl", CAP)
mode = sys.argv[1]
before = L.spent
if mode == "probe":
    pick = [r for r in rows if r["pr"] in {int(x) for x in sys.argv[2:]}]
    res = v4.run(pick, snaps, index, run_dir="runs/v4-probe", rules_md=RULES, model=MODEL, critic_model=CRITIC,
                 second_model=SECOND, ledger=L, workers=4)
    by = {r["pr"]: r for r in rows}
    for e in res:
        print(json.dumps({k: e.get(k) for k in ("pr", "verdict", "confidence", "reasons", "fix", "specific",
                                                 "comment", "critic", "second")}, indent=1, ensure_ascii=False))
        print("truth:", by[e["pr"]]["truth"], "final:", v4.final(e, by[e["pr"]]["facts"]))
else:
    pick = [r for r in rows if r["split"] == mode]
    print(mode, len(pick), "PRs; spent so far", round(L.spent, 2))
    res = v4.run(pick, snaps, index, run_dir=f"runs/v4-{mode}", rules_md=RULES, model=MODEL, critic_model=CRITIC,
                 second_model=SECOND, ledger=L, workers=8)
    m = v4.evaluate(res, {r["pr"]: r for r in rows})
    print(json.dumps({k: v for k, v in m.items() if k != "rows"}, indent=1))
print("this run", round(L.spent - before, 3), "total", round(L.spent, 3))
