#!/usr/bin/env python3
"""
Diff stars_raw.json against catalog.json → inbox.json (new repos only).
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


def load_json(path):
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def main():
    stars = load_json(DATA_DIR / "stars_raw.json")
    catalog = load_json(DATA_DIR / "catalog.json")

    catalog_ids = {item["id"] for item in catalog}

    inbox = [s for s in stars if s["id"] not in catalog_ids]

    # Save inbox
    with open(DATA_DIR / "inbox.json", "w", encoding="utf-8") as f:
        json.dump(inbox, f, ensure_ascii=False, indent=2)

    print(f"Diff: {len(inbox)} new repos out of {len(stars)} total stars (catalog has {len(catalog)})")


if __name__ == "__main__":
    main()