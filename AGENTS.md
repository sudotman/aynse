# AGENTS.md

## Overview

This repository contains `aynse`, a typed Python library and CLI for NSE India market data plus a small RBI helper module.

Core capabilities:
- historical stock, index, and derivatives data
- bhavcopy and related archive downloads
- live market endpoints and option-chain helpers
- trading-holiday utilities
- batching, connection pooling, retry-aware HTTP access, and streaming helpers

## Repo Map

- `aynse/__init__.py`: top-level public exports
- `aynse/cli.py`: Click CLI entrypoint exposed as `aynse`
- `aynse/holidays.py`: holiday and trading-day helpers
- `aynse/util.py`: shared parsing, caching, and concurrency utilities
- `aynse/nse/history.py`: historical stock/index/derivatives APIs, CSV/DataFrame helpers, stock backend selection, bhavcopy fallback
- `aynse/nse/archives.py`: bhavcopy, bulk deals, index constituents, expiry helpers
- `aynse/nse/live.py`: live quote, market status, chart, option-chain, and announcement endpoints
- `aynse/nse/http_client.py`: resilient HTTP client behavior for NSE/Nifty endpoints
- `aynse/nse/connection_pool.py`: centralized client pooling
- `aynse/nse/request_batcher.py`: adaptive batching helpers
- `aynse/nse/streaming_processor.py`: low-memory streaming utilities
- `aynse/rbi/historical.py`: RBI historical helpers
- `tests/`: pytest suite with `offline`, `live`, and `e2e` markers
- `docs/` and `mkdocs.yml`: MkDocs documentation site
- `scripts/bump_version.py`: version bump helper used by release workflow

## Working Notes

- The package targets Python `>=3.9`.
- The version is sourced from `pyproject.toml`; `aynse/__init__.py` reads it from package metadata at runtime.
- Historical stock fetches can use multiple backends: `auto`, `nse`, `bhavcopy`, and `custom`.
- `auto` first tries NSE historical data, then falls back to bhavcopy reconstruction for past dates.
- Live NSE access is network-dependent and can be flaky due to cookies, anti-bot behavior, or upstream changes.
- Tests split cleanly by marker:
  - `pytest -m offline -v --tb=short`
  - `pytest -m live -v --tb=short`
  - `pytest -m e2e -v --tb=short`
- Docs are built with MkDocs Material and `mkdocstrings`.

## Safe Defaults For Future Agents

- Start with offline tests unless the task specifically targets live integrations.
- Prefer reading `README.md`, `tests/conftest.py`, and the relevant module before changing behavior.
- Keep CLI changes aligned with the underlying library calls in `aynse/cli.py`.
- Do not commit generated caches or local artifacts such as `__pycache__/`, `.pytest_cache/`, `site/`, or local cookie/cache files.
- Treat live-endpoint fixes carefully: small response-shape compatibility changes are common in this repo.
