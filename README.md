# Researcher Metrics API

Local API that fetches researcher metrics from Google Scholar and Scopus, designed to be called from an Excel macro.

## Architecture

```
Excel Macro → HTTP GET → FastAPI (localhost:8000) → Google Scholar (ScraperAPI)
                                                   → Scopus (Selenium + Brave)
```

## Why Not Vercel?

Vercel was the original deployment target but has two blocking limitations:

1. **No persistent browser**: Scopus requires a logged-in browser session (Selenium + Chrome/Brave). Vercel serverless functions are stateless and cannot run a browser process.
2. **60s function timeout**: Google Scholar scraping via ScraperAPI can take 30-90s per researcher due to anti-bot retries. Vercel's hobby plan caps at 60s, Pro at 300s — still unreliable for Scopus (30-45s page render).
3. **Read-only filesystem**: Selenium and pybliometrics both require writing to disk (driver cache, config files). Vercel only allows writes to `/tmp` which resets between invocations.

**Solution**: Run locally. The API starts once, keeps a persistent Brave browser session logged into Scopus, and caches results for 24h.

## Setup

### Requirements

- Python 3.10+
- Brave Browser installed at `C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe`

### Install dependencies

```bash
pip install -r requirements.txt
pip install selenium webdriver-manager
```

### Configuration

Credentials are hardcoded in `main.py` (lines 21-22). To change them edit:

```python
SCOPUS_EMAIL = "your@email.com"
SCOPUS_PASSWORD = "yourpassword"
```

ScraperAPI key (line 18):
```python
SCRAPER_KEY = "your_scraperapi_key"
```

### Run

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

First Scopus request opens a Brave window, logs into Scopus automatically (~20s), then navigates to the author page (~30-45s). Subsequent requests reuse the same session. Same ID requested again = instant (24h cache).

## API

```
GET /metrics?scholar_id=<id>&scopus_id=<id>
```

Both parameters are optional. Returns:

```json
{
  "scholar": {
    "name": "Author Name",
    "h_index": 4,
    "citations": 74,
    "i10_index": 3,
    "source": "google_scholar"
  },
  "scopus": {
    "name": "Author Name",
    "h_index": 4,
    "citations": 67,
    "documents": 10,
    "source": "scopus"
  }
}
```

## Excel Macro

The macro in the `.xlsm` file reads Google Scholar IDs from column H and Scopus IDs from column I, calls the API for each row, and writes h-index values to columns J (Scholar) and K (Scopus).

Timeout per row: 120s. If the API doesn't respond in time, the cell is written as `TIMEOUT`.

## Data Sources

| Source | Method | Speed | Coverage |
|--------|--------|-------|----------|
| Google Scholar | ScraperAPI HTTP scrape | ~1-5s | All public profiles |
| Scopus | Selenium + logged-in Brave session | ~30-45s first, instant cached | Requires Scopus account |
