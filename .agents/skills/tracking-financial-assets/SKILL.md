---
name: tracking-financial-assets
description: Use when updating this workspace's asset dossiers, financial research, valuation notes, K-line observations, thesis files, or operation suggestions for A-shares, Hong Kong stocks, US stocks, precious metals, or crypto assets.
---

# Tracking Financial Assets

## Core Rule

Separate facts, views, and actions. Do not overwrite user-written research; append dated updates.

## Workflow

1. Read `AGENTS.md`.
2. Locate the asset folder under `assets/{asset_class}/{symbol}_{name}/`; create it from `templates/` if missing.
3. Put structured facts in `financials/`, `kline/`, `news/`, or `raw/`.
4. Put analysis in `README.md`, `thesis.md`, `valuation.md`, and `observation_log.md`.
5. For each update, append a dated observation with: trigger, facts, judgment, valuation change, operation suggestion, and follow-up condition.
6. If current market, news, laws, prices, or reports matter, verify with current sources and include links.
7. Run `scripts/workspace_report.py` after structural changes.

## Protected Files

Append or create dated sections in these files; do not replace them wholesale:

- `thesis.md`
- `valuation.md`
- `observation_log.md`
- `news/related_news.md`

## Investment Language

Use research language: assumptions, scenarios, price bands, risks, invalidation conditions. Do not promise returns.

