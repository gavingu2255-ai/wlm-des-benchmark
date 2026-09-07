# config.py — D/E/S paper: central configuration
#
# MODEL SNAPSHOTS
#
# Pinned as close to the published conditions as the APIs still allow.
#
# One of them can no longer be matched. The manuscript used
# claude-sonnet-4-20250514, which Anthropic retired on 15 June 2026; calls to it
# now return 404 with no fallback. claude-sonnet-4-5-20250929 is the nearest
# still-active Sonnet and is what this checkout uses, both for the model under
# test and for the primary judge.
#
# Consequence for any re-run: absolute scores are not directly comparable to
# Table 1. Within a single batch, where every condition sees the same snapshot,
# comparisons remain valid — which is why the ablation re-runs Hybrid and
# Baseline A alongside Baseline C rather than reading their published values.
#
# The substitution also changes the output budget. Sonnet 4.5 produces markedly
# longer responses than Sonnet 4 for the same prompts, and truncates at the 2048
# ceiling the published runs used; claude's max_tokens is therefore 4096 here.
# Worth recording in the manuscript: on a hosted API, the experimental conditions
# themselves drift with the provider, not only the scores.
#
# Do not update the remaining IDs here. A later working batch in this project
# used gpt-5.4-mini and qwen3.6 in place of the entries below; mixing those with
# published data confounds model drift with everything else. To evaluate newer
# models, copy this directory and change them there.

from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT_DIR  = Path(__file__).parent
DATA_DIR  = ROOT_DIR / "data"

# Two data trees, kept apart on purpose.
#
# published/  the four CSVs and their raw outputs behind every table in the
#             manuscript. Produced against claude-sonnet-4-20250514, which was
#             retired on 15 June 2026, so they cannot be regenerated. Checksummed.
#             Nothing writes here.
#
# runs/       everything this checkout produces. Delete it and rerun; nothing is
#             lost that a rerun cannot replace.
#
# The previous layout put both in data/results, which is how ablation CSVs came
# to sit beside the canonical ones and how a Table 1 row ended up assembled from
# three different sources.
PUBLISHED_DIR = DATA_DIR / "published"
PUBLISHED_RESULTS = PUBLISHED_DIR / "results"
PUBLISHED_OUTPUTS = PUBLISHED_DIR / "outputs"

RUNS_DIR    = DATA_DIR / "runs"
RESULTS_DIR = RUNS_DIR / "results"
OUTPUTS_DIR = RUNS_DIR / "outputs"
OUT_DIR     = ROOT_DIR / "out"
for _d in (RESULTS_DIR, OUTPUTS_DIR, OUT_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ── Judges ────────────────────────────────────────────────────────────────────
# Claude is the primary judge; all h/s/c reported in the paper are its scores.
# GPT-4o is the validation judge and supplies the Dh disagreement metric.
JUDGES = {
    "claude": {
        "api":        "anthropic",
        # Paper used claude-sonnet-4-20250514, retired 15 June 2026.
        "model_id":   "claude-sonnet-4-5-20250929",
        "max_tokens": 700,
    },
    "gpt4o": {
        "api":        "openai",
        "model_id":   "gpt-4o",
        "max_tokens": 700,
    },
}

# ── Models under test ─────────────────────────────────────────────────────────
MODELS = {
    "claude": {
        "api":        "anthropic",
        # Paper used claude-sonnet-4-20250514, retired 15 June 2026.
        "model_id":   "claude-sonnet-4-5-20250929",
        # 4096, not the 2048 used for the published runs. Sonnet 4.5 writes
        # substantially longer responses than Sonnet 4 to the same prompts and
        # hits 2048 on the first task. Raising the ceiling does not raise cost:
        # the tokens are generated and billed either way, and a truncated
        # response is spend with nothing usable to show for it.
        "max_tokens": 4096,
        "label":      "Claude Sonnet 4.5",
        "tier":       "large",
    },
    "gpt-4o": {
        "api":        "openai",
        "model_id":   "gpt-4o",
        "max_tokens": 2048,
        "label":      "GPT-4o",
        "tier":       "large",
    },
    "gemini-pro": {
        "api":        "gemini",
        "model_id":   "gemini-2.5-flash",
        "max_tokens": 2048,
        "label":      "Gemini 2.5 Flash",
        "tier":       "large",
    },
    "gpt-4o-mini": {
        "api":        "openai",
        "model_id":   "gpt-4o-mini",
        "max_tokens": 2048,
        "label":      "GPT-4o-mini",
        "tier":       "medium",
    },
    "qwen-7b": {
        "api":        "ollama",
        "model_id":   "qwen2.5:7b",
        "max_tokens": 2048,
        "label":      "Qwen2.5 7B",
        "tier":       "small",
    },
    "gemma-4b": {
        "api":        "ollama",
        "model_id":   "gemma3:4b",
        "max_tokens": 2048,
        "label":      "Gemma 3 4B",
        "tier":       "small",
    },
}

# ── Prompt conditions ─────────────────────────────────────────────────────────
PROMPTS = {
    "wlm_hybrid_v2": "WLM-Hybrid v2.2 — seven flat fields + completeness_check",
    "wlm_sl":        "WLM-SL — line-level D/E/S tags",
    "wlm_json":      "WLM-JSON — nested D/E/S schema",
    "base_a":        "Baseline A — raw prompt",
    "base_b":        "Baseline B — structured CoT",
    "base_c":        "Baseline C — schema-only structured output",
    "base_d":        "Baseline D — explicit uncertainty prompting",
}

# ── Sampling ──────────────────────────────────────────────────────────────────
# The published runs used temperature 0.7, the default in models/caller.py.
# The manuscript's §4.3 stated 0 and is corrected in the revision. Leave this
# at 0.7 so that re-runs remain comparable to the published tables.
TEMPERATURE = 0.7

OLLAMA_URL = "http://localhost:11434/api/chat"

# ── Defaults ──────────────────────────────────────────────────────────────────
# Group 2 — the ablation run. Four models, four conditions, 52 tasks, 3 repeats.
# Group 1 (the published tables) is not regenerable and is not re-run.
DEFAULT_MODELS  = ["claude", "gpt-4o", "gemini-pro", "gemma-4b"]
ABLATION_CONDITIONS = ["wlm_hybrid_v2", "base_a", "base_b", "base_c", "base_d"]
DEFAULT_JUDGES  = list(JUDGES.keys())

EXP1_TASKS = [f"T{n:02d}" for n in range(1, 8)]     # T01–T07
EXP2_TASKS = [f"T{n:02d}" for n in range(8, 38)]    # T08–T37
EXP3_TASKS_SELECTED = ["T38", "T41", "T42", "T44", "T46", "T50", "T51", "T52"]
ALL_PAPER_TASKS = EXP1_TASKS + EXP2_TASKS + EXP3_TASKS_SELECTED
