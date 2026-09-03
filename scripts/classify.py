#!/usr/bin/env python3
"""
Classify new starred repos using configurable LLM provider.
Supports: gemini, minimax (OpenAI-compatible), openai, anthropic
"""

import os
import sys
import json
import time
import subprocess
from pathlib import Path

PROVIDER = os.getenv("LLM_PROVIDER", "nvidia").lower()
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "8"))
RPM = int(os.getenv("LLM_RPM", "10"))
MAX_ATTEMPTS = int(os.getenv("LLM_MAX_ATTEMPTS", "5"))
DELAY_BETWEEN_BATCHES = 60.0 / RPM

DATA_DIR = Path(__file__).parent.parent / "data"
ROOT = Path(__file__).parent.parent
CATEGORIES_FILE = ROOT / "categories.yaml"
PREFERENCES_FILE = ROOT / "preferences.txt"


def _push_progress(message):
    """Commit catalog progress so a failed job can resume from GitHub."""
    if os.getenv("INCREMENTAL_PUSH") != "true":
        return
    subprocess.run(["git", "add", "data/catalog.json", "data/state.json", "data/ai_output.json"], cwd=ROOT)
    staged = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT)
    if staged.returncode == 0:
        return
    subprocess.run(["git", "commit", "-m", message], cwd=ROOT, check=False)
    push = subprocess.run(["git", "push"], cwd=ROOT)
    if push.returncode != 0:
        print("WARNING: incremental git push failed (will retry later)", flush=True)


def load_yaml(path):
    import yaml
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def build_prompt(inbox_batch, categories, preferences):
    """Build the prompt for the LLM."""
    cat_lines = []
    for cat in categories.get("categories", []):
        cat_lines.append(f"  - {cat['name']}")
        for sub in cat.get("subcategories", []):
            cat_lines.append(f"    - {sub}")

    categories_str = "\n".join(cat_lines)
    items_str = json.dumps(inbox_batch, ensure_ascii=False, indent=2)

    prompt = f"""You are categorizing GitHub starred repositories.

Preferences:
{preferences}

Available categories (use these, propose new only if truly necessary):
{categories_str}

Repositories to categorize:
{items_str}

For each repository, return a JSON object with these fields:
- id (int): the repo's numeric id
- category (string): one of the category names above
- subcategory (string): one of the subcategories, or empty string
- purpose (string): one sentence describing what this repo does
- tags (array of strings): 3-5 relevant short tags
- confidence (string): "high", "medium", or "low"
- needs_review (boolean): true if unsure, false otherwise
- suggested_new_category (boolean, optional): true only if proposing new
- suggested_category (string, optional): name of new category if suggesting

Return ONLY a JSON array of these objects, nothing else. No markdown, no explanation.
"""
    return prompt


