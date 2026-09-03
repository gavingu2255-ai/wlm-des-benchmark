#!/usr/bin/env python3
"""
analyze_ablation.py — decompose the D/E/S effect into marking and scaffold

    python analysis/analyze_ablation.py data/results/ablation_<batch>.csv
    python analysis/analyze_ablation.py <csv> --metric eta
    python analysis/analyze_ablation.py <csv> --csv out/ablation_summary.csv

Reports, per model and per metric:

    marking  = base_c - base_a      contribution of the marking instruction
    scaffold = hybrid - base_c      contribution of the three-layer structure
    total    = hybrid - base_a      the effect the submitted paper reported

Metrics follow the manuscript's conventions (docs/DATA_SOURCE.md):

    h    hallucination suppression, 1-5, Claude judge — primary outcome
    s    structure coherence, 1-5, Claude judge
    c    completeness, 1-5, Claude judge
    eta  token efficiency, mu / ln(tau + 1) — Claude judge
    tok  raw output token count — objective, not judge-mediated
    dh   inter-judge disagreement on h, |h_claude - h_gpt4o| — lower is better

The scaffold row on h is the answer to Reviewer 1 objections 2 and 6. Near zero
means the layer decomposition adds nothing beyond instructing the model to mark
its claims, and the paper's claim must narrow to that. Clearly positive means
the objection is answered empirically.

Read eta and tok alongside h. Token count is a direct measurement that never
passes through a judge, so it is immune to the circularity Reviewer 1 raised
about h. A format that scores the same on h while using fewer tokens is a real
result regardless of how that debate settles.
"""

import argparse
import csv
import sys
from collections import defaultdict
from statistics import mean, stdev

import numpy as np

try:
    from scipy.stats import wilcoxon
    HAVE_SCIPY = True
except ImportError:
    HAVE_SCIPY = False

SEED = 42
N_BOOT = 5000

# label -> (csv column, decimals, higher_is_better)
METRICS = {
    "h":   ("claude_hallucination",    2, True),
    "s":   ("claude_structure",        2, True),
    "c":   ("claude_completeness",     2, True),
    "eta": ("claude_token_efficiency", 3, True),
    "tok": ("output_tokens",           0, False),
    "dh":  ("agreement_hallucination_diff", 3, False),
}

CONDITIONS = ["wlm_hybrid_v2", "base_c", "base_d", "base_a", "base_b"]

# Each row isolates one thing, given what the two conditions share.
#
#   hybrid vs base_c   both impose a seven-field schema filled before the answer.
#                      They differ in what the fields mean. Isolates the D/E/S
#                      semantics from structured output as such.
#
#   hybrid vs base_d   both ask the model to qualify its claims. They differ in
#                      whether any structure is imposed. Isolates the layer
#                      scaffold from the instruction to express uncertainty —
#                      the condition Reviewer 1's circularity objection predicts
#                      will close the gap.
#
#   base_c vs base_d   schema without semantics against qualification without
#                      schema. Neither is D/E/S; the comparison says which of the
#                      two ingredients matters more on its own.
#
# The base_a and base_b rows run when those conditions are present in the file.
STEPS = [
    ("semantics    hybrid - base_c", "wlm_hybrid_v2", "base_c"),
    ("structure    hybrid - base_d", "wlm_hybrid_v2", "base_d"),
    ("schema/unc   base_c - base_d", "base_c",        "base_d"),
    ("vs raw       hybrid - base_a", "wlm_hybrid_v2", "base_a"),
    ("vs CoT       hybrid - base_b", "wlm_hybrid_v2", "base_b"),
]


