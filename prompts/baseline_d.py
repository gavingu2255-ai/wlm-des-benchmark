# prompts/baseline_d.py — Baseline D: explicit uncertainty prompting
#
# WHY THIS CONDITION EXISTS
# -------------------------
# Two concerns about the main study are one concern seen from two sides.
#
# Objection 2: the metric h credits explicit uncertainty markers, and the D/E/S
# prompts instruct the model to produce them, so h may be measuring compliance
# rather than any change in output.
#
# Objection 6, first item on his list of missing comparisons: explicit
# uncertainty prompting.
#
# The second is the experiment that settles the first. If instructing a model to
# state its uncertainty — with no structure, no layers, no D/E/S vocabulary —
# recovers most of what D/E/S achieves on h, then the objection is right and the
# paper's claim narrows to that instruction. If a gap remains, the objection is
# answered with a condition rather than an argument.
#
#     base_d − base_a  →  what the bare instruction to qualify claims buys
#     hybrid − base_d  →  what D/E/S adds beyond it
#
# §4.6 currently answers objection 2 with four indirect lines of evidence: the
# best-performing format uses a vocabulary the judge rule never names; the rule
# penalises absence rather than rewarding presence; stripping markers costs
# twenty-five times more on tasks where they carry information; and seven of
# thirty-five fully compliant cells score below an unmarked baseline. Those hold.
# None of them is a condition that supplies the marking instruction alone.
# This one is.
#
# DESIGN NOTES
# ------------
#   * No D/E/S marker vocabulary. Not [SP]/[CJ]/[EC], not
#     [FORMAL]/[CONJECTURE]/[EMPIRICAL]. Importing either would make this a
#     variant of the thing under test — the error that sank two earlier drafts
#     of Baseline C. The model expresses uncertainty in its own words, which is
#     what the verbalised-confidence literature does.
#   * No structure of any kind: no fields, no sections, no ordering, no
#     traceability, no self-check. Uncertainty expression is the only variable.
#   * The instruction covers three things the calibration literature treats
#     together: stating confidence, separating what is established from what is
#     inferred, and declining when the question cannot be answered from what is
#     given. Splitting them would make this weaker than the published methods
#     rather than matched to them.
#   * Single pass, no revision. Budget-comparable to every WLM condition.
#   * Judge strictness rule 4 fires on missing *required* markers. This
#     condition requires no marker tokens, so it is exempt on the same terms as
#     Baseline A — which is the point. It has to score on qualification without
#     the mechanical channel available.
#
# LINEAGE
#   Lin, Hilton & Evans (2022), Teaching Models to Express Their Uncertainty in
#     Words — verbalised confidence.
#   Si et al. (2022), Prompting GPT-3 To Be Reliable — calibration and
#     factuality as separable, promptable reliability facets.
#   Kadavath et al. (2022), Language Models (Mostly) Know What They Know.

BASELINE_D_PROMPT = """You are a knowledgeable assistant. Answer the user's question accurately and helpfully.

Be explicit about how confident you are in what you say.

State your confidence in the claims you make, and say where that confidence comes from. Distinguish what you are certain of from what you are inferring, and both from what you are guessing.

Where a claim rests on information you do not have, say so and say what the missing information is. Where the question cannot be answered from what you have been given, say that plainly rather than answering anyway. A well-supported partial answer is better than a complete answer that is partly invented.

Express all of this in your own words, as part of the response. Do not use a fixed notation or tagging scheme."""
