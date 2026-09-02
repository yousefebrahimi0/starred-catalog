#!/usr/bin/env python3
"""
Main orchestrator: fetch → diff → classify → merge → build MD.
Run locally or from GitHub Actions.
"""

import json
import os
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def run_script(name):
    """Run a script module and check exit code."""
    print(f"\n{'='*50}")
    print(f"Running: {name}")
    print(f"{'='*50}")

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / name)],
        cwd=str(ROOT),
    )
    if result.returncode != 0:
        print(f"ERROR: {name} failed with exit code {result.returncode}", file=sys.stderr)
        sys.exit(result.returncode)


def main():
    mode = os.getenv("RUN_MODE", "auto")  # auto, bootstrap, incremental

    # Step 1: Fetch stars
    run_script("fetch_stars.py")

    # Step 2: Diff — identify new stars
    run_script("diff_new.py")

    # Step 3: Check inbox
    inbox_path = DATA_DIR / "inbox.json"
    if inbox_path.exists():
        with open(inbox_path, "r", encoding="utf-8") as f:
            inbox = json.load(f)
    else:
        inbox = []

    if not inbox:
        print("\nNo new repos to classify. Catalog is up to date.")
        return

    # Step 4: Classify with Gemini
    run_script("classify.py")

    # Step 5: Merge into catalog
    run_script("merge.py")

    # Step 6: Build CATALOG.md
    run_script("build_md.py")

    print("\nDone! CATALOG.md is ready.")


if __name__ == "__main__":
    main()