def load(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r.get("claude_parse_error") == "True":
                continue
            if r.get("gpt4o_parse_error") == "True":
                continue
            if not r.get("claude_hallucination"):
                continue
            rows.append(r)
    return rows


def cohens_d(a, b):
    if len(a) < 2 or len(b) < 2:
        return None
    pooled = ((stdev(a) ** 2 + stdev(b) ** 2) / 2) ** 0.5
    return 0.0 if pooled == 0 else (mean(a) - mean(b)) / pooled


def boot_ci(a, b, n_boot=N_BOOT, seed=SEED):
    if len(a) < 2 or len(b) < 2:
        return None, None
    rng = np.random.default_rng(seed)
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    ds = np.empty(n_boot)
    for i in range(n_boot):
        sa = rng.choice(a, a.size, replace=True)
        sb = rng.choice(b, b.size, replace=True)
        pooled = ((sa.var(ddof=1) + sb.var(ddof=1)) / 2) ** 0.5
        ds[i] = 0.0 if pooled == 0 else (sa.mean() - sb.mean()) / pooled
    return float(np.percentile(ds, 2.5)), float(np.percentile(ds, 97.5))


def paired(rows, model, col, cond_a, cond_b):
    """Per-task means for two conditions, paired on task id."""
    acc = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r["model_key"] != model:
            continue
        v = r.get(col, "")
        if v in ("", None):
            continue
        try:
            acc[r["prompt_key"]][r["task_id"]].append(float(v))
        except ValueError:
            continue
    A, B = acc.get(cond_a, {}), acc.get(cond_b, {})
    tasks = sorted(set(A) & set(B))
    return tasks, [mean(A[t]) for t in tasks], [mean(B[t]) for t in tasks]


def stat_line(label, tasks, a, b, nd, higher_better):
    if not tasks:
        return f"  {label:<30} no paired tasks"
    diff = mean(a) - mean(b)
    d = cohens_d(a, b)
    lo, hi = boot_ci(a, b)
    wins = sum(x > y for x, y in zip(a, b))
    loss = sum(x < y for x, y in zip(a, b))
    tie = len(tasks) - wins - loss
    p = ""
    if HAVE_SCIPY and any(x != y for x, y in zip(a, b)):
        try:
            p = f"  p={wilcoxon(a, b).pvalue:.4f}"
        except ValueError:
            p = ""
    ci = f"[{lo:+.2f}, {hi:+.2f}]" if lo is not None else "—"
    # star marks a CI that excludes zero in the favourable direction
    if lo is None:
        star = "  "
    elif higher_better and lo > 0:
        star = " *"
    elif (not higher_better) and hi < 0:
        star = " *"
    else:
        star = "  "
    dstr = f"{d:+6.2f}" if d is not None else "     —"
    return (f"  {label:<30} n={len(tasks):3}  Δ={diff:+8.{nd}f}  d={dstr}  "
            f"{ci:>16}{star}  {wins}>{loss}({tie}){p}")


def condition_means(rows, model, col):
    out = {}
    for c in CONDITIONS:
        vals = []
        for r in rows:
            if r["model_key"] == model and r["prompt_key"] == c:
                v = r.get(col, "")
                if v not in ("", None):
                    try:
                        vals.append(float(v))
                    except ValueError:
                        pass
        out[c] = mean(vals) if vals else None
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--metric", default="all",
                    help="h | s | c | eta | tok | dh | all   (default: all)")
    ap.add_argument("--csv", metavar="FILE", help="also write a summary CSV")
    args = ap.parse_args()

    rows = load(args.path)
    if not rows:
        sys.exit("no usable rows (all parse errors?)")

    if args.metric == "all":
        metrics = list(METRICS)
    elif args.metric in METRICS:
        metrics = [args.metric]
    else:
        sys.exit(f"unknown metric {args.metric!r}; choose from {', '.join(METRICS)} or 'all'")

    models = sorted({r["model_key"] for r in rows})
    runs = sorted({r.get("run_index", "1") for r in rows})

    print()
    print("=" * 100)
    print("  MARKER-ABLATION DECOMPOSITION")
    print(f"  source: {args.path}")
    print(f"  {len(rows)} scored rows | models: {', '.join(models)} | repeats: {len(runs)}")
    print("=" * 100)
    if not HAVE_SCIPY:
        print("  note: scipy not installed — Wilcoxon p-values omitted")

    # ── condition means, all metrics at a glance ─────────────────────────────
    print()
    print("  CONDITION MEANS")
    hdr = f"  {'model':<12}{'condition':<16}" + "".join(f"{m:>10}" for m in metrics)
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for m in models:
        for c in CONDITIONS:
            cells = ""
            for met in metrics:
                col, nd, _ = METRICS[met]
                v = condition_means(rows, m, col)[c]
                cells += f"{v:>10.{nd}f}" if v is not None else f"{'—':>10}"
            print(f"  {m:<12}{c:<16}{cells}")
        print()

    # ── decomposition per metric ─────────────────────────────────────────────
    summary = []
    for met in metrics:
        col, nd, higher = METRICS[met]
        print("=" * 100)
        direction = "higher is better" if higher else "lower is better"
        print(f"  METRIC: {met}   ({col}, {direction})")
        print("=" * 100)
        for m in models:
            print(f"\n── {m} " + "─" * (94 - len(m)))
            for label, ca, cb in STEPS:
                t, a, b = paired(rows, m, col, ca, cb)
                print(stat_line(label, t, a, b, nd, higher))
                if t:
                    lo, hi = boot_ci(a, b)
                    summary.append({
                        "model": m, "metric": met, "step": label.split()[0],
                        "n": len(t),
                        "mean_a": round(mean(a), 4), "mean_b": round(mean(b), 4),
                        "delta": round(mean(a) - mean(b), 4),
                        "cohens_d": round(cohens_d(a, b), 4) if cohens_d(a, b) is not None else "",
                        "ci_lo": round(lo, 4) if lo is not None else "",
                        "ci_hi": round(hi, 4) if hi is not None else "",
                    })
        print()
        print("  * = bootstrapped 95% CI excludes zero in the favourable direction")
        print()

    # ── run-to-run stability ─────────────────────────────────────────────────
    if len(runs) > 1:
        print("=" * 100)
        print("  RUN-TO-RUN STABILITY  (h, Claude judge)")
        print("=" * 100)
        print(f"  {'model':<12}{'condition':<16}" +
              "".join(f"{'run '+str(r):>9}" for r in runs) + f"{'spread':>9}")
        for m in models:
            for c in CONDITIONS:
                per_run = []
                for r in runs:
                    v = [float(x["claude_hallucination"]) for x in rows
                         if x["model_key"] == m and x["prompt_key"] == c
                         and x.get("run_index", "1") == r]
                    per_run.append(mean(v) if v else None)
                vals = [v for v in per_run if v is not None]
                if not vals:
                    continue
                cells = "".join(f"{v:9.2f}" if v is not None else f"{'—':>9}"
                                for v in per_run)
                print(f"  {m:<12}{c:<16}{cells}{max(vals)-min(vals):9.2f}")
        print()
        print("  spread = max - min across repeats. The submitted paper ran each")
        print("  condition once and estimated this at ±0.5–1.0 without measuring it.")
        print()

    # ── plain-language read ─────────────────────────────────────────────────
    print("=" * 100)
    print("  READING")
    print("=" * 100)
    for met in metrics:
        col, nd, higher = METRICS[met]
        print(f"\n  {met}:")
        for m in models:
            bits = []
            for label, ca, cb in STEPS:
                t, a, b = paired(rows, m, col, ca, cb)
                if not t:
                    continue
                bits.append(f"{label.split()[0]:<10}{mean(a)-mean(b):+8.{nd}f}")
            if bits:
                print(f"    {m:<12}" + "   ".join(bits))

    # ── ceiling warning ──────────────────────────────────────────────────────
    ceiling = []
    for m in models:
        for c in CONDITIONS:
            v = condition_means(rows, m, "claude_hallucination")[c]
            if v is not None and v >= 4.9:
                ceiling.append(f"{m}/{c} (h={v:.2f})")
    if ceiling:
        print()
        print("  CEILING WARNING")
        print("  These conditions sit at or near the top of the 1-5 scale:")
        for cnd in ceiling:
            print(f"    {cnd}")
        print("  A scaffold difference of zero at the ceiling means the scale")
        print("  cannot resolve it, not that the scaffold does nothing. Read those")
        print("  rows against eta and tok, which have no ceiling.")
    print()

    if args.csv:
        import os
        d = os.path.dirname(args.csv)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(summary[0]))
            w.writeheader()
            w.writerows(summary)
        print(f"  summary written to {args.csv}")
        print()


if __name__ == "__main__":
    main()
