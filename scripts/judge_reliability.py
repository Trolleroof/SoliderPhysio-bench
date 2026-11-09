"""LLM-judge reliability checks over saved judged.json files (no API calls).

1. Test-retest: the same (model, case) answer judged more than once -> exact and
   within-1 agreement per rubric dimension.
2. Agreement with the deterministic grader: judge's `decision` mark versus the
   rule-based decision_correct flag (Keep/Pull and Rulebook body half).

    python3 scripts/judge_reliability.py [RUN_DIR]
"""
import itertools
import json
import sys
from collections import defaultdict
from pathlib import Path

run = Path(sys.argv[1] if len(sys.argv) > 1 else ".benchmark-runs/rerun-20261107")
if not run.exists():
    run = Path("results/rerun-20261107")  # layout inside the submission zip

marks = defaultdict(list)          # (model, case, answer_hash) -> [judge dict, ...]
vs_rule = defaultdict(list)        # decision mark -> [decision_correct, ...]
for f in sorted(run.glob("*judge*/judged.json")):
    d = json.loads(f.read_text())
    model = d.get("model") if isinstance(d.get("model"), str) else json.dumps(d.get("model"), sort_keys=True)
    for c in d["cases"]:
        j = c.get("judge") or {}
        if not j:
            continue
        key = (model, c["case_id"], hash(json.dumps(c.get("answer") or c.get("grader"), sort_keys=True)))
        marks[key].append((f.parent.name, j))
        g = c.get("grader") or {}
        if "decision_correct" in g and isinstance(j.get("decision"), (int, float)):
            vs_rule[j["decision"]].append(bool(g["decision_correct"]))

pairs = defaultdict(lambda: [0, 0, 0])   # dim -> [n, exact, within1]
cases_rejudged = 0
for runs in marks.values():
    runs = {d: j for d, j in runs}          # one per judge dir
    if len(runs) < 2:
        continue
    cases_rejudged += 1
    for a, b in itertools.combinations(runs.values(), 2):
        for dim in set(a) & set(b):
            x, y = a[dim], b[dim]
            if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                p = pairs[dim]
                p[0] += 1
                p[1] += x == y
                p[2] += abs(x - y) <= 1

print(f"Test-retest: {cases_rejudged} answers judged 2+ times")
for dim, (n, ex, w1) in sorted(pairs.items()):
    print(f"  {dim:22s} pairs={n:4d}  exact={ex / n:.0%}  within-1={w1 / n:.0%}")
print("Judge decision mark vs deterministic decision_correct:")
for mark in sorted(vs_rule):
    v = vs_rule[mark]
    print(f"  mark={mark}: n={len(v):3d}  rule says correct in {sum(v) / len(v):.0%}")
