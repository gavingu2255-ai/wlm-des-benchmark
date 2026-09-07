# models/caller.py  —  Unified model caller (lazy client init)

import json, time, os, urllib.request
from config import MODELS, JUDGES, OLLAMA_URL

def _get_anthropic():
    import anthropic
    return anthropic.Anthropic(timeout=120.0)

def _get_openai():
    import openai
    return openai.OpenAI()

def _get_gemini():
    from google import genai
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    return client

def call_model(model_key, system, user_input, max_tokens=None,
               registry=None, temperature=0.7):
    reg   = registry or MODELS
    cfg   = reg[model_key]
    api   = cfg["api"]
    mid   = cfg["model_id"]
    maxt  = max_tokens or cfg["max_tokens"]
    start = time.perf_counter()

    if api == "anthropic":
        client = _get_anthropic()
        kwargs = {
            "model": mid, "max_tokens": maxt,
            "messages": [{"role": "user", "content": user_input}],
            "temperature": temperature,
        }
        if system: kwargs["system"] = system
        resp    = client.messages.create(**kwargs)
        elapsed = round(time.perf_counter()-start, 3)
        return {
            "model_key": model_key, "model_id": mid, "api": api,
            "output": resp.content[0].text,
            "input_tokens":  resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
            "total_tokens":  resp.usage.input_tokens + resp.usage.output_tokens,
            "latency_s": elapsed,
        }

    elif api == "openai":
        client = _get_openai()
        msgs = []
        if system: msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": user_input})
        # Newer OpenAI models use max_completion_tokens instead of max_tokens
        _new_models = {"o1", "o3", "o4", "gpt-5", "gpt-4.5"}
        _use_completion_tokens = any(mid.startswith(m) for m in _new_models) or "gpt-5" in mid
        _tok_param = "max_completion_tokens" if _use_completion_tokens else "max_tokens"
        _create_kwargs = {
            "model": mid, "messages": msgs,
            _tok_param: maxt, "temperature": temperature,
        }
        resp    = client.chat.completions.create(**_create_kwargs)
        elapsed = round(time.perf_counter()-start, 3)
        return {
            "model_key": model_key, "model_id": mid, "api": api,
            "output": resp.choices[0].message.content,
            "input_tokens":  resp.usage.prompt_tokens,
            "output_tokens": resp.usage.completion_tokens,
            "total_tokens":  resp.usage.total_tokens,
            "latency_s": elapsed,
        }

    elif api == "gemini":
        client = _get_gemini()
        from google.genai import types
        config = types.GenerateContentConfig(
            max_output_tokens=8192,  # Large enough for full responses
            temperature=temperature,
            system_instruction=system if system else None,
            thinking_config=types.ThinkingConfig(thinking_budget=0),  # Disable thinking
        )
        try:
            resp    = client.models.generate_content(
                model=mid,
                contents=user_input,
                config=config,
            )
            elapsed = round(time.perf_counter()-start, 3)
            text    = resp.text
            # Strip markdown code blocks that Gemini adds around JSON
            text = text.strip()
            if text.startswith('```'):
                lines = text.split('\n')
                # Remove first line (```json or ```) and last line (```)
                if lines[-1].strip() == '```':
                    lines = lines[1:-1]
                else:
                    lines = lines[1:]
                text = '\n'.join(lines).strip()
            in_tok  = resp.usage_metadata.prompt_token_count
            out_tok = resp.usage_metadata.candidates_token_count
            return {
                "model_key": model_key, "model_id": mid, "api": api,
                "output": text,
                "input_tokens":  in_tok,
                "output_tokens": out_tok,
                "total_tokens":  in_tok + out_tok,
                "latency_s": elapsed,
            }
        except Exception as e:
            return {
                "model_key": model_key, "model_id": mid, "api": api,
                "error": str(e), "output": "",
                "input_tokens": 0, "output_tokens": 0,
                "total_tokens": 0, "latency_s": 0,
            }

    elif api == "ollama":
        msgs = []
        if system: msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": user_input})
        payload = json.dumps({
            "model": mid, "messages": msgs, "stream": False,
            "options": {"temperature": temperature,
                        "num_predict": maxt, "num_ctx": 8192}
        }).encode()
        try:
            req  = urllib.request.Request(
                OLLAMA_URL, data=payload,
                headers={"Content-Type": "application/json"}
            )
            resp = urllib.request.urlopen(req, timeout=240)
            data = json.loads(resp.read())
            elapsed = round(time.perf_counter()-start, 3)
            msg   = data.get("message", {})
            usage = data.get("prompt_eval_count", 0)
            gen   = data.get("eval_count", 0)
            return {
                "model_key": model_key, "model_id": mid, "api": api,
                "output": msg.get("content", ""),
                "input_tokens":  usage,
                "output_tokens": gen,
                "total_tokens":  usage + gen,
                "latency_s": elapsed,
            }
        except Exception as e:
            return {
                "model_key": model_key, "model_id": mid, "api": api,
                "error": str(e), "output": "",
                "input_tokens": 0, "output_tokens": 0,
                "total_tokens": 0, "latency_s": 0,
            }

    else:
        return {
            "model_key": model_key, "model_id": mid, "api": api,
            "error": f"Unknown API: {api}", "output": "",
            "input_tokens": 0, "output_tokens": 0,
            "total_tokens": 0, "latency_s": 0,
        }
