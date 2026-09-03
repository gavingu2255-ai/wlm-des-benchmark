#!/usr/bin/env python3
"""
verify_tables.py — recompute every table in the manuscript from the released CSVs.

Single source of truth per table, single metric convention throughout:

  * All reported h / s / c are CLAUDE-JUDGE scores (the primary judge).
  * Dh is the hallucination-only inter-judge disagreement,
        Dh = mean over tasks of |h_claude - h_gpt4o|.
  * Cohen's d is computed against Baseline A within each model,
    with a bootstrapped 95% CI (5,000 resamples, numpy seed 42).
    An effect is marked confirmed when the CI lower bound exceeds zero.
  * Rows flagged as judge parse errors are excluded.
  * Where a (model, format, task) cell appears more than once in a file,
    the last occurrence is kept.

Sources
  Table 1  -> full_v6_scores.csv        + gemini_all_scores.csv (experiment == exp1)
  Table 4  -> exp2_scores.csv           + gemini_all_scores.csv (experiment == exp2)
  Table 5  -> exp2_scores.csv           (small-model tier)
  Table 6  -> exp3_scores.csv           + gemini_all_scores.csv (experiment == exp3)

Usage
    python verify_tables.py            # print all tables
    python verify_tables.py --csv out  # also write out/table{1,4,5,6}.csv
"""

import argparse
import csv
import os
import sys
from statistics import mean, stdev

import numpy as np

SEED = 42
N_BOOT = 5000

MODEL_ORDER = ["claude", "gpt-4o", "gemini-pro", "gpt-4o-mini", "qwen-7b", "gemma-4b"]
MODEL_LABEL = {
    "claude": "Claude Sonnet 4",  # claude-sonnet-4-20250514
    "gpt-4o": "GPT-4o",
    "gemini-pro": "Gemini 2.5 Flash",
    "gpt-4o-mini": "GPT-4o-mini",
    "qwen-7b": "Qwen2.5-7B",
    "gemma-4b": "Gemma3-4B",
}
FORMAT_ORDER = ["wlm_hybrid_v2", "wlm_sl", "wlm_json", "base_a", "base_b"]
FORMAT_LABEL = {
    "wlm_hybrid_v2": "WLM-Hybrid v2.2",
    "wlm_sl": "WLM-SL",
    "wlm_json": "WLM-JSON",
    "base_a": "Baseline A",
    "base_b": "Baseline B",
}

HERE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "data", "published", "results")


# ---------------------------------------------------------------- loading


def load(fname):
    path = os.path.join(HERE, fname)
    if not os.path.exists(path):
        sys.exit(f"missing data file: {path}")
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def clean(rows, experiment=None):
    """Drop parse errors, keep the last row per (model, format, task)."""
    out = {}
    for r in rows:
        if experiment is not None and r.get("experiment") != experiment:
            continue
        if r.get("claude_parse_error") == "True" or r.get("gpt4o_parse_error") == "True":
            continue
        if not r.get("claude_hallucination"):
            continue
        out[(r["model_key"], r["prompt_key"], r["task_id"])] = r
    return list(out.values())


def cells(rows, model, fmt, col):
    vals = []
    for r in rows:
        if r["model_key"] == model and r["prompt_key"] == fmt:
            v = r.get(col, "")
            if v not in ("", None):
                vals.append(float(v))
    return vals


# ---------------------------------------------------------------- metrics


def dh_of(rows, model, fmt):
    """Hallucination-only inter-judge disagreement."""
    diffs = [
        abs(float(r["claude_hallucination"]) - float(r["gpt4o_hallucination"]))
        for r in rows
        if r["model_key"] == model
        and r["prompt_key"] == fmt
        and r.get("claude_hallucination")
        and r.get("gpt4o_hallucination")
    ]
    return mean(diffs) if diffs else None


def cohens_d(a, b):
    if len(a) < 2 or len(b) < 2:
        return None
    pooled = ((stdev(a) ** 2 + stdev(b) ** 2) / 2) ** 0.5
    if pooled == 0:
        return 0.0
    return (mean(a) - mean(b)) / pooled


def boot_ci(a, b, n_boot=N_BOOT, seed=SEED):
    if len(a) < 2 or len(b) < 2:
        return None, None
    rng = np.random.default_rng(seed)
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    ds = np.empty(n_boot)
    for i in range(n_boot):
        sa = rng.choice(a, size=a.size, replace=True)
        sb = rng.choice(b, size=b.size, replace=True)
        va, vb = sa.var(ddof=1), sb.var(ddof=1)
        pooled = ((va + vb) / 2) ** 0.5
        ds[i] = 0.0 if pooled == 0 else (sa.mean() - sb.mean()) / pooled
    return float(np.percentile(ds, 2.5)), float(np.percentile(ds, 97.5))


def fmt_num(v, nd=2):
    return "—" if v is None else f"{v:.{nd}f}"


# ---------------------------------------------------------------- tables


