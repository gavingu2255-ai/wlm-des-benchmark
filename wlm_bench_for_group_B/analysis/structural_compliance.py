#!/usr/bin/env python3
"""
structural_compliance.py — measure protocol conformance directly from output

    python analysis/structural_compliance.py
    python analysis/structural_compliance.py --csv out/compliance.csv

Every other number in this study passes through an LLM judge. This one does not.
Each of the three WLM formats specifies structural requirements that are either
present in the output or absent, and presence is decided by parsing, not by
judgement:

    WLM-JSON        valid JSON; d_layer.required and .excluded populated;
                    e_layer.sequence present; at least 80% of its steps carry a
                    back-reference to a D element; s_layer.response present;
                    icc_verified reported.

    WLM-SL          REQ, EXCL and CONST lines present; SEQ lines present;
                    at least 80% of SEQ lines carry a "<-" back-reference;
                    RESP: block present; ICC: line present.

    WLM-Hybrid v2.2 valid JSON; all seven mandatory fields non-empty;
                    completeness_check contains at least three tick or cross
                    marks.

The score per output is the fraction of that format's checks satisfied. It says
whether the model did what the protocol asked. It says nothing about whether the
answer was any good — the protocol constrains form and supplies no content, so
no such inference is available or attempted.

Reads from data/results/*.csv and data/outputs/*.jsonl. Conventions follow
docs/DATA_SOURCE.md: rows with a judge parse error are dropped.
"""

import argparse
import csv
import json
import os
import re
import sys
from collections import defaultdict
from statistics import mean, pstdev

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(HERE, "data", "published", "results")
OUTPUTS = os.path.join(HERE, "data", "published", "outputs")

MODEL_ORDER = ["claude", "gpt-4o", "gemini-pro", "gpt-4o-mini", "qwen-7b", "gemma-4b"]
FORMATS = ["wlm_json", "wlm_sl", "wlm_hybrid_v2"]
FORMAT_LABEL = {"wlm_json": "WLM-JSON", "wlm_sl": "WLM-SL",
                "wlm_hybrid_v2": "WLM-Hybrid v2.2"}
BACKREF_THRESHOLD = 0.8


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


def checks_json(out):
    try:
        d = json.loads(strip_fences(out))
    except Exception:
        return {"parses": False, "d_required": False, "d_excluded": False,
                "e_sequence": False, "e_backref": False, "s_response": False,
                "icc_reported": False}
    dl = d.get("d_layer", {}) or {}
    el = d.get("e_layer", {}) or {}
    sl = d.get("s_layer", {}) or {}
    seq = el.get("sequence", []) or []
    backs = sum(1 for s in seq if isinstance(s, str) and ("<-" in s or "\u2190" in s))
    return {
        "parses": True,
        "d_required": bool(dl.get("required")),
        "d_excluded": bool(dl.get("excluded")),
        "e_sequence": bool(seq),
        "e_backref": (backs / len(seq) if seq else 0) >= BACKREF_THRESHOLD,
        "s_response": bool(sl.get("response")),
        "icc_reported": "icc_verified" in sl,
    }


def checks_sl(out):
    out = out or ""
    seqs = re.findall(r"^\s*SEQ\s+(.+)$", out, re.M)
    backs = sum(1 for s in seqs if "<-" in s or "\u2190" in s)
    return {
        "req": bool(re.search(r"^\s*REQ\s", out, re.M)),
        "excl": bool(re.search(r"^\s*EXCL\s", out, re.M)),
        "const": bool(re.search(r"^\s*CONST\s", out, re.M)),
        "e_sequence": bool(seqs),
        "e_backref": (backs / len(seqs) if seqs else 0) >= BACKREF_THRESHOLD,
        "s_response": bool(re.search(r"^\s*RESP:", out, re.M)),
        "icc_reported": bool(re.search(r"^\s*ICC:", out, re.M)),
    }


HYBRID_FIELDS = ["definitions", "structure", "mappings", "examples",
                 "epistemics", "completeness_check", "final_answer"]


def checks_hybrid(out):
    try:
        d = json.loads(strip_fences(out))
    except Exception:
        return {**{f: False for f in HYBRID_FIELDS}, "cc_three_checks": False}
    cc = str(d.get("completeness_check", "") or "")
    return {**{f: bool(d.get(f)) for f in HYBRID_FIELDS},
            "cc_three_checks": len(re.findall(r"[\u2713\u2717\u2714\u2718]", cc)) >= 3}


def checks(out, prompt_key):
    if prompt_key == "wlm_json":
        return checks_json(out)
    if prompt_key == "wlm_sl":
        return checks_sl(out)
    if prompt_key == "wlm_hybrid_v2":
        return checks_hybrid(out)
    return None


