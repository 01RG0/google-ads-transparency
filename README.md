# 🔍 ads-transparency-client

<p align="center">
  <a href="https://github.com/01RG0/google-ads/actions/workflows/ci.yml">
    <img src="https://github.com/01RG0/google-ads/actions/workflows/ci.yml/badge.svg" alt="CI">
  </a>
  <a href="https://github.com/01RG0/google-ads/actions/workflows/daily-smoke.yml">
    <img src="https://github.com/01RG0/google-ads/actions/workflows/daily-smoke.yml/badge.svg" alt="Daily Smoke">
  </a>
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="Apache 2.0 License">
  <img src="https://img.shields.io/badge/no%20auth-public%20API-brightgreen" alt="No Auth">
</p>

<p align="center">
  Typed async Python client for the <strong>Google Ads Transparency Center</strong> — the public database of every ad running on Google Search, YouTube, Shopping, Maps, and Play.<br>
  No authentication. No browser. Pure <code>httpx</code>.
</p>

---

## ✨ What you can do

| Feature | Command |
|---|---|
| Search advertisers by name or multiple keywords | `search-advertisers`, `find-advertisers` |
| Browse all ads for a brand or domain | `list-creatives`, `search-by-domain` |
| Discover who else advertises on a domain | `discover-competitors` |
| Deep stats: format mix, monthly trends, reach | `advertiser-stats` |
| Side-by-side advertiser comparison | `compare-advertisers` |
| AI-powered strategy summary | `summarize-advertiser` |
| AI head-to-head competitive analysis | `smart-compare` |
| AI keyword suggestions from competitor data | `suggest-keywords` |
| Bulk download ad preview images | `download-previews` |
| Export to Excel, JSON, or CSV | `--format xlsx\|json\|csv` |

---

## 🚀 Installation

**Requirements:** Python 3.11+

```bash
git clone https://github.com/01RG0/google-ads.git
cd google-ads

# Client only (httpx + pydantic)
pip install -e .

# + FastAPI server
pip install -e ".[api]"

# + Excel export
pip install -e ".[excel]"

# + Development / tests
pip install -e ".[dev]"
```

---

## ⚡ Quick start

### CLI

```bash
# Set up config and .env files
python -m client config init

# Add your API key to .env (get a free one at console.groq.com)
echo "GROQ_API_KEY=gsk_..." >> .env

# Search for a brand
python -m client search-advertisers Nike --limit 5

# See all their ads
python -m client list-creatives --advertiser AR16735076323512287233 --region US

# Get a full competitive intelligence report
python -m client summarize-advertiser AR16735076323512287233 --provider groq
```

### Python

```python
import asyncio
from client import TransparencyClient

async def main():
    async with TransparencyClient() as client:

        # Find advertisers
        results = await client.search_advertisers("Nike", limit=5)
        advertiser_id = results[0].advertiser_id

        # List creatives with filters
        page = await client.list_creatives(
            advertiser_id=advertiser_id,
            region="US",
            date_from="2026-01-01",
            date_to="2026-12-31",
        )
        print(f"Found ~{page.total_count} ads")

        # Paginate all results with async generator
        async for creative in client.paginate(advertiser_id=advertiser_id, region="EG"):
            print(creative.creative_id, creative.domain)

asyncio.run(main())
```

### Sync (no asyncio)

```python
from client.sync_client import SyncTransparencyClient

with SyncTransparencyClient() as client:
    advertisers = client.search_advertisers("Nike")
    for creative in client.paginate(advertiser_id=advertisers[0].advertiser_id):
        print(creative.creative_id)
```

---

## 🖥️ CLI Reference

### Discovery

```bash
# Search by one or multiple keywords — results deduplicated
python -m client search-advertisers Nike
python -m client find-advertisers pepsi cola "soft drink"

# Find all advertisers running ads on a domain
python -m client discover-competitors nike.com
```

### Creatives

```bash
# List with filters
python -m client list-creatives --advertiser AR123 --region US
python -m client list-creatives --domain nike.com --from 2026-01-01 --to 2026-12-31

# Fetch ALL pages automatically
python -m client list-creatives --domain nike.com --all-pages

# Export to Excel
python -m client list-creatives --domain nike.com --format xlsx --output nike.xlsx
```

### Analytics

```bash
# Deep stats: format mix, monthly trends, reach
python -m client advertiser-stats AR123 --pages 10

# Side-by-side comparison
python -m client compare-advertisers AR111 AR222
```

### AI Analysis

```bash
# Structured competitive intelligence report
python -m client summarize-advertiser AR123 --provider groq

# Head-to-head AI comparison
python -m client smart-compare AR111 AR222 --provider openai --model gpt-4o-mini

# Keyword strategy from competitor data
python -m client suggest-keywords nike.com --provider anthropic

# Use local Ollama (free, no key needed)
python -m client summarize-advertiser AR123 --provider ollama --model llama3.2
```

### Download

```bash
# Bulk download ad preview images
python -m client download-previews AR123 --output ./previews --limit 200
```

### Config

```bash
# Create ads-transparency.toml and .env in current directory
python -m client config init

# Create in ~/.config/ads-transparency/ (applies to all projects)
python -m client config init --global

# Show current config + masked API keys
python -m client config show
```

---

## ⚙️ Configuration

After `python -m client config init`, edit `ads-transparency.toml`:

```toml
[ai]
# AI provider used by default for all AI commands
provider = "groq"
# Pin a model, or leave commented to auto-detect from the provider's /models endpoint
# model = "qwen/qwen3.8-27b"

[client]
timeout = 20
min_interval = 0.25   # seconds between requests (rate limiting)
max_retries = 3
# proxy = "http://user:pass@proxy:8080"
# proxies = ["http://p1:8080", "http://p2:8080"]   # rotating

[cli]
format = "table"      # default output format: table | json | csv | xlsx
pages = 1
limit = 50
```

