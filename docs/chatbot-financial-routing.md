# Financial questions and fund-value comparisons

With **All Funds** selected, “What fund holds the highest value?” now routes to
`compare_fund_values`. The first ConverseStream request explicitly selects this
tool using Bedrock's supported `toolChoice.tool` setting, rather than leaving the
financial/document distinction entirely to the model. Other financial questions
retain automatic tool selection, with explicit financial grounding instructions.
Document questions retain the existing document-evidence fallback.

## Metric and source

The tool compares **reported portfolio value** from `fund_returns.value`, the same
metric used by the portfolio dashboards. The ingestion calculation is
`delta_nav.ending_value - delta_nav.deposits_withdrawals` (same-day net flows).
This is not a per-share NAV, profit, percentage return, or largest individual
holding. The existing top-positions tool cannot answer which fund has the largest
total portfolio.

Source definitions were checked in the sibling data pipeline's
`dags/sql/fund_returns_create.sql`, `fund_returns_materialize.sql`,
`delta_nav_create.sql`, and `tasks/s3_to_rds_sub_tasks/delta_nav_task.py`.
Neither the stored tables nor that transformation retains currency metadata.
Results therefore identify **stored reporting units**, without assuming USD,
performing currency conversion, or asserting verified currency equivalence.
A financially comparable common currency needs confirmation before interpreting
this ordering as currency-normalized economic size.

## Date and coverage policy

One read-only query uses the existing five supported fund/account mappings.
It accepts no model-supplied fund list, account identifiers, or SQL. Its recent
candidate output is bounded by five funds and eight dates per fund, plus missing
coverage rows. Historical latest-date metadata detects stale funds. Future,
null, and non-finite values are excluded.

The database's `CURRENT_DATE` defines freshness: values older than seven calendar
days are stale. Among funds with recent data, ranking uses the **latest common
available date**, never each fund's independently latest date. If there is no
common recent date, or fewer than two eligible funds, there is no winning fund.
Ties return all leaders. Missing and stale funds remain visible in coverage;
a partial ranking cannot establish that an excluded fund is smaller.

A read-only check on November 12, 2026 found four funds current through November
11 and Quant Paper last available September 24. That produces a partial comparison
of four funds on November 11, with Quant Paper explicitly excluded as stale.
No migration or database update is needed or performed.

## Isolation, failures and tracing

Cross-fund comparisons require All Funds. The comparison tool is omitted from
individual-fund requests and independently rejected by the server dispatcher.
A recognized comparative question with an individual fund selected asks the user
to select All Funds, without querying other funds.

If Bedrock does not request the required comparison, or its execution fails, the
request emits the existing controlled SSE error instead of inventing a ranking or
substituting a document fallback. Valid missing-data results are supplied to the
model so it can explain the limitation. Three tool-execution rounds and the final
bounded text-only response remain unchanged. Citations and `answerContexts` still
represent retrieved document evidence, not synthetic database excerpts.

Phoenix retains the existing request → round → model/tool span tree, model usage
and cost estimates. Comparison tool spans add only status, included-fund count,
and as-of date; portfolio balances and tool results are not exported as content.
Question/answer capture remains governed by the separate local opt-in controls.

Bedrock documentation: [Nova tool choice](https://docs.aws.amazon.com/nova/latest/nova2-userguide/prompting-tools-function.html).
The default Nova model supports specific-tool choice; an incompatible replacement
model will produce the existing controlled API error rather than a silent fallback.

## Validation

`tests/services/test_chatbot_fund_values.py` covers the exact reported question,
selected-fund isolation, tool argument validation, common-date alignment, stale and
missing coverage, ties, unavailable tools, ignored tool choice, document fallback,
SSE completion, Bedrock request validation, and Phoenix span validity.

Run the complete suite and lint from `sf-web-api`:

```bash
.venv/bin/pytest -q
.venv/bin/ruff check app tests
```

Local validation on November 12, 2026 completed the exact question through the
actual service generator, real retrieval/Bedrock, and database connections forced
read-only. It used one comparison tool and two inference calls, completed SSE,
and avoided the document fallback. Phoenix's authenticated local read API confirmed
all nine spans in `silverfund-local`, trace
`a92ac60182e97c82acdb74337966decf`. This was a service-level test; browser/Cognito
endpoint authentication was not exercised. No balances or credential values were
printed, and question/answer trace capture was disabled for this validation.

## Dividend yield versus dividend receipts

`get_latest_dividends` reports recorded payments and amounts per share, **not** a
yield percentage. A response must never rename `dividends_per_share` as yield.
The existing portfolio summary calculates its period dividend yield as recorded
period dividends divided by ending reported portfolio value, multiplied by 100;
the holding summary exposes the analogous ticker metric. These are period
measures, not automatically forward or annualized yields.

An unspecified request such as “what is our current dividend yeil” now asks for
trailing 12 months versus year-to-date, retaining the selected fund, rather than
querying the latest payment and substituting that amount. Common yield
misspellings are recognized. Explicit periods, definitions, and genuine
latest-dividend receipt questions retain the normal tool pipeline. The assistant
is stateless, so the clarification asks the user to include the period in the next
question. No default yield window, new financial calculation, database write,
or guessed financial figure is introduced.
