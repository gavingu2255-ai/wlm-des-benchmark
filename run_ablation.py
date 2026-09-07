#!/usr/bin/env python3
"""
run_ablation.py — marker-ablation experiment (Baseline C)

Separates two things the main study conflated: whether the structural shape
design bundled together:

    WLM-Hybrid v2.2  =  epistemic marking requirement  +  three-layer scaffold
    Baseline C       =  epistemic marking requirement
    Baseline A       =  neither

    h(base_c) - h(base_a)   ->  contribution of the marking instruction
    h(hybrid) - h(base_c)   ->  contribution of the layer scaffold

Also addresses objection 4 (single run per condition) by repeating every
condition and reporting run-to-run spread.

WHY EVERYTHING RUNS IN ONE BATCH
--------------------------------
Baseline A and WLM-Hybrid v2.2 are re-run here rather than read from the May
2026 CSVs. Those were produced against different model snapshots — the June
batch in this project used claude-sonnet-4-5 where May used claude-sonnet-4,
gpt-5.4-mini where May used gpt-4o-mini, qwen3.6 where May used qwen2.5:7b.
Comparing a June Baseline C against a May Hybrid would confound the ablation
with model drift. Same session, same snapshots, or the result means nothing.

Place this file in the repository root, next to runner.py.

    python run_ablation.py --dry-run
    python run_ablation.py --models claude,gpt-4o,gemma-4b --repeats 3

Output:
    data/results/ablation_<timestamp>.csv     one row per (model, prompt, task, run)
    data/outputs/ablation_<timestamp>.jsonl   full agent outputs and judge payloads
"""

import argparse
import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from config import MODELS, RESULTS_DIR, OUTPUTS_DIR
from prompts import get_prompt
from models.caller import call_model
from scoring.judge import score_output


# ── Task loading ──────────────────────────────────────────────────────────────
# In this checkout every task lives under tasks/: benchmark.py holds T01-T37 and
# exp3_tasks.py holds T38-T52. Both are merged here.

from tasks.benchmark import TASK_MAP as _T1_37
from tasks.exp3_tasks import EXP3_TASKS as _T38_52

TASK_MAP = dict(_T1_37)
for _t in _T38_52:
    TASK_MAP[_t["id"]] = _t


# ── Conditions ────────────────────────────────────────────────────────────────

CONDITIONS = ["wlm_hybrid_v2", "base_a", "base_b", "base_c", "base_d"]

# All four conditions are single-pass and share the model's output budget.
#
# This was not always so. An earlier Baseline C emitted a draft, an audit and a
# revised answer, of which only the third was scored, and needed a larger budget
# to avoid truncating the part that counted. That design was withdrawn — its
# audit questions restated ICC-1 and the D-layer, making it a variant of the
# protocol under test rather than an alternative to it. Chain-of-Verification was
# considered as its replacement and rejected because its Factored form requires
# four independent calls; a baseline with four times the inference budget is not
# a comparison.
#
# The current conditions are budget-matched by construction, so no per-condition
# override is needed.
CONDITION_MAX_TOKENS = {}

DEFAULT_MODELS = ["claude", "gpt-4o", "gemini-pro", "gemma-4b"]

# All T-series tasks that exist in this repository.
# T01-T07 (Exp1), T08-T37 (Exp2), and the eight selected Exp3 tasks.
# The published Experiment 3 evaluated eight of the fifteen stress tasks. The
# ablation runs all fifteen. Two reasons: it removes the selection concern raised
# for replication, and T46-T49 are all high_structural_load — the main study
# evaluated only T46, so that category rested on a single task and could not
# support a category-level claim. Four gives it one.
EXP3_PUBLISHED = ["T38", "T41", "T42", "T44", "T46", "T50", "T51", "T52"]


def default_tasks():
    ids = [f"T{n:02d}" for n in range(1, 53)]
    return [t for t in ids if t in TASK_MAP]


CSV_FIELDS = [
    "run_index", "batch_id", "task_id", "task_type",
    "model_key", "model_id", "prompt_key",
    "claude_structure", "claude_hallucination", "claude_completeness",
    "claude_token_efficiency", "claude_parse_error",
    "gpt4o_structure", "gpt4o_hallucination", "gpt4o_completeness",
    "gpt4o_token_efficiency", "gpt4o_parse_error",
    "agreement_structure_diff", "agreement_hallucination_diff",
    "agreement_completeness_diff", "agreement_mean_diff", "agreement_exact_match",
    "output_tokens", "total_tokens", "latency_s", "api",
]