And add API keys to `.env`:

```bash
# Get a free key at console.groq.com
GROQ_API_KEY=gsk_...

# Other providers
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
# TOGETHER_API_KEY=...
```

**Priority order (highest wins):** CLI flag → env var → `.env` file → `ads-transparency.toml` → global config

---

## 🤖 AI Providers

All providers use `httpx` — no extra dependencies.

| Provider | Env variable | Notes |
|---|---|---|
| `groq` | `GROQ_API_KEY` | Free tier available at [console.groq.com](https://console.groq.com) — **recommended to start** |
| `openai` | `OPENAI_API_KEY` | GPT-4o-mini is fast and cheap |
| `anthropic` | `ANTHROPIC_API_KEY` | Claude Haiku |
| `together` | `TOGETHER_API_KEY` | 100+ open-source models |
| `ollama` | — | Local, 100% free — install [ollama.com](https://ollama.com) |
| `custom` | `AI_API_KEY` | Any OpenAI-compatible endpoint via `--base-url` |

> Model is **auto-detected** from the provider's `/models` endpoint on first call. Override with `--model` or pin in `ads-transparency.toml`.

---

## 🐍 Python API

### `TransparencyClient`

```python
client = TransparencyClient(
    timeout=20,
    min_interval=0.25,   # min seconds between requests
    max_retries=3,
    proxy="http://proxy:8080",          # single proxy
    proxies=["http://p1:8080", ...],    # rotating proxies
)
```

| Method | Returns |
|---|---|
| `search_advertisers(query, *, limit=10)` | `list[AdvertiserSuggestion]` |
| `get_advertiser(advertiser_id)` | `Advertiser \| None` |
| `list_creatives(advertiser_id, domain, region, date_from, date_to, cursor, *, page_size=40)` | `CreativePage` |
| `search_by_domain(domain, *, cursor, page_size=40)` | `CreativePage` |
| `paginate(advertiser_id, region, date_from, date_to, *, domain, page_size=40)` | `AsyncGenerator[Creative]` |
| `get_creative(advertiser_id, creative_id)` | `CreativeDetail \| None` |
| `get_advertiser_duns_mapping()` | `list[DunsMappingEntry]` |

### Filters

**Region:** ISO 3166-1 alpha-2 code (`US`, `EG`, `PS`) or full country name (`Egypt`, `Palestine`). Pass `"anywhere"` to disable.

**Date:** `YYYY-MM-DD` strings. Both `date_from` and `date_to` must be supplied together.

**Page size:** max 40.

### Models

```python
from client.models import Creative, CreativeDetail, Advertiser, Timestamp

# Readable repr in REPL
print(creative)
# Creative(advertiser_id='AR...', creative_id='CR...', domain='nike.com', format_type=1)

# Convert timestamp to Python datetime
dt = creative.last_shown.to_datetime()   # UTC datetime | None

# Ad count buckets on search suggestions
suggestion.ad_count_lower   # e.g. '9000'
suggestion.ad_count_upper   # e.g. '10000'
```

### Error types

```python
from client.errors import (
    TransparencyError,      # base
    ResponseShapeError,     # API returned unexpected shape
    UnsupportedFilterError, # e.g. unknown country code
    UpstreamHTTPError,      # non-2xx after retries
)
```

---

## 🌐 FastAPI server

```bash
pip install -e ".[api]"
uvicorn api.app:app --reload
```

Browse the interactive docs at **http://localhost:8000/docs** — all endpoints documented with typed request/response schemas and error models.

---

## 🧪 Tests

```bash
# Contract + request-encoding tests (no network, runs in ~0.3s)
pytest -m "not live"

# Live smoke tests against the real API
ADS_TRANSPARENCY_LIVE=1 pytest -m live
```

CI runs on every push and PR. Daily smoke tests run at 09:17 UTC with live tests isolated in a `continue-on-error` job so a transient Google outage never fails the main build.

---

## 🏗️ Project structure

```
ads-transparency-client/
├── client/
│   ├── client.py          # TransparencyClient (async httpx)
│   ├── sync_client.py     # SyncTransparencyClient wrapper
│   ├── models.py          # Pydantic models (Advertiser, Creative, ...)
│   ├── errors.py          # Exception hierarchy
│   ├── geo_targets.py     # Country → geo ID mapping (219 countries)
│   ├── ai.py              # Multi-provider AI client (Groq/OpenAI/Anthropic/...)
│   ├── config.py          # Config file + .env loader
│   ├── downloader.py      # Bulk preview image downloader
│   └── __main__.py        # CLI (12 subcommands)
├── api/
│   └── app.py             # FastAPI facade
├── tests/
│   ├── test_contract_samples.py   # Response shape contracts
│   ├── test_client_requests.py    # Request encoding
│   ├── test_sync_and_cli.py       # Sync wrapper + CLI
│   └── test_live.py               # Live smoke tests
├── docs/
│   ├── endpoints.md        # Full RPC endpoint documentation
│   └── samples/            # Captured response examples
└── .github/workflows/
    ├── ci.yml              # Push/PR tests
    └── daily-smoke.yml     # Daily live tests
```

---

## 📄 License

[Apache 2.0](LICENSE) — free to use, modify, and distribute, including commercially. Includes **explicit patent protection** — contributors cannot later sue you for patent infringement over code they contributed.

---

## 🙏 Acknowledgements

Built on top of Google's publicly accessible [Ads Transparency Center](https://adstransparency.google.com). All data returned is public information Google makes available for transparency purposes.
