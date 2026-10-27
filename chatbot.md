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

All valid Cognito users share the same chatbot data access. Expose only these explicitly defined read-only tools and enforce input validation and result limits in the API.

## Retrieval storage

The API embeds each question with Titan Text Embeddings V2 (1024 dimensions), retrieves up to five nearest indexed chunks, then streams Nova 2 Lite output. Model IDs can be overridden with `BEDROCK_EMBEDDING_MODEL_ID` and `BEDROCK_CHAT_MODEL_ID`.

The pgvector contract is in `migrations/001_chatbot_schema.sql`. Apply it once after enabling pgvector. `chatbot.ingestion_state` records each S3 source object and its indexing status; `chatbot.embeddings` stores the document chunks and 1024-dimension vectors. The API searches only rows whose ingestion state is `indexed`. Without indexed tables or documents, it still calls Bedrock and instructs the model to say the library is not indexed yet.
