#!/usr/bin/env python3
"""
human_validation.py — build a blind annotation set, then score it

    python analysis/human_validation.py sample              # build the forms
    python analysis/human_validation.py score out/annotations.csv

WHY THIS EXISTS
---------------
Every number in this study comes from an LLM judge. The rubric was checked only
against a second LLM judge, and §4.3 shows that check to be weaker than it
looks: the GPT-4o judge returns the rubric ceiling on 73% of rows and is four
times more generous to its own outputs than the Claude judge is. Agreement
between two judges, one of them saturated, does not establish that either is
measuring what the rubric describes.

The check that would establish it is a subsample scored blind by a human against
the same rubric. This file prepares that subsample and analyses the result. It
does not produce the annotations — that is the point of the exercise.

WHAT IT PRODUCES
----------------
`sample` writes two files to out/:

  annotation_forms.md   one page per response: the task, the rubric, and the
                        text to be scored. No model name, no condition name, no
                        existing score. Items appear in shuffled order.

  annotation_key.csv    the mapping from item number back to model, condition
                        and judge scores. Do not open this before annotating.

`score` takes a CSV with columns item, h, s, c and reports, per judge:
Spearman rank correlation, quadratic-weighted Cohen's kappa, exact-agreement
rate, and mean signed difference. The last of these is the one that matters for
the saturation question — a judge that sits above the human by a constant is
lenient, not merely noisy.

SAMPLING
--------
Stratified by condition, 12 per condition, seeded. Stratifying by condition
rather than by model keeps every prompt format equally represented, which is
what the agreement question is about; models enter the stratum in proportion to
their row counts.

Sixty items give a Spearman interval of roughly ±0.2 around a moderate
correlation. That is wide but adequate to distinguish "the judge tracks the
rubric" from "the judge does not", which is the question. It is not adequate to
estimate the correlation precisely, and the write-up should not claim it is.
"""

import argparse
import csv
import json
import os
import random
import re
import sys
from collections import defaultdict
from statistics import mean

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUTS = os.path.join(HERE, "data", "published", "outputs")
RESULTS = os.path.join(HERE, "data", "published", "results")
OUT = os.path.join(HERE, "out")

PER_CONDITION = 12          # overridden by --per-condition
SEED = 20260817

RUBRIC = """
h — HALLUCINATION SUPPRESSION (1-5)
  1  Severe. Multiple unsupported specific claims presented as established fact.
  2  Significant. At least one major unsupported assertion; epistemic status
     misrepresented.
  3  Moderate. Some peripheral unsupported claims; the core argument is
     correctly qualified.
  4  Minimal. All central claims qualified; at most one minor unqualified
     peripheral assertion.
  5  None. Every claim is derived, marked, or attributed; epistemic status is
     consistent throughout.

s — STRUCTURE COHERENCE (1-5)
  1  No discernible structure; arbitrary order; no logical connections stated.
  2  Minimal; some grouping, transitions absent, dependencies implied not stated.
  3  Moderate; major sections identifiable; some dependencies explicit; one gap.
  4  Good; all components present; dependencies explicit; at most one minor
     imprecision.
  5  Complete explicit architecture; every claim traces to a prior element.

c — COMPLETENESS (1-5)
  1  Under 50% of the required elements addressed.
  2  50-74% present.
  3  75-89% present with appropriate depth.
  4  90-99% present; one minor element underdeveloped.
  5  100% addressed at the specified depth; nothing skipped.

Score what is on the page against the rubric. Do not reward length, and do not
reward a response for resembling how you would have written it. Where a level's
boundary condition is not met, assign the lower score.
"""


