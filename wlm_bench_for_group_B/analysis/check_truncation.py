#!/usr/bin/env python3
"""
check_truncation.py — find responses that hit the token cap

    python analysis/check_truncation.py data/outputs/ablation_<batch>.jsonl

An output that reaches max_tokens was cut off mid-sentence. Nothing in the
scoring pipeline notices: _extract_scorable_text() returns whatever it finds,
and any fragment over twenty characters passes. The judge then scores a partial
response and the row looks normal in the CSV.

This matters most for Baseline C, whose three-part output — draft, self-audit,
revised answer — puts the part that gets scored last. Truncation there removes
the response entirely while leaving the draft and audit intact, so the row is
not merely degraded but meaningless.

Reports, per condition: how many outputs hit the cap, and for base_c whether
the REVISED ANSWER heading survived and how long the text after it is.
"""

import json
import re
import sys
from collections import defaultdict

# Effective output cap per (model, condition).
#
# models/caller.py does not treat max_tokens uniformly. The Anthropic, OpenAI and
# Ollama paths pass through whatever the caller supplies. The Gemini path ignores
# it and hardcodes max_output_tokens=8192, so a Gemini response is capped at 8192
# whatever run_ablation.py requests. Comparing Gemini output lengths against 2048
# or 3072 flags ordinary long responses as truncation.
# Caps are per model, not per condition. config.py sets max_tokens on each
# model; the Gemini path in models/caller.py ignores it and hardcodes 8192.
# An earlier version of this script assumed 2048 everywhere except Gemini and
# reported 240 spurious truncations for Claude, whose cap is 4096.
MODEL_CAPS = {
    "claude":      4096,
    "gemini-pro":  8192,
    "gemini":      8192,
    "gpt-4o":      2048,
    "gpt-4o-mini": 2048,
    "qwen-7b":     2048,
    "gemma-4b":    2048,
}
DEFAULT_CAP = 2048


def cap_for(model_key, prompt_key):
    return MODEL_CAPS.get(model_key, DEFAULT_CAP)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path = sys.argv[1]

    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    if not rows:
        sys.exit("no readable rows")

    by = defaultdict(list)
    for r in rows:
        by[(r.get("model_key", "?"), r.get("prompt_key", "?"))].append(r)

    print()
    print("=" * 84)
    print("  TRUNCATION CHECK")
    print(f"  {path}   {len(rows)} outputs")
    print("=" * 84)
    print(f"  {'model':12}{'condition':16}{'n':>4}{'cap':>7}{'at cap':>8}{'max tok':>9}{'mean tok':>10}")
    print("  " + "-" * 66)

    total_hit = 0
    for (m, p), rs in sorted(by.items()):
        cap = cap_for(m, p)
        toks = [r.get("output_tokens", 0) for r in rs]
        hit = sum(1 for t in toks if t >= cap)
        total_hit += hit
        flag = "  <<<" if hit else ""
        print(f"  {m:12}{p:16}{len(rs):4}{cap:7}{hit:8}{max(toks):9}"
              f"{sum(toks)/len(toks):10.0f}{flag}")

    # The three-part DRAFT/SELF-AUDIT/REVISED check that used to live here
    # belonged to the withdrawn self-verification design of Baseline C. The
    # current Baseline C is Pattern 3 structured output — flat JSON, no section
    # headings — so the check reported every row as a failure. Removed.

    print()
    if total_hit:
        print(f"  {total_hit} output(s) hit the cap and are truncated. Re-run those conditions")
        print("  with a larger max_tokens; their scores are not usable as they stand.")
    else:
        print("  No output reached its cap. All responses are complete.")
    print()


if __name__ == "__main__":
    main()
