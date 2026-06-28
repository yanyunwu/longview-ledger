---
name: recording-investment-operations
description: Use when the user reports buys, sells, adds, reductions, clears, dividends, transfers, cash changes, holdings, position percentages, planned operations, or any portfolio action to record in this workspace.
---

# Recording Investment Operations

## Core Rule

Transaction history is immutable. Append rows; do not rewrite old rows unless the user explicitly asks for correction.

## Workflow

1. Read `AGENTS.md`.
2. Parse the user's operation into `portfolio/transactions.csv`.
3. Ask a concise question only when a required field cannot be inferred safely.
4. If quantity or price is missing but position percentage is known, still record the operation with available fields and leave unknown fields blank.
5. Update `portfolio/positions.csv` only when enough data exists to do so safely; otherwise add a note row or leave positions unchanged.
6. For buy, add, reduce, sell, or clear actions, create a dated review stub in `reviews/trade_reviews/`.
7. Run `scripts/workspace_report.py`.

## Transaction Fields

Use the existing header:

```csv
datetime,asset_class,symbol,name,action,quantity,price,currency,amount,fee,account,position_pct,strategy_type,reason,expected_outcome,invalidation_condition,source_message,created_at
```

## Strategy Types

Use one of:

- `value_investment`
- `cycle_allocation`
- `small_position_speculation`
- `risk_hedge`
- `cash_management`
- `watch_only`

Mark news-driven small trades as `small_position_speculation`.