def flatten(result, scores, run_index, batch_id):
    row = {
        "run_index": run_index,
        "batch_id": batch_id,
        "task_id": result.get("task_id", ""),
        "task_type": result.get("task_type", ""),
        "model_key": result.get("model_key", ""),
        "model_id": result.get("model_id", ""),
        "prompt_key": result.get("prompt_key", ""),
        "output_tokens": result.get("output_tokens", 0),
        "total_tokens": result.get("total_tokens", 0),
        "latency_s": result.get("latency_s", 0),
        "api": result.get("api", ""),
    }
    for judge in ["claude", "gpt4o"]:
        js = scores.get("scores_by_judge", {}).get(judge, {})
        for dim in ["structure", "hallucination", "completeness", "token_efficiency"]:
            row[f"{judge}_{dim}"] = js.get(dim, "")
        row[f"{judge}_parse_error"] = js.get("parse_error", True)
    ag = scores.get("agreement", {})
    row["agreement_structure_diff"] = ag.get("structure_diff", "")
    row["agreement_hallucination_diff"] = ag.get("hallucination_diff", "")
    row["agreement_completeness_diff"] = ag.get("completeness_diff", "")
    row["agreement_mean_diff"] = ag.get("mean_diff", "")
    row["agreement_exact_match"] = ag.get("exact_match", "")
    return row