def parse_response(text):
    """Parse JSON from LLM response, handling code fences."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


def call_gemini(prompt, model_name):
    import google.generativeai as genai
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY required for gemini provider")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    response = model.generate_content(
        prompt,
        generation_config={"temperature": 0.1, "max_output_tokens": 8192}
    )
    return parse_response(response.text)


def _strip_key(value):
    if not value:
        return value
    return value.strip().strip('"').strip("'")


def call_openai_compatible(prompt, model_name, api_key, base_url, extra_body=None):
    from openai import OpenAI
    timeout = float(os.getenv("LLM_TIMEOUT", "600"))
    client = OpenAI(
        api_key=_strip_key(api_key),
        base_url=base_url.rstrip("/"),
        timeout=timeout,
        max_retries=0,
    )
    kwargs = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 8192,
    }
    if extra_body:
        kwargs["extra_body"] = extra_body
    response = client.chat.completions.create(**kwargs)
    content = response.choices[0].message.content
    if not content:
        raise ValueError(f"Empty LLM response: {response.model_dump()}")
    return parse_response(content)


def call_nvidia(prompt, model_name):
    """NVIDIA NIM OpenAI-compatible API (minimaxai/minimax-m3)."""
    api_key = _strip_key(os.getenv("NVIDIA_API_KEY") or os.getenv("MINIMAX_API_KEY"))
    base_url = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
    if not api_key:
        raise ValueError("NVIDIA_API_KEY (or MINIMAX_API_KEY) required for nvidia provider")
    return call_openai_compatible(
        prompt,
        model_name or "minimaxai/minimax-m3",
        api_key,
        base_url,
    )


def call_minimax(prompt, model_name):
    """MiniMax official OpenAI-compatible API."""
    api_key = _strip_key(os.getenv("MINIMAX_API_KEY"))
    base_url = os.getenv("MINIMAX_BASE_URL", "https://api.minimax.io/v1")
    if not api_key:
        raise ValueError("MINIMAX_API_KEY required for minimax provider")
    return call_openai_compatible(
        prompt,
        model_name or "MiniMax-M3",
        api_key,
        base_url,
        extra_body={"thinking": {"type": "disabled"}},
    )


def call_openai(prompt, model_name):
    from openai import OpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY required for openai provider")
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model_name or "gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=8192,
        response_format={"type": "json_object"},
    )
    return parse_response(response.choices[0].message.content)


def call_anthropic(prompt, model_name):
    import anthropic
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY required for anthropic provider")
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model_name or "claude-3-5-sonnet-20241022",
        max_tokens=8192,
        temperature=0.1,
        messages=[{"role": "user", "content": prompt}],
    )
    return parse_response(response.content[0].text)


def call_llm(prompt, model_name):
    """Dispatch to the configured provider."""
    if PROVIDER == "gemini":
        return call_gemini(prompt, model_name)
    elif PROVIDER in ("nvidia", "nim"):
        return call_nvidia(prompt, model_name)
    elif PROVIDER == "minimax":
        return call_minimax(prompt, model_name)
    elif PROVIDER == "openai":
        return call_openai(prompt, model_name)
    elif PROVIDER == "anthropic":
        return call_anthropic(prompt, model_name)
    else:
        raise ValueError(f"Unknown provider: {PROVIDER}")


def main():
    # Load inputs
    inbox_path = DATA_DIR / "inbox.json"
    if not inbox_path.exists():
        print("No inbox.json found, nothing to classify")
        return

    with open(inbox_path, "r", encoding="utf-8") as f:
        inbox = json.load(f)

    if not inbox:
        print("inbox.json is empty, nothing to classify")
        return

    categories = load_yaml(CATEGORIES_FILE)
    preferences = load_text(PREFERENCES_FILE)

    # Model name per provider
    model_name = os.getenv("LLM_MODEL")
    if not model_name:
        defaults = {
            "gemini": "gemini-3.6-flash",
            "nvidia": "minimaxai/minimax-m3",
            "nim": "minimaxai/minimax-m3",
            "minimax": "MiniMax-M3",
            "openai": "gpt-4o-mini",
            "anthropic": "claude-3-5-sonnet-20241022",
        }
        model_name = defaults.get(PROVIDER, "gemini-3.6-flash")

    print(
        f"Classifying {len(inbox)} repos with {PROVIDER} ({model_name}) in batches of {BATCH_SIZE}...",
        flush=True,
    )

    all_results = []
    sys.path.insert(0, str(Path(__file__).parent))
    from merge import merge_results  # noqa: E402

    for i in range(0, len(inbox), BATCH_SIZE):
        batch = inbox[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(inbox) + BATCH_SIZE - 1) // BATCH_SIZE

        print(f"  Batch {batch_num}/{total_batches} ({len(batch)} repos)...", flush=True)

        prompt = build_prompt(batch, categories, preferences)
        results = None
        for attempt in range(MAX_ATTEMPTS):
            try:
                results = call_llm(prompt, model_name)
                all_results.extend(results)
                break
            except Exception as e:
                wait = min(90, 15 * (attempt + 1))
                print(
                    f"  API error (attempt {attempt+1}/{MAX_ATTEMPTS}): {e}",
                    file=sys.stderr,
                    flush=True,
                )
                if attempt < MAX_ATTEMPTS - 1:
                    print(f"  Retrying in {wait}s...", flush=True)
                    time.sleep(wait)

        if not results:
            print(
                f"  SKIP batch {batch_num} after {MAX_ATTEMPTS} failures "
                f"(will retry on next workflow run)",
                flush=True,
            )
            continue

        output_path = DATA_DIR / "ai_output.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)
        merge_results(results, clear_temp=False)
        _push_progress(f"chore: catalog progress batch {batch_num}/{total_batches} [skip ci]")

        if batch_num < total_batches:
            time.sleep(DELAY_BETWEEN_BATCHES)

    print(f"Done: {len(all_results)} results", flush=True)


if __name__ == "__main__":
    main()