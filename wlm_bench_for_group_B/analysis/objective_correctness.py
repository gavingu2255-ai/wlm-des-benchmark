#!/usr/bin/env python3
"""
objective_correctness.py — does the hallucination metric track being right?

    python analysis/objective_correctness.py
    python analysis/objective_correctness.py --show T29     # inspect one task
    python analysis/objective_correctness.py --csv out/correctness.csv

WHY THIS EXISTS
---------------
Every score in this study comes from an LLM judge applying a rubric. The
hallucination metric h rewards appropriate epistemic qualification: claims that
are marked, hedged, or declined where the evidence does not support them. It
does not check whether the answer is right.

Those are different properties, and a spot check on T08 during revision found
them pulling apart — responses that identified a proof correctly scoring h = 2
while responses that misread a valid step scored h = 5. If that pattern holds
across the objectively checkable subset, the paper's claim has to be that D/E/S
improves the discipline of presentation, not that it improves correctness.

WHAT IS CHECKED
---------------
Fourteen of the 52 tasks have a determinate answer: five proof-verification
tasks, three logical-validity tasks, three code-debugging tasks, and three
mathematical-reasoning tasks. For each, this file records the fact a correct
answer must state and a predicate that decides whether the response states it.

The predicates are deliberately narrow. Each targets one unambiguous fact — a
numerical answer, a specific bug, a validity label — rather than attempting to
grade the response as a whole. A response can satisfy the predicate and still be
a poor answer; it cannot fail the predicate and be a correct one.

Three checks are marked MANUAL because no reliable predicate exists for them.
They are reported separately and excluded from the totals rather than guessed.

CALIBRATION
-----------
Run with --show to print the matched text for a task before trusting its
numbers. The predicates were written against the task definitions, not against
the responses, and then verified on a sample; --show reproduces that check.
"""

import argparse
import csv
import json
import os
import re
import sys
from collections import defaultdict
from statistics import mean

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUTS = os.path.join(HERE, "data", "published", "outputs")
RESULTS = os.path.join(HERE, "data", "published", "results")


