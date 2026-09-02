#!/usr/bin/env python3
"""
Fetch all starred repositories from GitHub API.
Saves to data/stars_raw.json
"""

import os
import json
import sys
import time
import requests
from pathlib import Path

GITHUB_TOKEN = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    print("ERROR: GH_TOKEN or GITHUB_TOKEN env var required", file=sys.stderr)
    sys.exit(1)

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def fetch_all_stars(username: str):
    """Fetch all starred repos with pagination."""
    all_stars = []
    page = 1
    per_page = 100

    while True:
        url = f"https://api.github.com/users/{username}/starred"
        params = {"page": page, "per_page": per_page, "sort": "created", "direction": "desc"}

        resp = requests.get(url, headers=HEADERS, params=params)
        if resp.status_code != 200:
            print(f"ERROR: GitHub API {resp.status_code}: {resp.text}", file=sys.stderr)
            sys.exit(1)

        batch = resp.json()
        if not batch:
            break

        # Keep only needed fields
        for repo in batch:
            all_stars.append({
                "id": repo["id"],
                "full_name": repo["full_name"],
                "name": repo["name"],
                "description": repo.get("description") or "",
                "language": repo.get("language") or "",
                "stargazers_count": repo["stargazers_count"],
                "html_url": repo["html_url"],
                "topics": repo.get("topics", []),
                "owner_login": repo["owner"]["login"],
                "created_at": repo.get("created_at", ""),
                "pushed_at": repo.get("pushed_at", ""),
            })

        print(f"  Fetched page {page} ({len(batch)} repos)...")
        page += 1
        time.sleep(0.1)  # be nice

    return all_stars


def main():
    # Get authenticated user if not specified
    username = os.getenv("GH_USERNAME")
    if not username:
        resp = requests.get("https://api.github.com/user", headers=HEADERS)
        if resp.status_code == 200:
            username = resp.json()["login"]
        else:
            print("ERROR: Could not determine username. Set GH_USERNAME.", file=sys.stderr)
            sys.exit(1)

    print(f"Fetching starred repos for {username}...")
    stars = fetch_all_stars(username)

    out_path = DATA_DIR / "stars_raw.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(stars, f, ensure_ascii=False, indent=2)

    print(f"Done: {len(stars)} stars saved to {out_path}")


if __name__ == "__main__":
    main()