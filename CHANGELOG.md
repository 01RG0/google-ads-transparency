# Changelog

All notable changes are documented here.

---

## [Unreleased]

### Added
- Repo renamed to `google-ads-transparency`
- `CHANGELOG.md`

---

## [0.3.0] — 2026-11-10

### Added
- **Config system** (`client/config.py`): loads `ads-transparency.toml` + `.env` files
- `python -m client config init` — creates sample config and `.env`
- `python -m client config show` — shows active config and masked API keys
- All client settings (timeout, proxy, retries) and AI defaults configurable without CLI flags
- `ads-transparency.toml` added to `.gitignore`

### Changed
- `_collect_stats` now returns monthly activity distribution, avg region count, and trend direction
- `advertiser-stats` command shows peak months and geographic reach
- AI prompts fully rewritten with structured 6-section reports (Executive Summary, Format Strategy, Geographic Reach, Activity Patterns, Competitive Implications, Recommendations)
- `smart-compare` output now includes Head-to-Head Summary, What A/B Can Learn, Recommended Actions
- `suggest-keywords` samples 3 pages and outputs 6 keyword groups

### Fixed
- `config init` now warns user to add files to `.gitignore`

---

## [0.2.2] — 2026-11-10

### Added
- AI model **auto-detection** from provider `/models` endpoint — no more hardcoded model names
- Windows UTF-8 encoding fix for AI response output

### Fixed
- Groq default model was hardcoded and broke when Groq renamed models

---

## [0.2.1] — 2026-11-10

### Added
- **AI summarization** (`summarize-advertiser`, `smart-compare`, `suggest-keywords`)
- 6 AI providers via `httpx` with no extra dependencies: Groq, OpenAI, Anthropic, Together, Ollama, custom
- `list-creatives --all-pages` flag to fetch all results automatically
- README updated with all 11 CLI commands and AI providers table

---

## [0.2.0] — 2026-11-10

### Added
- **UX improvements**: `--format table|json|csv|xlsx` on all listing commands, `--output` for Excel
- `RPCModel.__repr__` for readable REPL output
- `Timestamp.to_datetime()` returning UTC `datetime`
- `SUPPORTED_REGIONS` list and `list_regions()` exported from package
- `AdvertiserSuggestion.ad_count_lower` / `ad_count_upper` fields
- **FastAPI**: typed `ErrorResponse` schema on all 502/404 responses, query parameter descriptions
- Proxy support: `proxy=` (single) and `proxies=` (rotating, random per request)
- All `ResponseShapeError` messages now include actual keys present in the response
- `fastapi` and `uvicorn` moved to `[api]` optional extra; `[excel]` extra for `openpyxl`

---

## [0.1.1] — 2026-11-10

### Added
- 5 new CLI commands: `find-advertisers`, `discover-competitors`, `advertiser-stats`, `compare-advertisers`, `download-previews`
- `client/downloader.py` for bulk preview image downloading
- `client/ai.py` multi-provider AI client (foundation)
- `SyncTransparencyClient` in `client/sync_client.py`
- `python -m client` CLI with 8 subcommands
- `get_advertiser_duns_mapping()` method + `DunsMappingEntry` model
- `paginate()` async generator on `TransparencyClient`
- `DunsMappingEntry` contract test and request-encoding test
- 23 tests total (up from 12)

---

## [0.1.0] — 2026-11-06

### Added
- Initial release
- `TransparencyClient` async client with 5 endpoints:
  - `search_advertisers`, `get_advertiser`, `list_creatives`, `search_by_domain`, `get_creative`
- Pydantic models: `Advertiser`, `AdvertiserSuggestion`, `Creative`, `CreativePage`, `CreativeDetail`
- 219-country geo target mapping with Palestine
- Throttling, retries with jitter, typed errors
- FastAPI facade (`api/app.py`)
- Contract tests against captured response samples
- CI workflow (push/PR) + daily smoke test with `continue-on-error` for live tests
- Apache 2.0 license
