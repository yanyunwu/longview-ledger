---
name: tracking-financial-news
description: Use when recording, classifying, summarizing, or linking global, macro, industry, company, central-bank, commodity, precious-metal, or crypto news to this workspace and its tracked assets.
---

# Tracking Financial News

## Core Rule

News is evidence, not a trade by itself. Record the fact first, then separately record impact and confidence.

## Workflow

1. Read `AGENTS.md`.
2. Verify current or recent news from reliable sources when recency matters.
3. Append one row to `news/news_index.csv`.
4. If the news affects a tracked asset, append to `assets/{asset_class}/{asset}/news/related_news.csv` and `related_news.md`.
5. If the news changes thesis, valuation, or risk, append a dated note to `observation_log.md`.
6. Use links and dates. Do not rely on vague memory for news.

## News Fields

Use the existing global header:

```csv
date,title,source,url,category,region,assets,tags,impact_direction,impact_horizon,confidence,summary,created_at
```

## Classifications

Categories: `global`, `macro`, `industry`, `company`, `policy`, `central_bank`, `commodity`, `crypto`.

Impact direction: `positive`, `negative`, `mixed`, `neutral`, `unknown`.

Impact horizon: `short`, `medium`, `long`.
