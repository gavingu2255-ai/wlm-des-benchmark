# prompts/__init__.py — prompt registry for the D/E/S paper
#
# Seven conditions. The three DES encodings carry the prefix "wlm" in code and
# data files (the name of the author's earlier framework); the paper calls them
# DES-SL, DES-JSON and DES-Hybrid v2.2.

from prompts.wlm_sl        import WLM_SL_PROMPT
from prompts.wlm_json      import WLM_JSON_PROMPT
from prompts.wlm_hybrid_v2 import WLM_HYBRID_V2_PROMPT
from prompts.baseline_a    import BASELINE_A_PROMPT
from prompts.baseline_b    import BASELINE_B_PROMPT
from prompts.baseline_c    import BASELINE_C_PROMPT
from prompts.baseline_d    import BASELINE_D_PROMPT

PROMPT_MAP = {
    "wlm_sl":        WLM_SL_PROMPT,           # DES-SL         line syntax
    "wlm_json":      WLM_JSON_PROMPT,         # DES-JSON       nested schema
    "wlm_hybrid_v2": WLM_HYBRID_V2_PROMPT,    # DES-Hybrid v2.2  seven mandatory fields
    "base_a":        BASELINE_A_PROMPT,       # Baseline A     raw prompt
    "base_b":        BASELINE_B_PROMPT,       # Baseline B     structured chain-of-thought
    "base_c":        BASELINE_C_PROMPT,       # Baseline C     Pattern 3 schema-only (Mao et al. 2025)
    "base_d":        BASELINE_D_PROMPT,       # Baseline D     explicit uncertainty prompting
}

HYBRID_PROMPTS = {"wlm_hybrid_v2"}


def get_prompt(prompt_key: str, task_injection: str = "",
               hybrid_injection: str = "") -> str:
    """
    Return the system prompt for a condition.

    task_injection:   appended for every condition (e.g. T04 analogy rules)
    hybrid_injection: appended only for the hybrid format (field mapping hints)
    """
    if prompt_key not in PROMPT_MAP:
        raise KeyError(f"unknown prompt_key {prompt_key!r}; choose from {sorted(PROMPT_MAP)}")
    base = PROMPT_MAP[prompt_key]
    sep = "\n\n"
    if task_injection:
        base = base + sep + task_injection
    if hybrid_injection and prompt_key in HYBRID_PROMPTS:
        base = base + sep + hybrid_injection
    return base