def build(rows, models, formats, with_effects):
    """Return list of dicts, one per (model, format) condition."""
    out = []
    for m in models:
        base = cells(rows, m, "base_a", "claude_hallucination")
        for f in formats:
            h = cells(rows, m, f, "claude_hallucination")
            if not h:
                continue
            s = cells(rows, m, f, "claude_structure")
            c = cells(rows, m, f, "claude_completeness")
            eta = cells(rows, m, f, "claude_token_efficiency")
            row = {
                "model": MODEL_LABEL.get(m, m),
                "model_key": m,
                "format": FORMAT_LABEL.get(f, f),
                "format_key": f,
                "n": len(h),
                "h": mean(h),
                "s": mean(s) if s else None,
                "c": mean(c) if c else None,
                "eta": mean(eta) if eta else None,
                "dh": dh_of(rows, m, f),
            }
            if with_effects and f != "base_a" and base:
                d = cohens_d(h, base)
                lo, hi = boot_ci(h, base)
                row.update(
                    d=d,
                    ci_lo=lo,
                    ci_hi=hi,
                    confirmed=(lo is not None and lo > 0),
                )
            else:
                row.update(d=None, ci_lo=None, ci_hi=None, confirmed=False)
            out.append(row)
    return out


def show(title, note, rows, with_effects):
    print()
    print("=" * 96)
    print(title)
    print(note)
    print("=" * 96)
    if with_effects:
        hdr = f"{'Model':<20}{'Format':<18}{'n':>3}  {'h':>5} {'s':>5} {'c':>5} {'eta':>6} {'Dh':>6}  {'d':>7} {'95% CI':>18}  {'':<3}"
    else:
        hdr = f"{'Model':<20}{'Format':<18}{'n':>3}  {'h':>5} {'s':>5} {'c':>5} {'eta':>6} {'Dh':>6}"
    print(hdr)
    print("-" * len(hdr))
    last = None
    for r in rows:
        if last is not None and r["model_key"] != last:
            print()
        last = r["model_key"]
        line = (
            f"{r['model']:<20}{r['format']:<18}{r['n']:>3}  "
            f"{fmt_num(r['h']):>5} {fmt_num(r['s']):>5} {fmt_num(r['c']):>5} "
            f"{fmt_num(r['eta'], 3):>6} {fmt_num(r['dh'], 3):>6}"
        )
        if with_effects:
            if r["d"] is None:
                line += f"  {'—':>7} {'—':>18}   "
            else:
                ci = f"[{r['ci_lo']:+.2f}, {r['ci_hi']:+.2f}]"
                star = " *" if r["confirmed"] else ""
                line += f"  {r['d']:>+7.2f} {ci:>18}  {star:<3}"
        print(line)
    if with_effects:
        print()
        print("* = bootstrapped 95% CI lower bound > 0 (confirmed effect)")


def write_csv(path, rows):
    fields = [
        "model", "model_key", "format", "format_key", "n",
        "h", "s", "c", "eta", "dh", "d", "ci_lo", "ci_hi", "confirmed",
    ]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in fields})


# ---------------------------------------------------------------- main


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", metavar="DIR", help="also write table CSVs to DIR")
    args = ap.parse_args()

    v6 = load("full_v6_scores.csv")
    gem = load("gemini_all_scores.csv")
    e2 = load("exp2_scores.csv")
    e3 = load("exp3_scores.csv")

    exp1 = clean(v6) + clean(gem, experiment="exp1")
    exp2 = clean(e2) + clean(gem, experiment="exp2")
    exp3 = clean(e3) + clean(gem, experiment="exp3")

    large = ["claude", "gpt-4o", "gemini-pro"]
    small = ["gpt-4o-mini", "qwen-7b", "gemma-4b"]

    t1 = build(exp1, MODEL_ORDER, FORMAT_ORDER, with_effects=True)
    t4 = build(exp2, large, FORMAT_ORDER, with_effects=True)
    t5 = build(exp2, small, ["wlm_sl", "base_a", "base_b"], with_effects=True)
    t6 = build(exp3, ["claude", "gpt-4o", "gemini-pro"], FORMAT_ORDER, with_effects=True)

    show(
        "TABLE 1 — Experiment 1: format selection (T01–T07)",
        "source: full_v6_scores.csv + gemini_all_scores.csv[exp1]   |   Claude judge, n = 7 tasks per condition",
        t1, True,
    )
    show(
        "TABLE 4 — Experiment 2: cross-domain generalization, large models (T08–T37)",
        "source: exp2_scores.csv + gemini_all_scores.csv[exp2]      |   Claude judge, n = 30 tasks per condition",
        t4, True,
    )
    show(
        "TABLE 5 — Experiment 2: small-model tier (T08–T37)",
        "source: exp2_scores.csv                                    |   Claude judge, n = 30 tasks per condition",
        t5, True,
    )
    show(
        "TABLE 6 — Experiment 3: adversarial stress test (8 selected tasks)",
        "source: exp3_scores.csv + gemini_all_scores.csv[exp3]      |   Claude judge, n = 8 tasks per condition",
        t6, True,
    )

    if args.csv:
        os.makedirs(args.csv, exist_ok=True)
        for name, rows in [("table1", t1), ("table4", t4), ("table5", t5), ("table6", t6)]:
            p = os.path.join(args.csv, f"{name}.csv")
            write_csv(p, rows)
            print(f"wrote {p}")


if __name__ == "__main__":
    main()