def load():
    outs = []
    for f in sorted(os.listdir(OUTPUTS)):
        if f.endswith(".jsonl"):
            with open(os.path.join(OUTPUTS, f), encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        try:
                            outs.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
    scores = {}
    for f in sorted(os.listdir(RESULTS)):
        if f.endswith(".csv"):
            with open(os.path.join(RESULTS, f), newline="", encoding="utf-8") as fh:
                for r in csv.DictReader(fh):
                    if r.get("prompt_key"):
                        scores[(r["model_key"], r["prompt_key"], r["task_id"])] = r
    return outs, scores


def do_sample(per_condition=PER_CONDITION, only_h=False):
    sys.path.insert(0, HERE)
    try:
        from tasks.benchmark import TASK_MAP
        from tasks.exp3_tasks import EXP3_TASKS
        for t in EXP3_TASKS:
            TASK_MAP[t["id"]] = t
    except ImportError as e:
        sys.exit(f"cannot load tasks: {e}")

    outs, scores = load()
    pool = defaultdict(list)
    for o in outs:
        key = (o.get("model_key"), o.get("prompt_key"), o.get("task_id"))
        sc = scores.get(key)
        if not sc or sc.get("claude_parse_error") == "True":
            continue
        if not sc.get("claude_hallucination"):
            continue
        text = (o.get("output") or "").strip()
        if len(text) < 200:
            continue
        pool[o["prompt_key"]].append((o, sc))

    rng = random.Random(SEED)
    items = []
    for cond in sorted(pool):
        rows = sorted(pool[cond], key=lambda p: (p[0]["model_key"], p[0]["task_id"]))
        items += rng.sample(rows, min(per_condition, len(rows)))
    rng.shuffle(items)

    os.makedirs(OUT, exist_ok=True)
    form = os.path.join(OUT, "annotation_forms.md")
    key = os.path.join(OUT, "annotation_key.csv")

    with open(form, "w", encoding="utf-8") as fh:
        fh.write("# Annotation set\n\n")
        fh.write(f"{len(items)} responses, presented in random order with model and "
                 "condition removed.\n\n")
        if only_h:
            fh.write("Score each on h using the rubric below, and record the scores in a "
                     "CSV with columns `item,h`. Work through in order; the items are "
                     "shuffled, so consecutive items are unrelated.\n\n")
        else:
            fh.write("Score each on h, s and c using the rubric below, and record them in a "
                     "CSV with columns `item,h,s,c`. Work through in order and do not skip "
                     "ahead; the items are shuffled, so consecutive items are unrelated.\n\n")
        fh.write("Do not open `annotation_key.csv` until you have finished.\n\n")
        fh.write("A caveat this design cannot remove: some responses carry visible "
                 "formatting — bracketed field labels, tag lines, JSON — that reveals "
                 "which prompt condition produced them. That formatting is part of what "
                 "is being scored and cannot be stripped without changing the object. "
                 "Score the content against the rubric and try not to let the presence "
                 "or absence of visible structure substitute for judging whether the "
                 "rubric’s conditions are met; the analysis reports this as a known "
                 "limit either way.\n\n")
        rub = RUBRIC.strip()
        if only_h:
            rub = rub[:rub.index("s \u2014 STRUCTURE")].strip() + "\n\n" + rub[rub.index("Score what is on the page"):]
        fh.write("## Rubric\n```\n" + rub + "\n```\n\n---\n\n")
        for n, (o, sc) in enumerate(items, start=1):
            task = TASK_MAP.get(o["task_id"], {})
            fh.write(f"## Item {n}\n\n")
            fh.write(f"**Task type:** {task.get('type','—')}\n\n")
            fh.write("**Task given to the model:**\n\n")
            fh.write("```\n" + (task.get("input", "") or "").strip()[:2000] + "\n```\n\n")
            req = task.get("required_elements")
            if req:
                fh.write("**Required elements:**\n\n")
                for r in req:
                    fh.write(f"- {r}\n")
                fh.write("\n")
            fh.write("**Response:**\n\n")
            fh.write("```\n" + (o.get("output") or "").strip()[:6000] + "\n```\n\n")
            if only_h:
                fh.write(f"**Score:** item {n} — h ___\n\n---\n\n")
            else:
                fh.write(f"**Scores:** item {n} — h ___  s ___  c ___\n\n---\n\n")

    with open(key, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["item", "model", "condition", "task",
                    "claude_h", "claude_s", "claude_c",
                    "gpt4o_h", "gpt4o_s", "gpt4o_c"])
        for n, (o, sc) in enumerate(items, start=1):
            w.writerow([n, o["model_key"], o["prompt_key"], o["task_id"],
                        sc.get("claude_hallucination"), sc.get("claude_structure"),
                        sc.get("claude_completeness"),
                        sc.get("gpt4o_hallucination"), sc.get("gpt4o_structure"),
                        sc.get("gpt4o_completeness")])

    print()
    print(f"  {len(items)} items written")
    print(f"    forms : {form}")
    print(f"    key   : {key}   (do not open before annotating)")
    print()
    print("  by condition:")
    cnt = defaultdict(int)
    for o, _ in items:
        cnt[o["prompt_key"]] += 1
    for c in sorted(cnt):
        print(f"    {c:16} {cnt[c]}")
    print()
    print("  Record annotations as a CSV with columns: item,h,s,c")
    print("  Then: python analysis/human_validation.py score <that file>")
    print()


def qwk(a, b, lo=1, hi=5):
    """Quadratic-weighted Cohen's kappa."""
    n = len(a)
    k = hi - lo + 1
    O = [[0]*k for _ in range(k)]
    for x, y in zip(a, b):
        O[int(x)-lo][int(y)-lo] += 1
    ha = [0]*k; hb = [0]*k
    for x in a: ha[int(x)-lo] += 1
    for y in b: hb[int(y)-lo] += 1
    num = den = 0.0
    for i in range(k):
        for j in range(k):
            w = ((i-j)**2)/((k-1)**2)
            num += w*O[i][j]
            den += w*ha[i]*hb[j]/n
    return 1 - num/den if den else float("nan")


def do_score(path):
    key = os.path.join(OUT, "annotation_key.csv")
    if not os.path.exists(key):
        sys.exit(f"no key at {key} — run `sample` first")
    K = {int(r["item"]): r for r in csv.DictReader(open(key, encoding="utf-8"))}
    H = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            try:
                H[int(r["item"])] = {d: float(r[d]) for d in ("h", "s", "c") if r.get(d)}
            except (ValueError, KeyError):
                continue
    common = sorted(set(K) & set(H))
    if not common:
        sys.exit("no items matched between the key and the annotations")

    print()
    print("=" * 74)
    print(f"  HUMAN VALIDATION — {len(common)} annotated items")
    print("=" * 74)
    try:
        from scipy.stats import spearmanr
    except ImportError:
        spearmanr = None

    for dim, ck, gk in [("h", "claude_h", "gpt4o_h"),
                        ("s", "claude_s", "gpt4o_s"),
                        ("c", "claude_c", "gpt4o_c")]:
        rows = [(H[i][dim], K[i][ck], K[i][gk]) for i in common
                if dim in H[i] and K[i][ck] and K[i][gk]]
        if len(rows) < 5:
            continue
        hum = [r[0] for r in rows]
        print()
        print(f"  {dim}   n = {len(rows)}   human mean {mean(hum):.2f}")
        print(f"    {'judge':10}{'mean':>7}{'bias':>8}{'exact':>8}{'within 1':>10}"
              f"{'rho':>8}{'QWK':>8}")
        for label, idx in [("Claude", 1), ("GPT-4o", 2)]:
            jud = [float(r[idx]) for r in rows]
            bias = mean(jud) - mean(hum)
            exact = sum(1 for a, b in zip(hum, jud) if a == b)/len(rows)
            near = sum(1 for a, b in zip(hum, jud) if abs(a-b) <= 1)/len(rows)
            rho = spearmanr(hum, jud).statistic if spearmanr else float("nan")
            print(f"    {label:10}{mean(jud):7.2f}{bias:+8.2f}{100*exact:7.0f}%"
                  f"{100*near:9.0f}%{rho:8.2f}{qwk(hum, jud):8.2f}")

    print()
    print("  Reading. Bias is the judge's mean minus the human's: a positive value")
    print("  is leniency, not noise, and a large positive bias for one judge with a")
    print("  small one for the other is the saturation pattern of §4.3 seen from")
    print("  outside. Rank correlation says whether the judge orders responses as a")
    print("  human does even where the absolute level differs; that is the property")
    print("  the comparative results in this paper depend on.")
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["sample", "score"])
    ap.add_argument("annotations", nargs="?")
    ap.add_argument("--per-condition", type=int, default=PER_CONDITION)
    ap.add_argument("--h-only", action="store_true",
                    help="score only the hallucination dimension")
    a = ap.parse_args()
    if a.mode == "sample":
        do_sample(a.per_condition, a.h_only)
    else:
        if not a.annotations:
            sys.exit("usage: human_validation.py score <annotations.csv>")
        do_score(a.annotations)


if __name__ == "__main__":
    main()
