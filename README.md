# WLM Benchmark

Code and data for

> **D/E/S: A Tri-Layer Generative Prompt Architecture for Structured Reasoning
> and Hallucination Suppression in Large Language Models**
> Wujie Gu · *Frontiers in Artificial Intelligence* · manuscript 1878392

---

## The one thing to know

There are two data trees and they are not the same kind of thing.

```
data/published/     the five CSVs behind every table in the manuscript,
                    plus the raw model outputs that produced them.
                    Generated against claude-sonnet-4-20250514, retired
                    15 June 2026. NOT REGENERABLE. Checksummed. Read-only.

data/runs/          everything this checkout produces. Delete it and rerun.
```

The previous layout put both under `data/results`, which is how ablation CSVs
came to sit beside the canonical ones, and how a row of Table 1 ended up
assembled from three different sources under two judge conventions. Keep them
apart.

---

## Setup

```bash
python -m venv .venv
```

Activate — PowerShell `.venv\Scripts\Activate.ps1`, cmd `.venv\Scripts\activate`,
macOS/Linux `source .venv/bin/activate`. The prompt gains `(.venv)`; it
disappears when the terminal closes and must be re-activated, though nothing is
lost in between.

If PowerShell refuses, once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Then:

```bash
pip install -r requirements.txt
python -c "import anthropic, openai, numpy, scipy; print('ok')"
```

API keys, in the terminal you will run from:

```powershell
$env:ANTHROPIC_API_KEY="sk-ant-..."
$env:OPENAI_API_KEY="sk-..."
$env:GOOGLE_API_KEY="..."          # Gemini only
```

Gemma runs locally: `ollama serve` in a second window, then
`ollama pull gemma3:4b`.

Check the keys reached Python:

```bash
python -c "import os;print([k for k in ('ANTHROPIC_API_KEY','OPENAI_API_KEY') if os.getenv(k)])"
```

System environment variables only reach *new* processes. If a key was just set
through the Windows dialog, close the terminal and open a new one.

---

## Analysis that needs no API calls

Four of the five analysis scripts read stored data and cost nothing to run.

```bash
python analysis/verify_tables.py                 # every table in the manuscript
python analysis/structural_compliance.py         # protocol conformance, parsed
python analysis/check_truncation.py <jsonl>      # find cut-off responses
python analysis/analyze_ablation.py <csv>        # decompose an ablation run
```

`verify_tables.py` is the source of truth. Every figure in the revised manuscript
comes from its output; nothing is typed by hand. If a manuscript number disagrees
with it, the script is right.

`structural_compliance.py` parses 528 stored outputs against each format's
structural requirements — does the D-layer enumerate, do E-steps carry
back-references, are the seven fields present. It is the one measurement in the
study that never passes through a judge.

Verify the published data first:

```bash
cd data/published
sha256sum -c CHECKSUMS.txt
cd ../..
```

On Windows:

```powershell
cd data\published
python -c "import hashlib,os;os.chdir('results');[print(l.split()[1],'OK' if hashlib.sha256(open(l.split()[1],'rb').read()).hexdigest()==l.split()[0] else 'MISMATCH') for l in open('../CHECKSUMS.txt')]"
cd ..\..
```

---

## Running experiments

```bash
python run_ablation.py --dry-run
```

Prints the plan and calls nothing. Check the model IDs before spending anything.

Smoke test — Gemma is local, so only the judges cost money:

```bash
python run_ablation.py --models gemma-4b --tasks T01,T02,T03 --repeats 1
```

Each line should end with two judge scores. A `!` after a judge's bracket means
its reply failed to parse; if every line carries one, stop and check the keys.

Then the real run:

```bash
python run_ablation.py --models claude,gpt-4o --conditions wlm_hybrid_v2,base_c,base_d --repeats 1
```

Output lands in `data/runs/`. Resume after any interruption:

```bash
python run_ablation.py ... --resume data/runs/results/ablation_<batch>.csv
```

Completed rows are skipped and every row is flushed immediately, so a crash
costs at most one call.

After a run, always:

```bash
python analysis/check_truncation.py data/runs/outputs/ablation_<batch>.jsonl
python analysis/analyze_ablation.py data/runs/results/ablation_<batch>.csv --csv out/summary.csv
```

Truncation first. A response cut off at the token cap is billed, scored, and
useless, and nothing else in the pipeline notices.

---

## Conditions

| Key | What it is |
|---|---|
| `wlm_hybrid_v2` | D/E/S: seven fields with layer semantics, ICC-1 enforced through markers |
| `wlm_json` | same schema, nested JSON, machine-readable D-references |
| `wlm_sl` | same schema, line tags, line-local back-references |
| `base_a` | raw prompt, one sentence |
| `base_b` | structured chain-of-thought, four steps |
| `base_c` | schema-only: seven generic fields, same shape, no D/E/S semantics |
| `base_d` | explicit uncertainty prompting: qualify claims in your own words, no structure |

