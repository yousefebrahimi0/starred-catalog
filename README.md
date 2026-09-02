# Starred Catalog

Private catalog of my GitHub starred repositories, auto-categorized with Gemini AI and updated via GitHub Actions.

## How It Works

```
GitHub Stars (fetch)
        ↓
Diff against catalog → inbox.json (new repos only)
        ↓
Gemini AI classification (batched, rate-limited)
        ↓
Merge into catalog.json (source of truth)
        ↓
Generate CATALOG.md (human-readable)
        ↓
Commit & push via Actions bot
```

## Files

| File | Purpose |
|------|---------|
| `CATALOG.md` | **The main output** — categorized, searchable list of all starred repos |
| `data/catalog.json` | Machine source of truth (do not edit manually) |
| `data/stars_raw.json` | Last raw fetch from GitHub API |
| `data/inbox.json` | Repos waiting for classification (usually empty) |
| `categories.yaml` | Locked taxonomy — edit this to adjust categories |
| `preferences.txt` | Guidance for Gemini on categorization focus |

## Secrets Required

Add these in **Settings → Secrets → Actions**:

| Secret | Description |
|--------|-------------|
| `GH_PAT` | GitHub Personal Access Token with `repo` scope (read stars, write this repo) |
| `GEMINI_API_KEY` | Google Gemini API key (free tier at AI Studio) |

## Usage

### Automatic
Runs daily at 06:00 UTC via GitHub Actions. Only new stars are classified.

### Manual / First bootstrap
1. Go to **Actions → Update Starred Catalog → Run workflow**
2. Check **full_recategorize** to wipe and rebuild from scratch
3. Click **Run workflow**

### Local development
```bash
pip install -r requirements.txt
export GH_TOKEN=<your-pat>
export GEMINI_API_KEY=<your-key>
export GH_USERNAME=yousefebrahimi0
python scripts/run.py
```

## Customization

- **Change categories**: Edit `categories.yaml` — add/remove categories and subcategories
- **Adjust focus**: Edit `preferences.txt` to tell Gemini what matters to you
- **Model/tuning**: Set `GEMINI_MODEL`, `BATCH_SIZE`, `GEMINI_RPM` in workflow env

## Structure of CATALOG.md

- Header with stats and timestamp
- Table of Contents with category counts
- Sections per category → optional subcategories
- Each entry: link, language, star count, purpose, tags

## Notes

- Never edits your existing stars or GitHub Lists
- Only writes to this repository
- Low-confidence items marked `needs_review` in catalog
- Bootstrap for 500+ stars takes several minutes (Gemini free tier limits)

## License

MIT — use, modify, fork as you wish.