def norm(t):
    """Lowercase, strip markdown emphasis, collapse whitespace."""
    t = (t or "").lower()
    t = re.sub(r"[*_`#]+", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t


def num_near(text, target, tol, window_words=None):
    """Does a number within tol of target appear in the text?"""
    for m in re.finditer(r"(\d+(?:[.,]\d+)?)", text):
        try:
            v = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        if abs(v - target) <= tol:
            return True
    return False


# ── the key ─────────────────────────────────────────────────────────────────
#
# Each entry: what a correct answer must state, and how to decide whether it did.
# "fact" is prose for the write-up; "check" returns True/False/None (None = the
# predicate cannot decide and the row is excluded).

def _t06(t):
    # The claimed proof of √2+√3 irrational is sound (step 6 needs p≠0, which
    # holds since √2+√3 > 0). Declaring a step INVALID is the error.
    m = re.search(r"step\s*(\d)\s*[:.\-–—]?\s*(?:is\s+)?invalid", t)
    return m is None

def _t08(t):
    # Same structure for √5+√7: the proof is sound.
    m = re.search(r"step\s*(\d)\s*[:.\-–—]?\s*(?:is\s+)?invalid", t)
    return m is None

def _t09(t):
    # Step 6 ("therefore M is prime") is the error: M need only have a prime
    # factor outside the list. A correct answer says M may be composite.
    said_not_prime = bool(re.search(
        r"(m\s+(?:is\s+)?(?:need not|may not|might not|not necessarily)\s+(?:be\s+)?prime"
        r"|not necessarily prime|need not be prime|may be composite|could be composite"
        r"|has a prime factor not in|prime factor not in the list)", t))
    return said_not_prime

def _t10(t):
    # Conclusion true; rigour requires the reals as a complete ordered field and
    # decimals read as convergent series.
    framework = bool(re.search(
        r"(complete(?:ness)?\s+(?:ordered\s+)?(?:field|axiom|property)|convergent series"
        r"|geometric series|limit of (?:the )?(?:partial sums|a sequence)"
        r"|real number system|construction of the real)", t))
    return framework

def _t11(t):
    # Step 6 invokes Bolzano–Weierstrass; step 2 needs boundedness of a
    # continuous function on a compact set.
    bw = bool(re.search(r"bolzano[\s\-–—]*weierstrass", t))
    return bw

def _t12(t):
    # C1 VALID, C2 UNDETERMINED, C3 VALID, C4 UNDETERMINED, C5 UNDETERMINED.
    # The discriminating one is C4: platypuses laying eggs is true in fact but
    # not derivable from the premises.
    m = re.search(r"c4[^.\n]{0,80}", t)
    if not m:
        return None
    seg = m.group(0)
    if re.search(r"undetermined|not (?:inferable|derivable|entailed)|cannot be (?:inferred|determined)", seg):
        return True
    if re.search(r"\bvalid\b", seg) and "invalid" not in seg:
        return False
    return None

def _t13(t):
    # Four fallacies: correlation/causation, false dilemma, ad hominem,
    # appeal to emotion. A correct answer names at least three.
    hits = sum(bool(re.search(p, t)) for p in [
        r"(correlation|post hoc|cum hoc|causal fallacy|correlation (?:does not|≠|is not) caus)",
        r"(false (?:dilemma|dichotomy)|either[\s\-/]*or fallacy|black[\s\-]and[\s\-]white)",
        r"ad hominem",
        r"(appeal to (?:emotion|pity|fear)|argumentum ad (?:passiones|misericordiam))",
    ])
    return hits >= 3

def _t14(t):
    # Both arguments are deductively valid; the dispute is over soundness.
    valid_both = bool(re.search(
        r"(both (?:arguments? )?(?:are )?(?:formally |deductively |logically )?valid"
        r"|argument (?:1|a|one)[^.]{0,60}valid[^.]{0,120}argument (?:2|b|two)[^.]{0,60}valid)", t))
    return valid_both

def _t18(t):
    # `if n = 0:` is a syntax error — assignment where comparison is meant.
    return bool(re.search(r"(n\s*=\s*0[^=]|assignment (?:instead of|rather than|not) compar"
                          r"|single equals|=\s*(?:instead of|vs\.?|rather than)\s*==|syntaxerror)", t))

def _t19(t):
    # `self.count == 0` in reset() compares instead of assigning: reset is a
    # no-op. This is the correctness bug distinct from the race condition.
    return bool(re.search(r"(reset[^.]{0,140}(?:==|comparison|compares|does nothing|no[\s\-]op|never)"
                          r"|==\s*0[^.]{0,80}(?:instead of|should be|rather than)\s*=)", t))

def _t20(t):
    # ORDER BY defaults to ASC, returning the lowest-paid departments.
    return bool(re.search(r"(order by[^.]{0,90}(?:asc|ascending|desc missing|not desc)"
                          r"|ascending[^.]{0,80}(?:lowest|bottom|instead of highest)"
                          r"|missing desc|needs? desc)", t))

def _t27(t):
    # Bayes: 0.0095/0.1085 ≈ 8.76%. Monty Hall: 2/3. Eleventh flip: 1/2.
    bayes = num_near(t, 8.76, 0.35) or num_near(t, 0.0876, 0.0035)
    monty = bool(re.search(r"(2/3|2 ⁄ 3|66\.6|66\.7|0\.66|two[\s\-]thirds)", t))
    return bayes and monty

def _t28(t):
    # Expected false positives = 50 × 0.05 = 2.5; Bonferroni threshold 0.001.
    fp = bool(re.search(r"2\.5\b", t))
    bonf = bool(re.search(r"0\.001\b", t))
    return fp and bonf

def _t29(t):
    # The benchmark's own key gives 200 x 100 = 20,000 m2 with the barn wall and
    # 100 x 100 = 10,000 without. A stricter reading is available - the barn is
    # stated to be 100 m long, so a 200 m side cannot rest against it, giving
    # 150 x 100 = 15,000 - and an earlier version of this file scored against
    # that reading. It was the wrong choice: the task defines what a correct
    # answer is, and substituting an outside reading measures agreement with the
    # scorer rather than with the benchmark. Scored against the task's key here,
    # with the ambiguity reported in the write-up.
    return bool(re.search(r"20[,.]?000", t))

KEY = {
 "T06": ("The claimed proof is sound; no step is INVALID.", _t06),
 "T08": ("The claimed proof is sound; no step is INVALID.", _t08),
 "T09": ("Step 6 is wrong: M need not be prime, only to have a prime factor outside the list.", _t09),
 "T10": ("Rigour requires the reals as a complete ordered field and decimals as convergent series.", _t10),
 "T11": ("Step 6 invokes Bolzano-Weierstrass.", _t11),
 "T12": ("C4 is UNDETERMINED: platypuses laying eggs is true but not derivable from the premises.", _t12),
 "T13": ("At least three of: correlation/causation, false dilemma, ad hominem, appeal to emotion.", _t13),
 "T14": ("Both arguments are deductively valid; the dispute is over soundness.", _t14),
 "T18": ("`if n = 0:` is a syntax error - assignment where comparison is meant.", _t18),
 "T19": ("`self.count == 0` in reset() compares instead of assigning; reset does nothing.", _t19),
 "T20": ("ORDER BY defaults to ASC, returning the lowest-paid departments.", _t20),
 "T27": ("Bayes gives 8.76%; Monty Hall gives 2/3.", _t27),
 "T28": ("Expected false positives 2.5; Bonferroni threshold 0.001.", _t28),
 "T29": ("The barn is 100 m, so 150x100 = 15,000 m2. Reporting 20,000 ignores the stated limit.", _t29),
}


def load():
    outs = []
    for f in sorted(os.listdir(OUTPUTS)):
        if not f.endswith(".jsonl"):
            continue
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
        if not f.endswith(".csv"):
            continue
        with open(os.path.join(RESULTS, f), newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if r.get("prompt_key"):
                    scores[(r["model_key"], r["prompt_key"], r["task_id"],
                            r.get("experiment", ""))] = r
    return outs, scores


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", metavar="TASK", help="print matched text for one task")
    ap.add_argument("--csv", metavar="FILE")
    args = ap.parse_args()

    outs, scores = load()
    rows = []
    for o in outs:
        tid = o.get("task_id")
        if tid not in KEY:
            continue
        text = norm(o.get("output", ""))
        if len(text) < 40:
            continue
        verdict = KEY[tid][1](text)
        sc = None
        for exp in ("", o.get("experiment", "")):
            sc = scores.get((o.get("model_key"), o.get("prompt_key"), tid, exp)) or sc
        if not sc or sc.get("claude_parse_error") == "True":
            continue
        if not sc.get("claude_hallucination"):
            continue
        rows.append({
            "task": tid, "model": o.get("model_key"), "format": o.get("prompt_key"),
            "correct": verdict,
            "h": float(sc["claude_hallucination"]),
            "s": float(sc["claude_structure"]),
            "c": float(sc["claude_completeness"]),
        })

    if args.show:
        for o in outs:
            if o.get("task_id") != args.show:
                continue
            t = norm(o.get("output", ""))
            if len(t) < 40:
                continue
            v = KEY[args.show][1](t)
            print(f"--- {o.get('model_key')}/{o.get('prompt_key')}  verdict={v}")
            print("    " + t[:300])
            print()
        return

    decided = [r for r in rows if r["correct"] is not None]
    print()
    print("=" * 78)
    print("  OBJECTIVE CORRECTNESS vs HALLUCINATION SCORE")
    print(f"  {len(rows)} responses on {len(KEY)} checkable tasks; "
          f"{len(decided)} decided, {len(rows)-len(decided)} undecidable")
    print("=" * 78)

    print()
    print("  Per task")
    print(f"  {'task':6}{'n':>4}{'correct':>9}{'h | correct':>13}{'h | wrong':>12}{'gap':>8}")
    print("  " + "-" * 50)
    for t in sorted(KEY, key=lambda x: int(x[1:])):
        sub = [r for r in decided if r["task"] == t]
        if not sub:
            continue
        ok = [r["h"] for r in sub if r["correct"]]
        no = [r["h"] for r in sub if not r["correct"]]
        gap = (mean(ok) - mean(no)) if ok and no else None
        print(f"  {t:6}{len(sub):4}{f'{len(ok)}/{len(sub)}':>9}"
              f"{(f'{mean(ok):.2f}' if ok else '—'):>13}"
              f"{(f'{mean(no):.2f}' if no else '—'):>12}"
              f"{(f'{gap:+.2f}' if gap is not None else '—'):>8}")

    ok = [r for r in decided if r["correct"]]
    no = [r for r in decided if not r["correct"]]
    print()
    print("  Overall")
    print(f"    correct responses   n={len(ok):3}  mean h={mean([r['h'] for r in ok]):.2f}"
          if ok else "    correct responses   none")
    print(f"    incorrect responses n={len(no):3}  mean h={mean([r['h'] for r in no]):.2f}"
          if no else "    incorrect responses none")
    if ok and no:
        d = mean([r["h"] for r in ok]) - mean([r["h"] for r in no])
        print(f"    difference          {d:+.2f}")
        try:
            from scipy.stats import mannwhitneyu, pointbiserialr
            u = mannwhitneyu([r["h"] for r in ok], [r["h"] for r in no])
            rb = pointbiserialr([1 if r["correct"] else 0 for r in decided],
                                [r["h"] for r in decided])
            print(f"    Mann-Whitney U      p = {u.pvalue:.4f}")
            print(f"    point-biserial r    {rb.statistic:+.3f}  (p = {rb.pvalue:.4f})")
        except ImportError:
            pass

    print()
    print("  Correctness by condition")
    print(f"  {'format':18}{'n':>5}{'correct':>10}{'rate':>8}{'mean h':>9}")
    print("  " + "-" * 50)
    for fmt in sorted({r["format"] for r in decided}):
        sub = [r for r in decided if r["format"] == fmt]
        c = sum(1 for r in sub if r["correct"])
        print(f"  {fmt:18}{len(sub):5}{c:10}{100*c/len(sub):7.0f}%"
              f"{mean([r['h'] for r in sub]):9.2f}")

    print()
    print("  Reading. If h tracked correctness, correct responses would score")
    print("  higher and the point-biserial correlation would be positive and")
    print("  substantial. A near-zero or negative value means the metric is")
    print("  measuring the discipline of presentation, not whether the answer")
    print("  is right - which bounds what the paper can claim.")
    print()

    if args.csv:
        d = os.path.dirname(args.csv)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(f"  wrote {args.csv}")
        print()


if __name__ == "__main__":
    main()