`base_c` and `base_d` address the objection that
the study compared D/E/S only against an unconstrained prompt and a single CoT
protocol. Both are single-pass and share the model's output budget, so the
comparison measures protocol rather than inference spend. `hybrid − base_c`
isolates the layer semantics with structural shape held constant;
`hybrid − base_d` isolates the structure with the instruction to qualify claims
held constant.

Two earlier designs for `base_c` were discarded, for reasons worth not
rediscovering. A marker-only control cannot be built: markers are how ICC-1 is
enforced, and a claim that traces to a D-element carries none, so removing the
structure leaves the markers with nothing to enforce. A self-verification control
was written, run, and withdrawn — its audit questions restated ICC-1 and the
D-layer, making it a variant of the protocol under test rather than an
alternative to it. Chain-of-Verification was considered and rejected because its
Factored form needs four independent calls.

---

## Model snapshots

Pinned in `config.py` as close to the published conditions as the APIs still
allow. One cannot be matched: `claude-sonnet-4-20250514` was retired on 15 June
2026 and now returns 404. `claude-sonnet-4-5-20250929` stands in, for the model
under test and for the primary judge.

Two consequences. Absolute scores from a rerun are not comparable to Table 1 —
within-batch comparisons are, which is why the ablation reruns Hybrid alongside
the new baselines rather than reading its published values. And Sonnet 4.5 writes
markedly longer responses than Sonnet 4, so `claude`'s `max_tokens` is 4096 here
against the 2048 the published runs used.

Worth recording in the manuscript: on a hosted API the experimental conditions
drift with the provider, not only the scores. This benchmark lost the ability to
reproduce its own original conditions inside a year.

---

## Layout

```
config.py               model snapshots, judges, paths, task lists
run_ablation.py         experiment runner

prompts/                the seven conditions, one file each
  wlm_sl.py               DES-SL          line syntax
  wlm_json.py             DES-JSON        nested schema
  wlm_hybrid_v2.py        DES-Hybrid v2.2 seven mandatory fields
  baseline_a.py           Baseline A      raw prompt
  baseline_b.py           Baseline B      structured chain-of-thought
  baseline_c.py           Baseline C      Pattern 3 schema-only (Mao et al. 2025)
  baseline_d.py           Baseline D      explicit uncertainty prompting
tasks/                  benchmark.py T01–T37, exp3_tasks.py T38–T52
models/caller.py        unified caller: Anthropic, OpenAI, Gemini, Ollama
scoring/judge.py        dual LLM-as-judge, full rubric and strictness rules

analysis/
  verify_tables.py           recompute every Group A manuscript table
  data_reference.py          every number in the manuscript, from source
  check_manuscript.py        cell-by-cell check of a docx against the reference
  structural_compliance.py   protocol conformance, parsed, no judge
  objective_correctness.py   correctness on the 14 checkable tasks
  analyze_ablation.py        decompose a Group B run
  check_truncation.py        find responses cut off at the cap
  extraction_check.py        does presentation drive the s/c scores?

data/published/         irreplaceable. read-only. checksummed.
  results/                five score CSVs (four Group A, one Group B)
  outputs/                raw model outputs, both groups
  CHECKSUMS.txt           sha256 of all six
data/runs/              regenerable. gitignored.

docs/
  manuscript.md               the paper, markdown source
  Supplementary.md            all 52 task prompts + five matched output pairs
  DATA_SOURCE.md              which file produces which table
  DATA_REFERENCE.md           generated by data_reference.py
  CHANGES.md                  cell-level corrections from the data audit
  reference.docx, build_black.sh   pandoc build (all text black)

figures/                the four manuscript figures, 300 dpi
```

## Known defects, carried over

Recorded so they are not rediscovered as surprises. Full detail in
`docs/CHANGES.md`.

**Table 1, Baseline B row.** The submitted values came from at least three
sources under two judge conventions; two of them match no file in a 178-file
archive. The revised table is computed entirely from `full_v6_scores.csv`,
Claude judge.

**Table 1, Δh column.** Originally the composite Δ = (|s| + |h| + |c|)/3,
relabelled Δh when the metric narrowed to hallucination, never recomputed. Now
computed as Δh throughout. Claude/Hybrid and Claude/Baseline B both move to
0.000, so the §5.4 argument resting on their difference no longer holds.

**Table 4, Gemini rows.** Hand-transcribed from console output before
`gemini_all_scores.csv` existed. Corrected in the second decimal; no ★ changes.

**Temperature.** `models/caller.py` defaults to 0.7 and passes it on every path.
The manuscript's §4.3 said 0. The runs were at 0.7.

**Judge strictness rule 4** did not list `[FORMAL]/[CONJECTURE]/[EMPIRICAL]`, the
vocabulary WLM-Hybrid v2.2 uses, so it never fired on unmarked Hybrid output.
Fixed here. Published scores were produced under the rule as written and are
unchanged.