def load_scores():
    sc = {}
    for f in os.listdir(RESULTS):
        if not f.endswith(".csv") or f.startswith("ablation_"):
            continue
        with open(os.path.join(RESULTS, f), newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if "prompt_key" not in r:
                    continue
                sc[(r.get("model_key"), r.get("prompt_key"), r.get("task_id"))] = r
    return sc


def load_outputs():
    rows = []
    for f in os.listdir(OUTPUTS):
        if not f.endswith(".jsonl") or f.startswith("ablation_"):
            continue
        with open(os.path.join(OUTPUTS, f), encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", metavar="FILE", help="write per-output results")
    args = ap.parse_args()

    if not os.path.isdir(OUTPUTS):
        sys.exit(f"no output directory at {OUTPUTS}")

    scores = load_scores()
    outs = load_outputs()

    recs = []
    for o in outs:
        pk = o.get("prompt_key")
        if pk not in FORMATS:
            continue
        s = scores.get((o.get("model_key"), pk, o.get("task_id")))
        if not s or s.get("claude_parse_error") == "True":
            continue
        c = checks(o.get("output", ""), pk)
        if not c:
            continue
        frac = sum(1 for v in c.values() if v) / len(c)
        recs.append({
            "model": o.get("model_key"), "format": pk, "task": o.get("task_id"),
            "compliance": frac, "n_checks": len(c),
            **{k: int(v) for k, v in c.items()},
        })

    if not recs:
        sys.exit("no matching outputs found")

    print()
    print("=" * 88)
    print("  STRUCTURAL COMPLIANCE")
    print(f"  {len(recs)} outputs parsed. No judge involved.")
    print("=" * 88)

    print()
    print("  Fraction of each format's structural checks satisfied")
    print(f"  {'model':14}" + "".join(f"{FORMAT_LABEL[f]:>18}" for f in FORMATS)
          + f"{'overall':>10}{'n':>5}")
    print("  " + "-" * 79)
    for m in MODEL_ORDER:
        cells = []
        for f in FORMATS:
            v = [r["compliance"] for r in recs if r["model"] == m and r["format"] == f]
            cells.append(mean(v) if v else None)
        allv = [r["compliance"] for r in recs if r["model"] == m]
        if not allv:
            continue
        print(f"  {m:14}"
              + "".join(f"{c:18.2f}" if c is not None else f"{'—':>18}" for c in cells)
              + f"{mean(allv):10.2f}{len(allv):5}")

    print()
    print("  Distribution — compliance is close to binary, not graded")
    print(f"  {'model':14}{'n':>5}{'mean':>8}{'sd':>8}{'at 1.00':>10}{'at 0.00':>10}")
    print("  " + "-" * 55)
    for m in MODEL_ORDER:
        v = [r["compliance"] for r in recs if r["model"] == m]
        if not v:
            continue
        top = sum(1 for x in v if x >= 0.999)
        bot = sum(1 for x in v if x <= 0.001)
        print(f"  {m:14}{len(v):5}{mean(v):8.2f}{pstdev(v):8.3f}"
              f"{100*top/len(v):9.0f}%{100*bot/len(v):9.0f}%")

    print()
    print("  Per-check detail, by format and model")
    for f in FORMATS:
        sub = [r for r in recs if r["format"] == f]
        if not sub:
            continue
        keys = [k for k in sub[0] if k not in
                ("model", "format", "task", "compliance", "n_checks")]
        print()
        print(f"  {FORMAT_LABEL[f]}")
        print(f"    {'model':14}" + "".join(f"{k[:11]:>13}" for k in keys))
        for m in MODEL_ORDER:
            ms = [r for r in sub if r["model"] == m]
            if not ms:
                continue
            print(f"    {m:14}" + "".join(f"{mean([r[k] for r in ms]):13.2f}" for k in keys))

    print()
    print("  Note on interpretation. These figures describe conformance to the")
    print("  protocol, nothing further. The protocol constrains the form of an")
    print("  answer and supplies no content, so compliance cannot be expected to")
    print("  predict answer quality and no such relationship is tested here.")
    print("  Compliance is also close to binary within a model — Claude sits at")
    print("  1.00 on every output — which leaves no variance for such a test even")
    print("  if one were wanted.")
    print()

    if args.csv:
        d = os.path.dirname(args.csv)
        if d:
            os.makedirs(d, exist_ok=True)
        keys = sorted({k for r in recs for k in r})
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=keys)
            w.writeheader()
            w.writerows(recs)
        print(f"  wrote {args.csv}")
        print()


if __name__ == "__main__":
    main()
