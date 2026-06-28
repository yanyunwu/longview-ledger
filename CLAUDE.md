# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

This is **not a software project**. It is a long-term financial-asset research workspace
("longview-ledger"). Most of the repo is human-written Markdown and machine-readable
CSV/JSON data; the only executable code lives in `scripts/`. Content is in Chinese
(asset classes are named `a股`, `港股`, `美股`, `贵金属`, `加密货币`).

The governing rule is **separation of facts, views, and actions**:
- **Facts** → CSV/JSON and sourced Markdown (`financials/`, `kline/`, `news/`, `raw/`, `data_raw/`).
- **Views** → `README.md`, `thesis.md`, `valuation.md`, `observation_log.md`, review notes.
- **Actions** → `portfolio/transactions.csv`, `portfolio/positions.csv`, `reviews/`.

Default investing posture is value investing. Short-term/news-driven trades are allowed
**only** when explicitly tagged `small_position_speculation` in the transaction's `strategy_type`.

`AGENTS.md` is the authoritative workspace charter — read it before acting. This file summarizes it.

## Data discipline (most important constraint)

- **Transaction history is immutable.** Append rows to `portfolio/transactions.csv`; never
  rewrite existing rows unless the user explicitly asks for a correction (then add a new
  dated row/note, don't edit in place).
- **Protected, append-only files** — add dated sections, never overwrite wholesale:
  `thesis.md`, `valuation.md`, `observation_log.md`, `news/related_news.md`, and everything
  under `portfolio/*.csv` and `reviews/**`.
- Do not delete user records unless explicitly asked.
- Use ISO dates: `YYYY-MM-DD` or `YYYY-MM-DD HH:mm:ss`.
- When recency matters (prices, news, filings, law), verify against current sources and cite
  links in the note — do not rely on memory.
- Never frame output as guaranteed returns. Use research language: assumptions, scenarios,
  price bands, risks, invalidation conditions.

## Architecture / layout

- `assets/{asset_class}/{symbol}_{name}/` — one dossier per symbol. Canonical dossier shape
  (currently fully populated only for `a股`): `README.md`, `thesis.md`, `valuation.md`,
  `observation_log.md`, `financials/financials.csv`, `kline/daily.csv`,
  `news/related_news.{md,csv}`, `raw/source_index.json`. The other asset-class folders exist
  but are empty placeholders.
- `assets/a股/_index.csv` — rolled-up ranking table across all A-share dossiers (rating,
  score, suggested weight, valuation + ROE metrics).
- `portfolio/` — `transactions.csv`, `positions.csv`, `allocation.md`, `account_snapshots/`.
- `news/` — `news_index.csv` plus `global/ macro/ industry/ company/ daily_digest/`.
- `reviews/` — `mistake_log.md`, `trade_reviews/`, `thesis_reviews/`, `monthly_reviews/`.
- `templates/` — copy these when creating a new dossier/log/review.
- `data_raw/` — raw API caches: `eastmoney/{code}_{finance,kline,profile,quote}.json`,
  `cninfo/{code}_announcements.json`, and generated batches under `generated_research/`.
- `.agents/skills/` — project-local skills; read the matching one before acting (see below).

### CSV schemas (use the existing headers verbatim — they have a UTF-8 BOM)
- transactions: `datetime,asset_class,symbol,name,action,quantity,price,currency,amount,fee,account,position_pct,strategy_type,reason,expected_outcome,invalidation_condition,source_message,created_at`
- news: `date,title,source,url,category,region,assets,tags,impact_direction,impact_horizon,confidence,summary,created_at`
- `action` ∈ buy/sell/add/reduce/clear/dividend/transfer_in/transfer_out/note
- `strategy_type` ∈ value_investment/cycle_allocation/small_position_speculation/risk_hedge/cash_management/watch_only

## Project-local skills

Before doing workspace work, read the relevant skill under `.agents/skills/`:
- `tracking-financial-assets/` — adding/updating a dossier, financials, valuation, K-line, thesis.
- `recording-investment-operations/` — any buy/sell/add/reduce/clear/dividend/transfer/cash/position change.
- `reviewing-investment-decisions/` — trade/thesis/monthly reviews, mistake logging.
- `tracking-financial-news/` — recording, classifying, or linking news.

After any structural change (new dossier, new files), run the health check below.

## Commands

The workspace pins a specific Python interpreter. Run the health check (verifies every
A-share dossier has all required files; exits non-zero if any are missing):

```powershell
& 'C:\Users\kirito\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\workspace_report.py
```

Syntax-check the scripts before committing changes to them:

```powershell
& 'C:\Users\kirito\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m py_compile scripts\generate_stock_research.py scripts\workspace_report.py
```

### `scripts/generate_stock_research.py`
Batch generator that fetches data from Eastmoney + cninfo APIs (stdlib `urllib` only, no
deps), scores stocks, allocates a model portfolio, and writes Markdown + `summary.csv`.
Important: it is **not parameterized** — the target symbol list (`STOCKS`) and output path
(`TARGET_DIR`) are hardcoded constants near the top of the file; edit them to retarget.
It caches every raw API response under the output dir's `_data/raw/` and reuses the cache
on rerun, so deleting a cache file forces a refetch of just that item.
