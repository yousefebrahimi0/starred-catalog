#!/usr/bin/env python3
"""
Build CATALOG.md from data/catalog.json.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
CATALOG_MD = Path(__file__).parent.parent / "CATALOG.md"
README_MD = Path(__file__).parent.parent / "README.md"


def load_json(path):
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def main():
    catalog = load_json(DATA_DIR / "catalog.json")
    if not catalog:
        print("No catalog data, skipping")
        return

    # Group by category
    categories = {}
    for item in catalog:
        cat = item.get("category", "Uncategorized")
        sub = item.get("subcategory", "")
        if cat not in categories:
            categories[cat] = {}
        if sub:
            if sub not in categories[cat]:
                categories[cat][sub] = []
            categories[cat][sub].append(item)
        else:
            if "" not in categories[cat]:
                categories[cat][""] = []
            categories[cat][""].append(item)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = []
    lines.append(f"# Starred Repositories Catalog")
    lines.append("")
    lines.append(f"> Auto-generated from `data/catalog.json` — do not edit manually.")
    lines.append(f">")
    lines.append(f"> **{len(catalog)}** repositories in **{len(categories)}** categories")
    lines.append(f"> Last updated: {now}")
    lines.append("")

    # Table of Contents
    lines.append("## Table of Contents")
    lines.append("")
    for cat in sorted(categories.keys()):
        count = sum(len(repos) for repos in categories[cat].values())
        anchor = cat.lower().replace(" ", "-").replace("&", "").replace("--", "-").strip("-")
        lines.append(f"- [{cat}](#{anchor}) ({count})")
    lines.append("")

    # Each category section
    for cat in sorted(categories.keys()):
        subs = categories[cat]
        count = sum(len(repos) for repos in subs.values())

        lines.append(f"## {cat}")
        lines.append("")

        # Subcategories with repos
        for sub_name in sorted(subs.keys()):
            repos = subs[sub_name]

            if sub_name:
                lines.append(f"### {sub_name}")
                lines.append("")

            for repo in repos:
                name = repo.get("full_name", "unknown")
                url = repo.get("html_url", f"https://github.com/{name}")
                purpose = repo.get("purpose", "")
                lang = repo.get("language", "")
                stars = repo.get("stargazers_count", 0)
                tags = repo.get("tags", [])

                # One-liner entry
                star_str = f"⭐ {stars:,}" if stars else ""
                lang_str = f" `{lang}`" if lang else ""
                lines.append(f"- [{name}]({url}){lang_str} {star_str}")
                if purpose:
                    lines.append(f"  {purpose}")
                if tags:
                    lines.append(f"  Tags: {', '.join(tags[:5])}")
                lines.append("")

    content = "\n".join(lines)
    with open(CATALOG_MD, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"CATALOG.md written: {len(catalog)} repos in {len(categories)} categories")

    # Update README stats placeholder
    update_readme_stats(len(catalog), len(categories), now)


def update_readme_stats(total, categories, updated):
    """Update stats section in README if it exists."""
    if not README_MD.exists():
        return

    content = README_MD.read_text(encoding="utf-8")

    # Replace stats between markers
    start_marker = "<!-- STATS_START -->"
    end_marker = "<!-- STATS_END -->"

    if start_marker in content and end_marker in content:
        new_stats = f"""{start_marker}
- **{total}** repositories categorized
- **{categories}** categories
- Last updated: {updated}
{end_marker}"""
        import re
        content = re.sub(
            f"{start_marker}.*?{end_marker}",
            new_stats,
            content,
            flags=re.DOTALL
        )
        README_MD.write_text(content, encoding="utf-8")
        print("README.md stats updated")


if __name__ == "__main__":
    main()