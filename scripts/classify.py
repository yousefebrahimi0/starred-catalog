#!/usr/bin/env python3
"""
Classify new starred repos using configurable LLM provider.
Supports: gemini, minimax (OpenAI-compatible), openai, anthropic
"""

import os
import sys
import json
import time
from pathlib import Path

PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "20"))
RPM = int(os.getenv("LLM_RPM", "15"))
DELAY_BETWEEN_BATCHES = 60.0 / RPM

DATA_DIR = Path(__file__).parent.parent / "data"
CATEGORIES_FILE = Path(__file__).parent.parent / "categories.yaml"
PREFERENCES_FILE = Path(__file__).parent.parent / "preferences.txt"


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


def call_minimax(prompt, model_name):
    """Call Minimax AI via OpenAI-compatible API."""
    from openai import OpenAI
    api_key = os.getenv("MINIMAX_API_KEY")
    base_url = os.getenv("MINIMAX_BASE_URL", "https://api.minimax.chat/v1")
    if not api_key:
        raise ValueError("MINIMAX_API_KEY required for minimax provider")
    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model_name or "minimax-m3",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=8192,
        response_format={"type": "json_object"} if "json" in model_name.lower() else None,
    )
    return parse_response(response.choices[0].message.content)


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
            "minimax": "minimax-m3",
            "openai": "gpt-4o-mini",
            "anthropic": "claude-3-5-sonnet-20241022",
        }
        model_name = defaults.get(PROVIDER, "gemini-3.6-flash")

    print(f"Classifying {len(inbox)} repos with {PROVIDER} ({model_name}) in batches of {BATCH_SIZE}...")

    all_results = []

    for i in range(0, len(inbox), BATCH_SIZE):
        batch = inbox[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(inbox) + BATCH_SIZE - 1) // BATCH_SIZE

        print(f"  Batch {batch_num}/{total_batches} ({len(batch)} repos)...")

        prompt = build_prompt(batch, categories, preferences)

        for attempt in range(3):
            try:
                results = call_llm(prompt, model_name)
                all_results.extend(results)
                break
            except json.JSONDecodeError as e:
                print(f"  JSON parse error (attempt {attempt+1}): {e}", file=sys.stderr)
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
            except Exception as e:
                print(f"  API error (attempt {attempt+1}): {e}", file=sys.stderr)
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)

        if batch_num < total_batches:
            time.sleep(DELAY_BETWEEN_BATCHES)

    output_path = DATA_DIR / "ai_output.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print(f"Done: {len(all_results)} results saved to {output_path}")


if __name__ == "__main__":
    main()