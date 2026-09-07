# Matched pairs — pre-annotation

My reading of the seven pairs in `matched_pairs.md`. Yours to correct.

Each pair holds the model and the task constant and varies only the prompt
format, so the difference in score is attributable to the format. I have read the
full text of each and recorded what I think produced the difference. Where I
think the judge was wrong, I say so.

**How to use this.** Open `matched_pairs.md` alongside. For each pair, check
three things against my reading: whether the derivation is actually performed
rather than asserted; whether the epistemic markers sit on claims that were
derived or on claims that were not; and whether the seven fields displaced the
answer or organised it. Those three account for every difference I found.

---

## Summary

| Pair | Task / model | h base → hybrid | What actually differs |
|---|---|---|---|
| 1 | T29 / GPT-4o | 5 → 1 | Hybrid asserts the answer without doing the calculus |
| 2 | T29 / Claude | 1 → 5 | Baseline does *better* mathematics and is punished for it |
| 3 | T44 / GPT-4o | 5 → 2 | Fields fill with generic taxonomy; the actual gaps never listed |
| 4 | T27 / Gemini | 4 → 1 | Definitions field consumes the response; no arithmetic reaches the answer |
| 5 | T09 / GPT-4o | 2 → 5 | Structure forces the error to be located instead of waved at |
| 6 | T12 / GPT-4o | 2 → 5 | Mapping field forces premise-by-premise derivation; baseline smuggles in world knowledge |
| 7 | T05 / Qwen-7B | 2 → 5 | Baseline fabricates a citation; the field structure leaves nowhere to put one |

Four of seven turn on the same thing: whether the derivation is performed or
merely claimed. That is the axis to watch.

---

## Pair 1 — T29 on GPT-4o. Structure hurt.

Both responses give the same final answer, 100 × 200 = 20,000. The scores differ
by four points.

The Baseline A response writes the algebra out: `A(x) = x(400−2x) = 400x − 2x²`,
`A'(x) = 400 − 4x = 0`, `x = 100`, then `A''(x) = −4 < 0` to verify the maximum,
then the extension case worked separately. Every step is on the page.

The Hybrid response never performs the calculus. Its `[MAPPINGS]` field contains
functional notation with no values — `f_CE: (x,y) → g(x,y)`, `f_OC: g(x,y) →
{Critical Points}` — and its `[EXAMPLES]` field substitutes a different, simpler
problem (100 m of fencing, no barn). The `[FINAL ANSWER]` states 100 and 200
without either being derived anywhere in the response.

Then `[EPISTEMICS]` marks three claims `[FORMAL]`, which the protocol defines as
"follows by logical necessity from stated definitions". Nothing in the response
states the definitions those results would follow from.

**Reading.** The seven fields consumed the budget. Definitions with two negations
each, structure, mappings in functional notation, a worked example of a different
problem — by the time the response reaches the answer there is no room left for
the work, and the marker claims derivation that did not occur. h = 1 is
"multiple unsupported specific claims presented as established fact", and that is
what the judge saw.

This is the clearest instance in the set of the field-filling failure mode.

---

## Pair 2 — T29 on Claude. Structure helped, and the judge was wrong.

The same task, the opposite direction, and it does not mean what the scores say.

The Baseline A response derives the domain constraint the task states: the barn
is 100 m, so `y ≤ 100`, hence `400 − 2x ≤ 100`, hence `x ≥ 150`. It finds the
unconstrained critical point at `x = 100`, observes that this lies outside the
feasible domain, checks the endpoints, and reports 150 × 100 = **15,000 m²**.

That is correct. A 200-metre side cannot rest against a 100-metre wall.

The Hybrid response ignores the barn's length and reports 20,000 m².

The judge scored the correct answer h = 1 and the incorrect one h = 5, because
the task's own `required_elements` field states the answer as "200 m × 100 m =
20,000 m²". The judge is scoring agreement with the task key, and **the task key
is wrong**.

**Reading.** This is a defect in the benchmark, not in either model. It also
means the objective-correctness analysis in §4.8 of the paper, which scores
against the task's key, marks this response incorrect when it is the best answer
in the set. I flagged the ambiguity in that section; this pair shows it is not an
ambiguity but an error, and T29 should be corrected or dropped before the
benchmark is used again.

Note the contrast with Pair 1: both responses there scored h = 1, one for
asserting without deriving, this one for deriving correctly against a bad key.
The same score, opposite causes.

---

## Pair 3 — T44 on GPT-4o. Structure hurt.

The task asks the model to list what information is present, what is absent, and
what each absent item would change — an information-gap task where the correct
answer is largely a list of specific missing facts.

Baseline A produces exactly that: eight numbered absent items, each specific to
the case (team performance norms, the nature of the conflicts, historical
performance data, what support was offered during the divorce), each with a
stated consequence.

The Hybrid response spends `[DEFINITIONS]` defining "Information Classification",
"Performance Relevant Information", "Context Information" and "Personal
Information" as abstract categories. `[STRUCTURE]` restates the taxonomy.
`[MAPPINGS]` gives `f: Info → {Performance Relevant, Context, Personal}`.
`[EXAMPLES]` invents a different employee. The actual list of absent items —
the thing the task asks for — never appears at the specificity Baseline A
reaches.

**Reading.** The fields pulled the response toward the general when the task
required the particular. The protocol asks for definitions and mappings before
the answer; on a task whose answer *is* a list of particulars, that ordering
spends the response on scaffolding. Completeness drops from 5 to 2, which is the
same observation from the judge's side.

---

