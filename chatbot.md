# Chatbot API

## Streaming chat endpoint

`POST /chat/stream` is implemented in `app/routers/chatbot.py` and registered in `app/main.py`.

- **Authentication:** Require `Authorization: Bearer <Cognito access token>` and validate it with the existing Cognito auth dependency. Reject missing or invalid tokens with `401`; use the verified user's immutable `sub` as the conversation owner.
- **Request:** `Content-Type: application/json`

  ```json
  { "message": "User's question" }
  ```

  The message must contain 1–4000 non-whitespace characters.

- **Response:** Stream Server-Sent Events (SSE) with `Content-Type: text/event-stream`. The client reads the response body incrementally.
- **Events:** Send `meta` once, zero or more `delta` chunks, `sources`, then `done`. Send a safe `error` event if processing fails.

  ```text
  event: meta\ndata: {"requestId":"..."}
  event: delta\ndata: {"text":"partial answer"}
  event: sources\ndata: {"sources":[{"citation":1,"documentKey":"...","page":1,"excerpt":"..."}]}
  event: done\ndata: {}
  ```

## LLM database tools and routes

The model must not generate or execute SQL. Nova 2 Lite receives typed tool definitions in `app/services/chatbot_tools.py`; `app/services/chatbot.py` validates and dispatches tool calls to existing read-only service functions, then returns their JSON results to Nova. Tool execution only occurs within the Cognito-protected `POST /chat/stream` request. Every valid Cognito user has the same chatbot data access, so no per-user fund mapping is required.

Resolve fund names through a server-side allowlist; never trust account IDs from the model. Parse date inputs as dates and bind every value as a SQL parameter—never interpolate model values into SQL. For example:

```python
connection.execute(
    text("""
        SELECT ... FROM fund_returns
        WHERE client_account_id = :account_id
          AND date BETWEEN :start_date AND :end_date
    """),
    {"account_id": fund_id, "start_date": args.start_date, "end_date": args.end_date},
)
```

Use a dedicated read-only database role scoped to the required views or query functions. Do not expose writes, auth data, or chatbot ingestion tables.

Wrap existing service functions as tools and return compact JSON (not CSV). The chatbot calls these functions inside the authenticated chat request; it does not need to make HTTP requests back to the API.

| Tool | Existing service / frontend route | Inputs | Returned data |
| --- | --- | --- | --- |
| `get_portfolio_summary` | `POST /portfolio/summary` | fund, start date, end date | Value, returns, Sharpe ratio, volatility, dividends, alpha, beta |
| `get_top_positions` | `POST /top-positions/` | fund | Latest top 10 positions by value |
| `get_holdings_summary` | `POST /all-holdings/summary` | fund, start date, end date | Summary metrics for each holding |
| `get_holding_summary` | `POST /holding/summary` | fund, ticker, start date, end date | Summary metrics for one holding |
| `get_trades` | `POST /portfolio/trades` or `/holding/trades` | fund, optional ticker, start date, end date | Matching trades |
| `get_dividends` | `POST /holding/dividends` | fund, ticker, start date, end date | Dividend history |

List tools accept an allowlisted `sort_by`, `sort_desc` (`true`, `false`, or `null` for the default direction), and `limit` from 1 to 50. The API validates sort columns and binds values; it never inserts model-provided SQL. Trades are grouped, sorted, and limited in SQL before per-trade metric calculations. Dividends are filtered, sorted, and limited in SQL. Summary calculations may read more than 50 historical rows as needed, but the chatbot returns no more than 50 list items. Top positions remain limited to 10.

All valid Cognito users share the same chatbot data access. Expose only these explicitly defined read-only tools and enforce input validation and result limits in the API.

## Retrieval storage

The API embeds each question with Titan Text Embeddings V2 (1024 dimensions), retrieves up to five nearest indexed chunks, then streams Nova 2 Lite output. Model IDs can be overridden with `BEDROCK_EMBEDDING_MODEL_ID` and `BEDROCK_CHAT_MODEL_ID`.

