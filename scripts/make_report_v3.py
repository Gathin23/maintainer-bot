import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""Write report/v3.md from the v3 dev and test runs (no model calls)."""
import json
from collections import Counter
from maintainer_bot import ledger, v3

GIT = os.environ.get('MB_GIT_DIR', '../cleanyourtv')
rows, ctx = v3.load('data/cleanyourtv', GIT)
by = {r['pr']: r for r in rows}


def load(run):
    out = {}
    p = f'runs/{run}/results.jsonl'
    if os.path.exists(p):
        for line in open(p):
            if line.strip():
                e = json.loads(line)
                if 'error' not in e and 'verdict' in e:
                    out[e['pr']] = e
    return list(out.values())


dev1, dev2, test = load('v3-dev1'), load('v3-dev2'), load('v3-test')

# ---- choose the policy on DEV (train split) only ----
# robust choice: the highest-coverage threshold that is >=95% precise with zero wrong merges on BOTH dev runs
grid = (0.0, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85)
c1 = {c['threshold']: c for c in v3.curve(dev1, by, thresholds=grid) if c['critic'] and c['second']}
c2 = {c['threshold']: c for c in v3.curve(dev2, by, thresholds=grid) if c['critic'] and c['second']}
good = [t for t in grid if all(c[t]['wrong_merges'] == 0 and (c[t]['precision'] or 0) >= 0.95 for c in (c1, c2))]
t_best = max(good, key=lambda t: c2[t]['coverage']) if good else 0.8
choice = c2[t_best]
POLICY = dict(threshold=choice['threshold'], use_critic=True, use_second=True, existing_list_edits=True)

# ---- v2 baseline on the same test PRs ----
v2 = {}
for run in ('claude-opus-5.5', 'roundL-opus'):
    for line in open(f'runs/{run}/results.jsonl'):
        e = json.loads(line)
        if 'verdict' in e and by.get(e['pr'], {}).get('split') == 'test':
            v2[e['pr']] = e
common = [r for r in test if r['pr'] in v2]


def stats_v2(prs):
    n = len(prs)
    fam = sum(1 for p in prs if v3.family(v2[p]['verdict']) == by[p]['family'])
    dec = [p for p in prs if v3.family(v2[p]['verdict']) != 'escalate']
    agree_dec = sum(1 for p in dec if v3.family(v2[p]['verdict']) == by[p]['family'])
    wm = [p for p in prs if v2[p]['verdict'] in v3.ACCEPT and by[p]['family'] != 'accept']
    return n, fam / n, len(dec) / n, agree_dec / len(dec) if dec else 0, wm


def stats_v3(res, policy):
    m = v3.evaluate(res, by, **policy)
    return m


L = ledger.Ledger('runs/ledger.jsonl', 41.0)
spend = Counter()
for line in open('runs/ledger.jsonl'):
    e = json.loads(line)
    t = e['tag'].split(':')[0]
    spend['v3' if t.startswith('v3') else 'before v3'] += e['usd']

out = []
w = out.append
w('# maintainer-bot v3: accuracy sprint report')
w('')
w('Generated locally, 21 Oct 2026. Nothing posted to GitHub. All model calls went through the 0G Private Computer router.')
w(f'Decision model: Claude Opus 5.5 (critic: Claude Opus 5.5, second opinion: GLM-5.3-flash). Spend so far: ${L.spent:.2f} of the $41 cap '
  f'(${spend["v3"]:.2f} in this sprint).')
w('')
w('## How it was tested (honest split)')
tr = [r for r in rows if r['split'] == 'train']
te = [r for r in rows if r['split'] == 'test']
w(f'- **Train** = rounds decided before 21 Oct ({len(tr)} PRs). Rules were tuned only here, on a fixed stratified sample of {len(dev2)} PRs.')
w(f'- **Test** = rounds K and L (21 Oct, {len(te)} PRs). Run **once** with the final rules and the policy chosen on train. No changes after looking at it.')
w('- Classes: **accept** (merge or merge-with-fix; "fix needed" tracked separately), **rework**, **close**, **escalate** (hold / needs the maintainer).')
w(f'- Batch-dependent cases (duplicates, overlaps, superseded): {sum(r["batch_dependent"] for r in tr)} in train, {sum(r["batch_dependent"] for r in te)} in test.')
w('')
w(f'Test split by class: {dict(Counter(r["family"] for r in te))}; by type: {dict(Counter(r["type"] for r in te))}.')
w('')
w('## Policy chosen on train')
w(f'- Escalate when: the PR type is launcher or workflow (always the maintainer), the model asks for the maintainer, '
  f'confidence < **{POLICY["threshold"]}**, the PR edits a TV list already on main, the critic finds a rule-backed blocker to a merge, or the cheap second '
  f'opinion disagrees on the class. Deterministic overrides (binaries, sensitive paths, protected packages, INTERNET, '
  f'strings missing in most locales, an existing list folder) always win.')
w(f'- On train (dev2) this gave precision {choice["precision"]} at coverage {choice["coverage"]} with {choice["wrong_merges"]} wrong merges.')
w('')

if test:
    mt = stats_v3(test, POLICY)
    raw = v3.model_only(test)
    w('## Results on the test split (rounds K–L)')
    w('')
    w('| | PRs | Agrees with Gathin (all) | Bot decides alone | Correct when it decides | Wrong merges |')
    w('|---|---|---|---|---|---|')
    if common:
        n, fam, cov, prec, wm = stats_v2([r['pr'] for r in common])
        w(f'| v2 (Opus, rules v2), same PRs | {n} | {fam:.0%} | {cov:.0%} | {prec:.0%} | {len(wm)} |')
        mc = stats_v3(common, POLICY)
        rawc = v3.model_only(common)
        w(f'| v3 raw model (no abstention), same PRs | {n} | {rawc["family_agreement"]:.0%} | — | {rawc["agreement_when_decides"]:.0%} | {rawc["wrong_merges"]} |')
        w(f'| **v3 with policy, same PRs** | {n} | {mc["family_agreement_overall"]:.0%} | {mc["coverage"]:.0%} | '
          f'**{(mc["precision_when_bot_decides"] or 0):.0%}** | **{len(mc["wrong_merges"])}** |')
    w(f'| v3 raw model, all test PRs | {raw["n"]} | {raw["family_agreement"]:.0%} | — | {raw["agreement_when_decides"]:.0%} | {raw["wrong_merges"]} |')
    w(f'| **v3 with policy, all test PRs** | {mt["n"]} | {mt["family_agreement_overall"]:.0%} | {mt["coverage"]:.0%} | '
      f'**{(mt["precision_when_bot_decides"] or 0):.0%}** | **{len(mt["wrong_merges"])}** |')
    w('')
    nb = [r for r in test if not r['batch_dependent']]
    mnb = stats_v3(nb, POLICY)
    w(f'Without batch-dependent cases ({len(nb)} PRs): correct when it decides {(mnb["precision_when_bot_decides"] or 0):.0%}, '
      f'coverage {mnb["coverage"]:.0%}, wrong merges {len(mnb["wrong_merges"])}.')
    w('')
    w('### What it would have done alone, by PR type (test)')
    ct = Counter((x['type'], v3.family(x['final'])) for x in mt['rows'])
    types = sorted({x['type'] for x in mt['rows']})
    w('| Type | Decided alone | Escalated | Correct when decided |')
    w('|---|---|---|---|')
    for t in types:
        rr = [x for x in mt['rows'] if x['type'] == t]
        d = [x for x in rr if v3.family(x['final']) != 'escalate']
        c = sum(1 for x in d if v3.family(x['final']) == x['family'])
        w(f'| {t} | {len(d)} | {len(rr) - len(d)} | {f"{c}/{len(d)}" if d else "—"} |')
    w('')
    w('### Precision vs coverage on test (for reference; the policy above was fixed on train)')
    w('| Threshold | Critic | Second opinion | Coverage | Precision | Wrong merges | Wrong closes |')
    w('|---|---|---|---|---|---|---|')
    for c in v3.curve(test, by, thresholds=(0.0, 0.6, 0.7, 0.8, 0.85)):
        if not (c['critic'] or c['second']) and c['threshold'] not in (0.0, 0.7):
            continue
        w(f'| {c["threshold"]} | {"yes" if c["critic"] else "no"} | {"yes" if c["second"] else "no"} | {c["coverage"]:.0%} | '
          f'{(c["precision"] or 0):.0%} | {c["wrong_merges"]} | {c["wrong_closes"]} |')
    w('')
    w('### Every case the bot would have decided wrongly on test')
    bad = [x for x in mt['rows'] if v3.family(x['final']) != 'escalate' and v3.family(x['final']) != x['family']]
    if not bad:
        w('None.')
    for x in bad:
        r = by[x['pr']]
        w(f'- **#{x["pr"]}** ({r["type"]}) {r["title"][:90]}: Gathin **{r["truth"]}**, bot **{x["final"]}** '
          f'(confidence {x["confidence"]:.2f}). Bot: {"; ".join(x["reasons"])[:300]}. '
          f'Maintainer: {(r.get("maintainer_note") or r.get("fix") or "(no note)")[:250]}')
    w('')
    w('### Fix needed vs plain merge (test, accepted PRs)')
    acc = [x for x in mt['rows'] if v3.family(x['final']) == 'accept' and x['family'] == 'accept']
    if acc:
        same = sum(1 for x in acc if (x['final'] == 'merge-with-fix') == by[x['pr']]['fix_needed'])
        w(f'Of {len(acc)} correct accepts, the bot matched "fix needed or not" on {same} ({same / len(acc):.0%}).')
    w('')

w('## Train: before and after rule mining (same 86 PRs)')
for name, res in (('v3 rules v2 (dev1)', dev1), ('v3 rules v3 (dev2)', dev2)):
    m = stats_v3(res, POLICY)
    raw = v3.model_only(res)
    w(f'- {name}: raw agreement {raw["family_agreement"]:.0%}; with policy {m["coverage"]:.0%} decided alone at '
      f'{(m["precision_when_bot_decides"] or 0):.0%} correct, {len(m["wrong_merges"])} wrong merges.')
w('')
w('## Rules learned from your past decisions')
cand = json.load(open('runs/rule-candidates.json'))
applied_marks = ['bundles', 'CI workflow', 'bug fixes', 'base rule', 'off by default', 'same helper', 'different design']
w('Applied to MAINTAINER.md (please confirm):')
for r in cand['rules']:
    txt = r['rule']
    applied = any(k.lower() in txt.lower() for k in ('bundles several', 'ci workflow', 'bug fixes', "base rule", 'diff, not the description', 'two open prs', 'different design'))
    if applied:
        w(f'- ✅ {txt} (from #{", #".join(map(str, r["evidence_prs"]))})')
w('')
w('Not applied (your call; they loosen a safety rule or contradict your recent rounds):')
for r in cand['rules']:
    txt = r['rule']
    applied = any(k.lower() in txt.lower() for k in ('bundles several', 'ci workflow', 'bug fixes', "base rule", 'diff, not the description', 'two open prs', 'different design'))
    if not applied:
        w(f'- ⏸ {txt} (from #{", #".join(map(str, r["evidence_prs"]))})')
w('')
w('## Cost')
v3calls = Counter()
for line in open('runs/ledger.jsonl'):
    e = json.loads(line)
    if e['tag'].startswith('v3'):
        v3calls[(e['model'], e['tag'].split(':')[0])] += e['usd']
for (m, t), usd in sorted(v3calls.items()):
    w(f'- {t} on {m}: ${usd:.2f}')
if test:
    tusd = sum(json.loads(l)['usd'] for l in open('runs/ledger.jsonl') if json.loads(l)['tag'].split(':')[-1].isdigit()
               and json.loads(l)['tag'].startswith('v3') and int(json.loads(l)['tag'].split(':')[-1]) in {r['pr'] for r in test})
    w(f'- Per PR on the test split (decision + critic + second opinion): about ${tusd / len(test):.3f}')
w('')
open('report/v3.md', 'w').write('\n'.join(out) + '\n')
print('\n'.join(out[:60]))
print('POLICY', POLICY)