## Pair 4 — T27 on Gemini. Structure hurt, most extremely.

Baseline A works Bayes' theorem through in full: defines the events, states each
given probability with a `[GIVEN]` marker, derives `P(T⁻|D) = 0.05` and
`P(T⁺|D^c) = 0.10`, computes `P(T⁺) = 0.0095 + 0.099 = 0.1085`, then applies the
theorem. Marked step by step as the task asks.

The Hybrid response's `definitions` field runs to roughly 300 words defining
Event, Probability, Conditional Probability, Independence, Prevalence,
Sensitivity, Specificity, Bayes' Theorem, Sample Space, Outcome and Random
Variable — each with the two mandatory negations. It is still defining
terminology where Baseline A has already finished the calculation.

**Reading.** The two-negations-per-concept rule scales badly when a task involves
many concepts. Eleven concepts × three clauses each is a page of definitions
before any arithmetic. On this model, which already produces long output, the
requirement is enough to displace the answer entirely. h = 1, c = 1.

This is the same failure as Pair 1 with a different proximate cause: there the
field structure was filled thinly, here it was filled thoroughly and left no
room.

---

## Pair 5 — T09 on GPT-4o. Structure helped.

The task is the classical Euclid proof with a deliberate error at Step 6:
"Therefore M is prime". M need not be prime; it need only have a prime factor
outside the assumed list.

Baseline A identifies the error correctly — it says Step 6 is INVALID and that M
"could still be composite, consisting of primes not in the list" — and yet scores
h = 2. Reading further, the response then marks Steps 7 and 8 CONDITIONAL "on the
assumption in Step 6" without resolving whether the conclusion survives, which
the task explicitly asks for in part (d). It locates the error and then leaves the
consequence hanging.

The Hybrid response's `[STRUCTURE]` field states the corrected argument directly:
"M requires a new prime divisor or is itself prime. The contradiction arises from
the finite assumption failing in accounting for M's divisibility, not from M's
primality itself." Its `constraint` line reads "the conclusion must not assume
M's primality directly".

**Reading.** Here the structure field did the work it is designed for. The task
requires a *corrected* argument, not just error location, and the requirement to
state a structural constraint pushed the model into formulating it. This is the
protocol operating as intended.

---

## Pair 6 — T12 on GPT-4o. Structure helped, and the mechanism is precise.

Five syllogistic conclusions to be labelled VALID, INVALID or UNDETERMINED.

Baseline A gets C2 wrong in a specific and revealing way. It labels "Some mammals
lay eggs" VALID, and its inference chain reads: "From P5, platypuses are mammals.
From general knowledge (not provided in premises but common knowledge),
platypuses lay eggs." It states outright that it is importing a premise, and
labels the conclusion valid anyway.

The Hybrid response's `[MAPPINGS]` field forces each conclusion to be written as
an explicit derivation from named premises. C4 comes out UNDETERMINED "as no
premise states that platypuses lay eggs" — the same fact Baseline A knew and used
anyway.

**Reading.** This is the most precise demonstration in the set. The requirement
to write the derivation as a mapping from named premises made it visible that the
premise was absent. The baseline had the same information and the same reasoning
capacity; what it lacked was a place where the missing premise would show.

Note that the Hybrid response is not fully correct either — its C5 derivation is
also questionable — but on the specific mechanism the task tests, the structure
caught what the baseline did not.

---

## Pair 7 — T05 on Qwen-7B. Structure helped, and this one matters most.

The task asks the model to classify claims about a framework as formally derived,
computationally verified, or theoretical, and to state whether the framework has
been empirically validated.

Baseline A fabricates. It writes that computational models "have been used to
simulate various scenarios", that "a study published in *Journal of Artificial
Societies and Social Simulation* utilized agent-based modeling techniques", and
that "the computational results showed that the framework accurately predicted
certain emergent behaviors". No such study exists. It then interprets the
framework as being about work–life management, which it is not.

The Hybrid response has no comparable passage. Its `definitions` field defines
the three categories, and the fields for computational verification are populated
with the *conditions* under which something would count as verified — method,
scope, result — rather than with a claim that it was.

**Reading.** This is the strongest case for the protocol in the set, and it
occurs on the weakest model. The mechanism is not that the structure made Qwen
smarter; it is that the field definitions specify what a computational
verification claim must contain, and the model could not produce those
components, so it did not produce the claim. The scaffold left nowhere to put a
fabrication.

Structure score drops from 3 to 2 — the Hybrid output is messier — while
hallucination suppression rises from 2 to 5. That trade is the paper's thesis in
one pair.

---

## What I would check first

Three places where my reading is most likely to be wrong, in order:

**Pair 2.** I am claiming the benchmark's own answer key is wrong. Confirm the
geometry yourself: 400 m of fencing, one side against a 100 m barn, `2x + y =
400`, `y ≤ 100`. If you agree, T29 needs correcting and §4.8 of the paper needs a
sentence stronger than "an ambiguity is available".

**Pair 5.** I score Baseline A as having located the error but not resolved the
consequence. That is a judgement about how much part (d) of the task demands, and
you may read the task differently.

**Pair 6.** I treat "importing common knowledge and labelling the result VALID"
as the failure. An alternative reading is that the model was answering a
different question — is the conclusion true — rather than the one asked. The
distinction matters for whether this counts as structure helping or as the
baseline misreading the task.

Two patterns I am confident about and would not expect you to overturn: the
field-filling displacement in Pairs 1, 3 and 4, and the absence of a place to put
a fabrication in Pair 7.