The pgvector contract is in `migrations/001_chatbot_schema.sql`. Apply it once after enabling pgvector. `chatbot.ingestion_state` records each S3 source object and its indexing status; `chatbot.embeddings` stores the document chunks and 1024-dimension vectors. The API searches only rows whose ingestion state is `indexed`. Without indexed tables or documents, it still calls Bedrock and instructs the model to say no usable document evidence is available.

Source excerpts use a 1,200-character soft target, extended only to a complete
Markdown block, with a 6,000-character hard cap per source and 24,000 characters
across all returned excerpts. Paragraphs (including inline math), contiguous
Markdown tables, fenced code, display math (`$$` / `\[...\]`), and LaTeX
environments are kept atomic. Oversized or unclosed blocks are omitted rather
than sliced; sources with no usable prefix are omitted. This cannot repair
content already cut during extraction or ingestion. Citation numbers retain
retrieval positions and may have gaps.

The model receives the same excerpts and source metadata as the SSE `sources`
event. Source objects add `truncated` (boolean) and may include `pdfPages`,
`pages`, `pageStart`, or `pageEnd` when stored on the chunk. These page fields
refer to the original chunk, including when only a prefix is shown. The existing
`page` remains the navigation fallback. Frontends should allow excerpts longer
than 1,200 characters, render complete Markdown, indicate `truncated`, accept
optional page metadata, and use `citation` rather than array position for labels.
The event sequence and existing required source fields are unchanged.


Shortened excerpts include the visible notice "Excerpt shortened by the API;
later source content is omitted." This is API status text, not quoted document
content, and is included in the model evidence and both character budgets.
If a complete prefix and its notice cannot fit together, the source is omitted
entirely. No notice-only or empty source cards are returned.
Optional page lists are accepted only as nonempty arrays of up to 100 positive
32-bit integers; malformed or oversized metadata is omitted. Scalar page-range
metadata must also contain positive 32-bit integers. This bounds metadata growth
as well as excerpt growth.

Validated against the current `sf-web-app` source parser and assistant renderer:
citation gaps are preserved and displayed correctly. The parser safely ignores
`pdfPages` and `truncated`, so the API's inline notice provides compatibility.
The current UI shows only `page`; displaying all spanning pages and a separate
truncation badge requires changes to `src/lib/assistant/adapter.ts`,
`src/lib/assistant/live.ts`, and
`src/components/assistant/SilverFundAssistant.tsx` in that repository.
No frontend files are changed by this API patch.

Local API validation: run
`pytest tests/routes/test_chatbot.py tests/services/test_chatbot_sources.py tests/services/test_chatbot_tools.py tests/auth/test_cognito_auth.py tests/auth/test_cors.py`.
In the Codex sandbox, Starlette's synchronous TestClient hangs in AnyIO's
cross-thread portal even for an unrelated minimal FastAPI app. The same route
tests pass outside the sandbox; this is independent of Bedrock or retrieval.

Document-answer instructions prioritize the requested definition or equation
before related optimization or scaling procedures. They preserve the distinction
between active, benchmark, and total portfolio weights, request concise symbol
explanations supported by the excerpts, and attach citations to the specific
supporting claims. A freely chosen scale should not be confused with an undefined
magnitude. Missing definitions or symbol meanings should be acknowledged rather
than supplied from assumptions. These instructions contain no document-specific
formulas or page rules and do not change retrieval, source budgets, or API fields.

Answers should be direct and avoid unnecessary follow-on claims. Generated
examples must be labeled as illustrations rather than document facts and remain
consistent with all stated constraints. The prompt disallows unsupported claims
about a manager's motives and asks the model to distinguish related quantities.

`tests/services/test_chatbot_prompt.py` checks the instructions sent to a mocked
Bedrock client using synthetic definition/procedure passages in both orders and
procedure-only evidence. These offline checks verify prompt construction,
evidence order, citation labels, and inference configuration. They do not measure
live model accuracy or prove that a generated answer will follow the instructions.
