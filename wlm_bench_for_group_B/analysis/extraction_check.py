#!/usr/bin/env python3
"""
extraction_check.py — is the s/c deficit a protocol effect or a presentation artefact?

    python analysis/extraction_check.py data/outputs/ablation_<batch>.jsonl
    python analysis/extraction_check.py <jsonl> --tasks 20 --dry-run

THE PROBLEM
-----------
In the 2 August pilot, WLM-Hybrid v2.2 beat both baselines on hallucination
suppression and lost to plain-prose uncertainty prompting on structure coherence
and completeness, on both models. Before that is reported as a property of the
protocol, one alternative has to be ruled out: the judge does not see the same
kind of text across conditions.

_extract_scorable_text() flattens Hybrid's seven fields into labelled prose —
[DEFINITIONS] … [MAPPINGS] … [EPISTEMICS] … — while base_d arrives as an ordinary
continuous answer. A rubric scoring "structure coherence" and "completeness" may
prefer continuous prose to labelled fragments for reasons unrelated to what the
protocol does.

Two confounds are tangled here, and they pull in opposite directions:

  (1) Labelling. Bracketed field markers may read as fragmentation rather than
      as structure.
  (2) Scaffolding. The flattened text includes definitions, mappings, epistemics
      and a completeness check — working material, not the answer. base_d
      produces an answer. Scoring scaffolding against an answer may penalise the
      condition that shows its work.

THE DESIGN
----------
Three renderings of the same Hybrid output, re-scored by both judges. Content is
never altered; only what the judge is shown changes.

  A  labelled     what the pipeline does now: seven fields, bracketed labels
  B  prose        same seven fields, labels removed, joined as paragraphs
  C  answer-only  the final_answer field alone

Readings:

  B > A on s/c      labelling is the artefact — fix the extractor
  C > A on s/c      including scaffolding is the artefact — score final_answer
  A ≈ B ≈ C         no artefact; the deficit is a real property of the protocol
  h stable across   presentation affects s/c but not h, which is what the
                    conditions      pilot's main result depends on

The last is the one to watch. If h moves as much as s and c, the whole metric is
presentation-sensitive and the pilot's headline result is in question too.

NOTE ON JUDGE RULE 7
--------------------
Strictness rule 7 fires only when the response contains a [COMPLETENESS CHECK]
section, and it caps completeness at 3 unless that section carries at least three
specific checks. Renderings B and C remove the marker, so the rule cannot fire on
them. This is itself part of what the check measures: the rule is a penalty that
applies to Hybrid and to no other condition, and if it accounts for the c deficit
that is worth knowing. The per-rendering completeness figures below separate the
two possibilities — if c rises in B by roughly the amount rule 7 could deduct, the
rule is doing the work.
"""

import argparse
import json
import os
import random
import re
import sys
from collections import defaultdict
from statistics import mean

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

HYBRID_FIELDS = ["definitions", "structure", "mappings", "examples",
                 "epistemics", "completeness_check", "final_answer"]
LABELS = {f: f.upper().replace("_", " ") for f in HYBRID_FIELDS}


