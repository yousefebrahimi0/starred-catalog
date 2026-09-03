#!/usr/bin/env python3
"""Build CATALOG.md and README.md from data/catalog.json."""

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


def category_anchor(name):
    return (
        name.lower()
        .replace(" ", "-")
        .replace("&", "")
        .replace("--", "-")
        .strip("-")
    )


def flatten_category(subs):
    repos = []
    for items in subs.values():
        repos.extend(items)
    return repos


def top_repo(repos):
    return max(repos, key=lambda r: r.get("stargazers_count") or 0)


def render_entry(repo):
    name = repo.get("full_name", "unknown")
    url = repo.get("html_url", f"https://github.com/{name}")
    purpose = repo.get("purpose", "")
    lang = repo.get("language", "")
    stars = repo.get("stargazers_count", 0)
    tags = repo.get("tags", [])
    star_str = f"⭐ {stars:,}" if stars else ""
    lang_str = f" `{lang}`" if lang else ""
    lines = [f"- [{name}]({url}){lang_str} {star_str}"]
    if purpose:
        lines.append(f"  {purpose}")
    if tags:
        lines.append(f"  Tags: {', '.join(tags[:5])}")
    lines.append("")
    return lines


def build_markdown(catalog, categories, now):
    lines = []
    lines.append("# My Starred Repositories Catalog")
    lines.append("")
    lines.append(
        f"**{len(catalog)}** repositories in **{len(categories)}** categories · Last updated: {now}"
    )
    lines.append("")

    lines.append("## Things I think are great and worth a check")
    lines.append("")
    lines.append(
        "One standout per category — the repo in that group with the most GitHub stars."
    )
    lines.append("")
    for cat in sorted(categories.keys()):
        repos = flatten_category(categories[cat])
        if not repos:
            continue
        best = top_repo(repos)
        name = best.get("full_name", "unknown")
        url = best.get("html_url", f"https://github.com/{name}")
        stars = best.get("stargazers_count", 0)
        purpose = best.get("purpose", "")
        star_str = f" — ⭐ {stars:,}" if stars else ""
        lines.append(f"- **{cat}:** [{name}]({url}){star_str}")
        if purpose:
            lines.append(f"  {purpose}")
    lines.append("")

    lines.append("## Table of Contents")
    lines.append("")
    for cat in sorted(categories.keys()):
        count = sum(len(repos) for repos in categories[cat].values())
        lines.append(f"- [{cat}](#{category_anchor(cat)}) ({count})")
    lines.append("")

    for cat in sorted(categories.keys()):
        subs = categories[cat]
        lines.append(f"## {cat}")
        lines.append("")
        for sub_name in sorted(subs.keys()):
            repos = subs[sub_name]
            if sub_name:
                lines.append(f"### {sub_name}")
                lines.append("")
            for repo in repos:
                lines.extend(render_entry(repo))

    return "\n".join(lines)


def main():
    catalog = load_json(DATA_DIR / "catalog.json")
    if not catalog:
        print("No catalog data, skipping")
        return

    categories = {}
    for item in catalog:
        cat = item.get("category", "Uncategorized")
        sub = item.get("subcategory", "")
        categories.setdefault(cat, {})
        categories[cat].setdefault(sub, [])
        categories[cat][sub].append(item)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    content = build_markdown(catalog, categories, now)

    CATALOG_MD.write_text(content, encoding="utf-8")
    README_MD.write_text(content, encoding="utf-8")

    print(f"CATALOG.md and README.md written: {len(catalog)} repos in {len(categories)} categories")


if __name__ == "__main__":
    main()
