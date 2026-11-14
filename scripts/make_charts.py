"""Render README/blog/video charts from the saved 2026-11-07 run. No API calls.

    python scripts/make_charts.py [RUN_DIR] [OUT_DIR]
"""
import collections
import glob
import json
import sqlite3
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
from matplotlib import font_manager

RUN = Path(sys.argv[1] if len(sys.argv) > 1 else ".benchmark-runs/rerun-20261107")
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "docs/figures")
OUT.mkdir(parents=True, exist_ok=True)

# Truss brand (truss.signalor.app): paper, slate ink, amber accent, EB Garamond
BG, INK, MUTED, GRID = "#FAFAF8", "#0F172A", "#57534E", "#E7E5E4"
AMBER, AMBER_DEEP, TAN, STONE = "#B45309", "#914400", "#E3B98C", "#D6D3D1"
for f in (Path(__file__).resolve().parent.parent / "docs" / "fonts").glob("EBGaramond*.ttf"):
    font_manager.fontManager.addfont(str(f))
plt.rcParams.update({
    "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG,
    "text.color": INK, "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": INK,
    "axes.edgecolor": INK, "axes.linewidth": 0.8, "font.size": 15, "axes.titlesize": 22,
    "axes.titleweight": "normal", "axes.titlelocation": "left", "axes.titlepad": 14,
    "axes.spines.top": False, "axes.spines.right": False,
    "font.family": ["EB Garamond", "Georgia", "DejaVu Serif"],
})

lb = json.loads((RUN / "final-leaderboard.json").read_text())
rows = [dict(r, overall=r["overall_100"]) for r in lb["leaderboard"]]


def name(r):
    return r["display"]


def subtitle(fig, text):
    fig.text(0.012, -0.03, text, color=AMBER_DEEP, fontsize=12, style="italic")


def save(fig, fn):
    fig.savefig(OUT / fn, dpi=200, bbox_inches="tight", pad_inches=0.3)
    plt.close(fig)
    print("wrote", OUT / fn)


# 1. Leaderboard
rows = sorted(rows, key=lambda r: r["overall"])
fig, ax = plt.subplots(figsize=(11, 7))
ys = range(len(rows))
top = max(r["overall"] for r in rows)
ax.barh(ys, [r["overall"] for r in rows], color=[AMBER if r["overall"] == top else INK for r in rows], height=0.6)
for y, r in zip(ys, rows):
    ax.text(r["overall"] + 0.8, y, f'{r["overall"]:.1f}', va="center", color=INK, fontsize=14)
ax.set_yticks(list(ys), [name(r) for r in rows])
ax.set_xlim(0, 100)
ax.xaxis.grid(True, color=GRID, lw=0.9)
ax.set_axisbelow(True)
ax.tick_params(axis="y", length=0)
ax.set_title("Best frontier model scores 54.5 / 100")
ax.set_xlabel("Overall score (mean of Keep/Pull, Rulebook, Research)")
subtitle(fig, "14 models x 21 frozen cases, 1 run per case, run 2026-11-07/08. Judge: openai/gpt-6.1-sol-pro.")
save(fig, "leaderboard.png")

# Collect deterministic grader outcomes, one per (model, case)
seen, wr, kg = set(), collections.Counter(), collections.Counter()
for f in sorted(glob.glob(str(RUN / "*-judge*/judged.json"))):
    d = json.loads(Path(f).read_text())
    m = d["model"] if isinstance(d["model"], str) else json.dumps(d["model"], sort_keys=True)
    if m not in {r["model"] for r in lb["leaderboard"]}:
        continue  # pilot models outside the roster (e.g. Gemini 3.7 Flash)
    for c in d["cases"]:
        k = (m, c["case_id"])
        if k in seen:
            continue
        seen.add(k)
        g = c.get("grader") or {}
        if c["case_id"].startswith("RB"):
            got = str(((g.get("rulebook") or {}).get("parsed") or {}).get("work_rest_min"))
            wr["40/20 (2003 card)" if got == "40/20" else "NL (correct, 2022)" if got == "NL"
               else "no answer" if got == "None" else "other value"] += 1
        if c["case_id"].startswith("KG") and "design" in g:
            et = g.get("error_type")
            kg[(g["design"], "correct" if et is None and g.get("decision_correct") else et or "correct")] += 1

# 2. Rulebook
order = ["40/20 (2003 card)", "other value", "no answer", "NL (correct, 2022)"]
colors = [AMBER, STONE, STONE, INK]
fig, ax = plt.subplots(figsize=(11, 5.2))
vals = [wr[o] for o in order]
ax.bar(order, vals, color=colors, width=0.6)
for i, v in enumerate(vals):
    ax.text(i, v + 0.3, str(v), ha="center", color=INK, fontsize=20)