def already_done(csv_path):
    """Return the set of (run_index, model, prompt, task) already written."""
    done = set()
    if not csv_path.exists():
        return done
    with open(csv_path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            done.add((r.get("run_index"), r.get("model_key"),
                      r.get("prompt_key"), r.get("task_id")))
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default=",".join(DEFAULT_MODELS),
                    help="comma-separated model keys, or 'all'")
    ap.add_argument("--tasks", default="",
                    help="comma-separated task ids; default = all T-series available")
    ap.add_argument("--repeats", type=int, default=3,
                    help="runs per condition (addresses R1 objection 4)")
    ap.add_argument("--conditions", default=",".join(CONDITIONS))
    ap.add_argument("--resume", default="",
                    help="path to an existing ablation CSV to continue")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the plan and exit without calling any API")
    ap.add_argument("--sleep", type=float, default=0.5)
    args = ap.parse_args()

    models = list(MODELS.keys()) if args.models == "all" else \
        [m.strip() for m in args.models.split(",")]
    for m in models:
        if m not in MODELS:
            sys.exit(f"unknown model key: {m}   (available: {', '.join(MODELS)})")

    if args.tasks:
        tasks = [t.strip() for t in args.tasks.split(",")]
        missing = [t for t in tasks if t not in TASK_MAP]
        if missing:
            sys.exit(f"task definitions not found for: {', '.join(missing)}\n"
                     "See the task-coverage note printed above.")
    else:
        tasks = default_tasks()

    conditions = [c.strip() for c in args.conditions.split(",")]

    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    total = len(models) * len(conditions) * len(tasks) * args.repeats

    print()
    print("=" * 74)
    print("  MARKER-ABLATION EXPERIMENT")
    print("=" * 74)
    print(f"  batch id   : {batch_id}")
    print(f"  models     : {', '.join(models)}")
    for m in models:
        print(f"                 {m:14} -> {MODELS[m]['model_id']}")
    print(f"  conditions : {', '.join(conditions)}")
    print(f"  tasks      : {len(tasks)}  ({tasks[0]} .. {tasks[-1]})")
    print(f"  repeats    : {args.repeats}")
    print(f"  generations: {total}       judge calls: {total * 2}")
    print("  note       : all conditions single-pass, sharing the model output budget")
    print("=" * 74)

    if args.dry_run:
        print("\n  dry run — nothing called. Remove --dry-run to execute.\n")
        return

    out_dir = OUTPUTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = Path(args.resume) if args.resume else RESULTS_DIR / f"ablation_{batch_id}.csv"
    jsonl_path = out_dir / f"ablation_{batch_id}.jsonl"

    done = already_done(csv_path)
    if done:
        print(f"\n  resuming: {len(done)} rows already present in {csv_path.name}\n")

    new_file = not csv_path.exists()
    csv_fh = open(csv_path, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(csv_fh, fieldnames=CSV_FIELDS)
    if new_file:
        writer.writeheader()
    jsonl_fh = open(jsonl_path, "a", encoding="utf-8")

    n = 0
    t0 = time.time()
    errors = 0
    truncated = 0

    # Interleave conditions within each task so that any drift during the run
    # affects all three conditions equally rather than one of them.
    for run_index in range(1, args.repeats + 1):
        for model_key in models:
            for task_id in tasks:
                task = TASK_MAP[task_id]
                for prompt_key in conditions:
                    n += 1
                    key = (str(run_index), model_key, prompt_key, task_id)
                    if key in done:
                        continue

                    label = f"r{run_index} {model_key}/{prompt_key}/{task_id}"
                    elapsed = time.time() - t0
                    eta = (elapsed / max(n, 1)) * (total - n)
                    print(f"  [{n:04d}/{total}] {label:<44} ETA {eta/60:5.1f}m ",
                          end="", flush=True)

                    prompt = get_prompt(
                        prompt_key,
                        task_injection=task.get("injection", ""),
                        hybrid_injection=task.get("hybrid_injection", ""),
                    )

                    result = call_model(
                        model_key=model_key,
                        system=prompt,
                        user_input=task["input"],
                        max_tokens=CONDITION_MAX_TOKENS.get(prompt_key),
                    )
                    result["task_id"] = task_id
                    result["task_type"] = task["type"]
                    result["prompt_key"] = prompt_key

                    if "error" in result:
                        print(f"AGENT ERROR: {result['error'][:44]}")
                        errors += 1
                        jsonl_fh.write(json.dumps(
                            {**result, "run_index": run_index, "batch_id": batch_id},
                            ensure_ascii=False) + "\n")
                        jsonl_fh.flush()
                        continue

                    try:
                        scores = score_output(task, result)
                        cj = scores.get("scores_by_judge", {}).get("claude", {})
                        gj = scores.get("scores_by_judge", {}).get("gpt4o", {})
                        ag = scores.get("agreement", {})
                        c_bad = "!" if cj.get("parse_error", True) else " "
                        g_bad = "!" if gj.get("parse_error", True) else " "
                        print(
                            f"C[s={cj.get('structure',0):.0f} h={cj.get('hallucination',0):.0f} "
                            f"c={cj.get('completeness',0):.0f} \u03b7={cj.get('token_efficiency',0):.3f}]{c_bad}"
                            f"G[s={gj.get('structure',0):.0f} h={gj.get('hallucination',0):.0f} "
                            f"c={gj.get('completeness',0):.0f}]{g_bad}"
                            f"\u0394h={ag.get('hallucination_diff','?')} tok={result.get('output_tokens',0)}"
                        )
                    except Exception as e:
                        print(f"JUDGE ERROR: {e}")
                        errors += 1
                        scores = {"scores_by_judge": {}, "agreement": {}}

                    # Flag outputs that hit the token cap: the response is truncated
                    # and whatever the judge scored is incomplete.
                    cap = CONDITION_MAX_TOKENS.get(
                        prompt_key, MODELS[model_key].get("max_tokens", 2048))
                    if result.get("output_tokens", 0) >= cap:
                        truncated += 1
                        print(f"        ^ TRUNCATED at {cap} tokens \u2014 scored text is incomplete")

                    jsonl_fh.write(json.dumps(
                        {**result, "run_index": run_index, "batch_id": batch_id,
                         "scores": scores},
                        ensure_ascii=False) + "\n")
                    writer.writerow(flatten(result, scores, run_index, batch_id))
                    jsonl_fh.flush()
                    csv_fh.flush()
                    time.sleep(args.sleep)

    csv_fh.close()
    jsonl_fh.close()

    print()
    print(f"  scores  -> {csv_path}")
    print(f"  outputs -> {jsonl_path}")
    print(f"  errors  : {errors}")
    if truncated:
        print(f"  TRUNCATED: {truncated} output(s) hit the token cap \u2014 "
              f"those rows are not usable")
    print()
    print(f"  next:  python analysis/analyze_ablation.py {csv_path}")
    print()


if __name__ == "__main__":
    main()
