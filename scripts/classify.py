#!/usr/bin/env python3
"""
Classify new starred repos using Gemini AI.
Reads data/inbox.json and categories.yaml, writes data/ai_output.json
"""

import os
import sys
import json
import time
import google.generativeai as genai
from pathlib import Path

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("ERROR: GEMINI_API_KEY env var required", file=sys.stderr)
    sys.exit(1)

genai.configure(api_key=GEMINI_API_KEY)

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "20"))
RPM = int(os.getenv("GEMINI_RPM", "15"))
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
    """Build the prompt for Gemini."""
    cat_lines = []
    for cat in categories.get("categories", []):
        cat_lines.append(f"  - {cat['name']}")
        for sub in cat.get("subcategories", []):
            cat_lines.append(f"    - {sub}")

    categories_str = "\n".join(cat_lines)

    # Format inbox items for prompt
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


def call_gemini(prompt):
    """Call Gemini with retry logic."""
    model = genai.GenerativeModel(MODEL_NAME)

    for attempt in range(3):
        try:
            response = model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.1,
                    "max_output_tokens": 8192,
                }
            )
            text = response.text.strip()
            # Strip markdown code fences if present
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
            return json.loads(text)
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

    return []


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

    print(f"Classifying {len(inbox)} repos in batches of {BATCH_SIZE}...")

    all_results = []

    # Process in batches
    for i in range(0, len(inbox), BATCH_SIZE):
        batch = inbox[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(inbox) + BATCH_SIZE - 1) // BATCH_SIZE

        print(f"  Batch {batch_num}/{total_batches} ({len(batch)} repos)...")

        prompt = build_prompt(batch, categories, preferences)
        results = call_gemini(prompt)
        all_results.extend(results)

        # Rate limit
        if batch_num < total_batches:
            time.sleep(DELAY_BETWEEN_BATCHES)

    # Save output
    output_path = DATA_DIR / "ai_output.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print(f"Done: {len(all_results)} results saved to {output_path}")


if __name__ == "__main__":
    main()