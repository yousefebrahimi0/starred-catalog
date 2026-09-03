#!/usr/bin/env python3
"""
Merge AI classification results into the catalog.
Handles both initial bootstrap and incremental updates.
"""

import json
import os
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


def load_json(path):
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def merge_results(ai_output, clear_temp=True):
    catalog_path = DATA_DIR / "catalog.json"
    ai_output_path = DATA_DIR / "ai_output.json"
    inbox_path = DATA_DIR / "inbox.json"
    stars_path = DATA_DIR / "stars_raw.json"
    state_path = DATA_DIR / "state.json"

    catalog = load_json(catalog_path)
    catalog_by_id = {item["id"]: item for item in catalog}

    if not ai_output:
        print("No AI output to merge")
        return 0

    stars_raw = load_json(stars_path)
    stars_by_id = {s["id"]: s for s in stars_raw}

    new_count = 0
    updated_count = 0

    for result in ai_output:
        repo_id = result.get("id")
        if not repo_id:
            continue

        star_data = stars_by_id.get(repo_id, {})

        entry = {
            "id": repo_id,
            "full_name": star_data.get("full_name", f"unknown/{repo_id}"),
            "html_url": star_data.get("html_url", f"https://github.com/{star_data.get('full_name', '')}"),
            "description": star_data.get("description", ""),
            "language": star_data.get("language", ""),
            "stargazers_count": star_data.get("stargazers_count", 0),
            "topics": star_data.get("topics", []),
            "owner_login": star_data.get("owner_login", ""),
            "category": result.get("category", "Uncategorized"),
            "subcategory": result.get("subcategory", ""),
            "purpose": result.get("purpose", ""),
            "tags": result.get("tags", []),
            "confidence": result.get("confidence", "low"),
            "needs_review": result.get("needs_review", True),
        }

        if repo_id in catalog_by_id:
            old = catalog_by_id[repo_id]
            if result.get("confidence") in ("high", "medium") or old.get("confidence") == "low":
                catalog_by_id[repo_id] = entry
                updated_count += 1
        else:
            catalog_by_id[repo_id] = entry
            new_count += 1

    merged = sorted(
        catalog_by_id.values(),
        key=lambda x: (-x.get("stargazers_count", 0), x.get("full_name", "")),
    )
    save_json(catalog_path, merged)

    total = len(merged)
    needs_review = sum(1 for item in merged if item.get("needs_review"))

    state = load_json(state_path)
    if not isinstance(state, dict):
        state = {}
    state["last_merge"] = {
        "total": total,
        "new": new_count,
        "updated": updated_count,
        "needs_review": needs_review,
    }
    save_json(state_path, state)

    print(
        f"Merge complete: {total} total ({new_count} new, {updated_count} updated, {needs_review} need review)",
        flush=True,
    )

    if clear_temp:
        save_json(inbox_path, [])
        save_json(ai_output_path, [])

    return total


def main():
    ai_output = load_json(DATA_DIR / "ai_output.json")
    merge_results(ai_output, clear_temp=os.getenv("MERGE_KEEP_TEMP") != "true")


if __name__ == "__main__":
    main()