ax.set_ylabel("answers (of 28)")
ax.yaxis.set_major_locator(matplotlib.ticker.MultipleLocator(5))
ax.yaxis.grid(True, color=GRID, lw=0.9)
ax.set_axisbelow(True)
ax.tick_params(axis="x", length=0)
ax.set_title("Models recite the 2003 heat card, not the 2022 one")
subtitle(fig, "TB MED 507, Moderate work at Yellow flag: work/rest per hour. 2022 card = NL (no limit); 2003 card = 40/20.")
save(fig, "rulebook.png")

# 3. Keep/Pull by case design
designs = [("falling_power_thermal_lag", "Slowed down,\ncore still rising"),
           ("steady_power_rising", "Steady work,\ncore rising"),
           ("falling_power_safe", "Slowed down,\nactually safe"),
           ("steady_power_safe", "Steady work,\nactually safe")]
fig, ax = plt.subplots(figsize=(11, 5.6))
x = range(len(designs))
c_ = [kg[(d, "correct")] for d, _ in designs]
fp = [kg[(d, "false_pull")] for d, _ in designs]
mp = [kg[(d, "missed_pull")] for d, _ in designs]
ax.bar(x, c_, color=INK, width=0.6, label="correct call", edgecolor=BG, lw=2)
ax.bar(x, fp, bottom=c_, color=TAN, width=0.6, label="needless pull", edgecolor=BG, lw=2)
ax.bar(x, mp, bottom=[a + b for a, b in zip(c_, fp)], color=AMBER_DEEP, width=0.6, label="missed pull (dangerous)", edgecolor=BG, lw=2)
for i in x:
    for base, v, fg in ((0, c_[i], BG), (c_[i], fp[i], INK), (c_[i] + fp[i], mp[i], BG)):
        if v >= 4:
            ax.text(i, base + v / 2, str(v), ha="center", va="center", color=fg, fontsize=16)
ax.set_xticks(list(x), [l for _, l in designs])
ax.tick_params(axis="x", length=0)
ax.set_ylabel("model answers")
ax.set_ylim(0, 50)
ax.legend(frameon=False, loc="upper center", ncol=3, fontsize=14, bbox_to_anchor=(0.5, 1.0))
ax.set_title("Keep or pull: 55% right, and safe soldiers get pulled", pad=28)
subtitle(fig, "Deterministic grade vs measured rectal temp 15 min later (PULL iff >= 38.5 C). 168 answers, 14 models.")
save(fig, "keep_pull.png")

# 4. Cost vs score
spend = collections.Counter()
for f in glob.glob(str(RUN / "**/spend.sqlite"), recursive=True):
    try:
        rows_ = list(sqlite3.connect(f).execute("select model, charged_nano, accounting from charges"))
    except sqlite3.Error:
        continue  # empty or partial ledger
    for m, c, a in rows_:
        if a == "provider_reported" and c:
            spend[m] += c / 1e9
fig, ax = plt.subplots(figsize=(11, 6.2))
pts = []
for r in rows:
    pts.append((spend[r["model"]], r["overall"], name(r)))
ax.scatter([p[0] for p in pts], [p[1] for p in pts], s=110, color=INK, edgecolor=BG, lw=2, zorder=3)
for s, o, n in pts:
    dy = -16 if n.startswith(("Gemini 3.8", "Muse")) else 5
    ax.annotate(n, (s, o), xytext=(7, dy), textcoords="offset points", fontsize=13, color=MUTED)
ax.set_xscale("log")
ax.set_xlabel("provider-reported USD to answer the 21 cases, incl. retries (log scale)")
ax.set_ylabel("overall score / 100")
ax.grid(True, color=GRID, lw=0.9)
ax.set_axisbelow(True)
ax.set_title("Paying 100x more does not buy a better medic")
judge = spend.get("openai/gpt-6.1-sol-pro", 0)
subtitle(fig, f"Total provider-reported spend \\${lb['spend']['provider_reported_usd']:.2f} incl. judge \\${judge:.2f}. Prices: OpenRouter, retrieved 2026-11-08.")
save(fig, "cost_vs_score.png")

print(json.dumps({"spend": {k: round(v, 2) for k, v in spend.most_common()}, "rulebook": wr, "kg": {f"{a}|{b}": v for (a, b), v in kg.items()}}, default=str))
