# AGENTS.md

## Workspace Purpose

This workspace is a long-term financial asset research system. Keep facts, views, and actions separate:

- Facts go into CSV/JSON and sourced Markdown notes.
- Views go into thesis, valuation, observation, and review Markdown.
- Actions go into `portfolio/transactions.csv`, `portfolio/positions.csv`, and `reviews/`.

The default investing style is value investing. Short-term speculation is allowed only as explicitly tagged small-position behavior.

## Directory Map

- `assets/`: asset research dossiers by asset class.
- `assets/a股/`: migrated A-share dossiers, one folder per symbol.
- `news/`: global, macro, industry, company, and daily news tracking.
- `portfolio/`: positions, transactions, account snapshots, and allocation policy.
- `reviews/`: trade reviews, thesis reviews, monthly reviews, and mistake log.
- `templates/`: reusable Markdown templates.
- `data_raw/`: raw source data cache.
- `scripts/`: generation and verification scripts.
- `skills/`: project-local skills for this workspace.

## Local Skills

Read the matching local skill before acting:

- `skills/tracking-financial-assets/SKILL.md`: use when adding or updating an asset dossier, financial research, valuation, K-line observations, or operation suggestions for a symbol.
- `skills/recording-investment-operations/SKILL.md`: use when the user says they bought, sold, added, reduced, cleared, transferred, received dividends, changed cash, or changed position sizing.
- `skills/reviewing-investment-decisions/SKILL.md`: use when reviewing a trade, wrong judgment, thesis change, monthly result, or lesson learned.
- `skills/tracking-financial-news/SKILL.md`: use when recording, classifying, or linking global, macro, industry, company, commodity, or crypto news.

## Data Discipline

- Do not delete user records unless explicitly asked.
- Append to protected human-written files instead of overwriting them: `thesis.md`, `valuation.md`, `observation_log.md`, `portfolio/*.csv`, and `reviews/**`.
- Keep transaction history immutable. Corrections should be new rows or clearly dated notes.
- Use ISO-like dates where possible: `YYYY-MM-DD` or `YYYY-MM-DD HH:mm:ss`.
- If live or recent market/news data matters, verify from current sources and cite links in the note.
- Never present investment output as guaranteed returns or personalized certainty. Use research language and state assumptions.

## Common Commands

Run workspace health check:

```powershell
& 'C:\Users\kirito\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\workspace_report.py
```

Compile scripts:

```powershell
& 'C:\Users\kirito\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m py_compile scripts\generate_stock_research.py scripts\workspace_report.py
```

