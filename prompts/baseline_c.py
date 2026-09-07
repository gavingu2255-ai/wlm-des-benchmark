# prompts/baseline_c.py — Baseline C: schema-only structured output
#
# WHY THIS CONDITION EXISTS
# -------------------------
# Schema-only structured output is the natural control for a field-based
# alternatives the study should have compared against. Of the seven he lists it
# is the one that isolates this paper's actual claim.
#
# WLM-Hybrid v2.2 imposes two things at once: a shape (seven mandatory fields,
# filled in order, before the answer is written) and a semantics (what those
# fields mean — required and excluded elements, directional mappings, epistemic
# status, a coverage self-check). Every comparison in the submitted paper
# confounds the two, because no condition supplies shape without meaning.
#
# This condition supplies exactly that.
#
#     hybrid − base_c  →  the contribution of the D/E/S semantics,
#                         with structural shape held constant
#
# If that difference is near zero, structured output as such is the active
# ingredient and the particular decomposition is decoration. That is a result
# worth reporting either way, and the submitted design cannot produce it.
#
# WHAT IT IMPLEMENTS
# ------------------
# Not an invention. Mao, He and Chen (FSE 2025, arXiv:2504.02052) analysed 2,163
# prompt templates extracted from real open-source LLM applications — including
# Uber's and Microsoft's — and found JSON to be the most common output format
# outside plain text. They identify three patterns in how developers specify it:
#
#     Pattern 1   JSON output only                                     36.21%
#     Pattern 2   JSON output + attribute names                        19.83%
#     Pattern 3   JSON output + attribute names + descriptions         43.97%
#
# Sample testing across 45 populated templates and two models rated each on
# format-following and content-following, 1 to 5:
#
#                    format-following        content-following
#                    llama3    gpt-4o        llama3    gpt-4o
#     Pattern 1        3.09      3.21          3.70      3.50
#     Pattern 2        4.66      4.86          4.02      4.30
#     Pattern 3        4.90      4.96          4.47      4.53
#
# Pattern 3 is both the most widely used and the best performing. This condition
# implements it: JSON output, named attributes, a description for each. The
# comparison against WLM-Hybrid v2.2 is therefore not against an arbitrary
# schema but against the strongest generic schema-prompting form documented in
# practice.
#
# Mao et al. also find (their Finding 8) that a format definition alone does not
# stop models appending commentary, and that an explicit exclusion constraint
# raises the rate of parseable-only output from 40% to 100% on llama3 and from
# 86.67% to 100% on gpt-4o. The closing instruction below is that constraint.
#
# WHAT THIS REPLACES, AND WHY
# ---------------------------
# Two earlier designs for this slot were discarded.
#
# A marker-only control — D/E/S with the layer structure removed, markers kept —
# does not exist as an object. Markers are how ICC-1 is enforced; a claim that
# traces to a D element carries none. Remove the structure and the markers have
# nothing to enforce.
#
# A self-verification control (draft, audit, revise) was written and run, then
# withdrawn. Its audit questions asked which claims lacked support, which parts
# of the question went unaddressed, where the draft contradicted itself — that
# is ICC-1 and the D-layer restated as a checklist. It was a variant of the
# thing under test, not an alternative to it. Chain-of-Verification was
# considered as a replacement and rejected on a different ground: its Factored
# form needs four independent calls, and a baseline with four times the
# inference budget cannot be compared to a single-pass protocol.
#
# DESIGN NOTES
# ------------
#   * Seven fields, matching Hybrid's count. Fewer or more would confound
#     semantics with schema size.
#   * Field names are the vocabulary of ordinary analytical writing. None
#     names a D/E/S construct.
#   * Fields are filled before the answer, as in Hybrid — the discipline of
#     committing to structure ahead of prose is shape, not semantics, and is
#     held constant.
#   * Nothing asks for exclusions, back-references, epistemic status or a
#     coverage check. Those are the semantics under test.
#   * No marker vocabulary is prescribed, so judge strictness rule 4 cannot fire
#     on this condition, exactly as it cannot fire on Baseline A.
#   * Flat JSON, same serialisation as Hybrid, so the comparison is not
#     confounded by JSON-handling ability. This makes the condition inaccessible
#     to models that cannot emit valid JSON; Gemini's 73% JSON failure rate on
#     Hybrid will recur here, and that is the intended behaviour — it is the
#     same demand.
#
# REFERENCE
#   Mao, Y., He, J., & Chen, C. (2025). From Prompts to Templates: A Systematic
#   Prompt Template Analysis for Real-world LLMapps. FSE 2025.
#   arXiv:2504.02052.

BASELINE_C_PROMPT = """You are a knowledgeable assistant. Structure your response as a JSON object with exactly these seven fields, in this order.

{
  "context":         "What the question is asking and what domain it belongs to.",
  "key_concepts":    "The concepts the answer depends on, each briefly explained.",
  "analysis":        "The main reasoning, worked through.",
  "considerations":  "Factors that bear on the answer.",
  "limitations":     "What the answer does not cover or cannot settle.",
  "summary":         "The reasoning condensed.",
  "answer":          "The direct answer to the question asked."
}

Fill every field. Complete all seven before writing the final answer — the earlier fields are where the thinking goes, and "answer" reports its result.

Return only the JSON object. No preamble, no commentary, no markdown fences.
"""