def strip_fences(t):
    t = (t or "").strip()
    if t.startswith("```"):
        lines = t.split("\n")[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    if not t.startswith("{"):
        i, j = t.find("{"), t.rfind("}")
        if i != -1 and j > i:
            t = t[i:j + 1]
    return t


def render(data, mode):
    """Three renderings of the same field content."""
    if mode == "A":
        parts = [f"[{LABELS[f]}] {data[f]}" for f in HYBRID_FIELDS if data.get(f)]
        return "\n\n".join(parts)
    if mode == "B":
        # Same fields, same order, labels removed. Sentence-cased joins so the
        # result reads as continuous prose rather than a stripped list.
        parts = [str(data[f]).strip() for f in HYBRID_FIELDS if data.get(f)]
        return "\n\n".join(parts)
    if mode == "C":
        return str(data.get("final_answer", "")).strip()
    raise ValueError(mode)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default=None,
                    help="ablation jsonl; defaults to the newest in data/runs/outputs")
    ap.add_argument("--tasks", type=int, default=20,
                    help="how many tasks to sample per model (default 20)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--csv", metavar="FILE")
    args = ap.parse_args()

    path = args.path
    if path is None:
        import glob
        cands = sorted(glob.glob(os.path.join(HERE, "data", "runs", "outputs",
                                              "ablation_*.jsonl")))
        if not cands:
            sys.exit("no ablation jsonl found in data/runs/outputs; pass one explicitly")
        path = cands[-1]
        print(f"  using {os.path.basename(path)}")

    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("prompt_key") != "wlm_hybrid_v2" or not r.get("output"):
                continue
            try:
                data = json.loads(strip_fences(r["output"]))
            except Exception:
                continue
            if not data.get("final_answer"):
                continue
            r["_data"] = data
            rows.append(r)

    if not rows:
        sys.exit("no parseable wlm_hybrid_v2 outputs found")

    by_model = defaultdict(list)
    for r in rows:
        by_model[r.get("model_key", "?")].append(r)

    rng = random.Random(args.seed)
    sample = []
    for m, rs in sorted(by_model.items()):
        rs = sorted(rs, key=lambda r: r.get("task_id", ""))
        sample += rng.sample(rs, min(args.tasks, len(rs)))

    print()
    print("=" * 84)
    print("  EXTRACTION CHECK")
    print(f"  {len(rows)} parseable Hybrid outputs; sampling {len(sample)}")
    for m, rs in sorted(by_model.items()):
        print(f"    {m:14} {len(rs):3} available, "
              f"{min(args.tasks, len(rs)):3} sampled")
    print(f"  3 renderings x {len(sample)} outputs x 2 judges "
          f"= {len(sample) * 6} judge calls")
    print("=" * 84)

    if args.dry_run:
        print("\n  dry run. Sample rendering of the first output:\n")
        d = sample[0]["_data"]
        for mode, name in [("A", "labelled"), ("B", "prose"), ("C", "answer-only")]:
            txt = render(d, mode)
            print(f"  --- {mode} {name} ({len(txt)} chars) ---")
            print("  " + txt[:220].replace("\n", "\n  "))
            print()
        return

    from scoring.judge import _build_prompt, _parse_judge_response, JUDGE_SYSTEM
    from models.caller import call_model
    from config import JUDGES

    try:
        from tasks.benchmark import TASK_MAP
        from tasks.exp3_tasks import EXP3_TASKS
        for t in EXP3_TASKS:
            TASK_MAP[t["id"]] = t
    except ImportError as e:
        sys.exit(f"could not load tasks: {e}")

    out = []
    n = 0
    total = len(sample) * 3
    for r in sample:
        task = TASK_MAP.get(r.get("task_id"))
        if not task:
            continue
        for mode in ["A", "B", "C"]:
            n += 1
            text = render(r["_data"], mode)
            if len(text) < 20:
                continue
            fake = {**r, "output": text, "prompt_key": "base_a"}  # pass through
            prompt = _build_prompt(task, fake)
            rec = {"model": r["model_key"], "task": r["task_id"], "mode": mode,
                   "chars": len(text)}
            for jk in JUDGES:
                try:
                    resp = call_model(model_key=jk, system=JUDGE_SYSTEM,
                                      user_input=prompt, registry=JUDGES)
                    p = _parse_judge_response(resp["output"])
                except Exception as e:
                    p = {"structure": 0, "hallucination": 0, "completeness": 0,
                         "parse_error": True}
                for dim in ["structure", "hallucination", "completeness"]:
                    rec[f"{jk}_{dim[0]}"] = p.get(dim, 0)
                rec[f"{jk}_err"] = p.get("parse_error", True)
            out.append(rec)
            print(f"  [{n:03d}/{total}] {r['model_key']:10} {r['task_id']:5} {mode}  "
                  f"C[s={rec.get('claude_s','?')} h={rec.get('claude_h','?')} "
                  f"c={rec.get('claude_c','?')}]  "
                  f"G[s={rec.get('gpt4o_s','?')} h={rec.get('gpt4o_h','?')} "
                  f"c={rec.get('gpt4o_c','?')}]  {len(text)}ch")

    good = [r for r in out if not r.get("claude_err")]

    print()
    print("=" * 84)
    print("  RESULTS  (Claude judge, paired by task)")
    print("=" * 84)
    print(f"  {'model':12}{'rendering':14}{'n':>4}{'s':>7}{'c':>7}{'h':>7}{'chars':>8}")
    for m in sorted({r["model"] for r in good}):
        for mode, name in [("A", "labelled"), ("B", "prose"), ("C", "answer-only")]:
            v = [r for r in good if r["model"] == m and r["mode"] == mode]
            if not v:
                continue
            print(f"  {m:12}{name:14}{len(v):4}"
                  f"{mean([r['claude_s'] for r in v]):7.2f}"
                  f"{mean([r['claude_c'] for r in v]):7.2f}"
                  f"{mean([r['claude_h'] for r in v]):7.2f}"
                  f"{mean([r['chars'] for r in v]):8.0f}")
        print()

    print("  Paired differences against rendering A")
    print(f"  {'model':12}{'comparison':16}{'n':>4}{'Δs':>8}{'Δc':>8}{'Δh':>8}")
    for m in sorted({r["model"] for r in good}):
        base = {r["task"]: r for r in good if r["model"] == m and r["mode"] == "A"}
        for mode, name in [("B", "prose - A"), ("C", "answer - A")]:
            alt = {r["task"]: r for r in good if r["model"] == m and r["mode"] == mode}
            ts = sorted(set(base) & set(alt))
            if not ts:
                continue
            ds = mean([alt[t]["claude_s"] - base[t]["claude_s"] for t in ts])
            dc = mean([alt[t]["claude_c"] - base[t]["claude_c"] for t in ts])
            dh = mean([alt[t]["claude_h"] - base[t]["claude_h"] for t in ts])
            print(f"  {m:12}{name:16}{len(ts):4}{ds:+8.2f}{dc:+8.2f}{dh:+8.2f}")

    print()
    print("  Reading. A positive Δs or Δc means the current extraction was")
    print("  depressing that score — the deficit against plain-prose baselines is")
    print("  an artefact of presentation, not a property of the protocol. A Δh")
    print("  near zero means hallucination suppression is presentation-stable and")
    print("  the pilot's main result stands. A large Δh means it does not.")
    print()

    if args.csv:
        import csv as _csv
        d = os.path.dirname(args.csv)
        if d:
            os.makedirs(d, exist_ok=True)
        keys = sorted({k for r in out for k in r})
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            w = _csv.DictWriter(fh, fieldnames=keys)
            w.writeheader()
            w.writerows(out)
        print(f"  wrote {args.csv}")
        print()


if __name__ == "__main__":
    main()
