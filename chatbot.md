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

Placeholder for the allowlisted API routes or service operations the LLM may invoke to query database-backed data. Define each tool's inputs, output, and authorization before implementation. Do not expose arbitrary SQL execution.

| Tool | API route or service | Inputs | Returned data | Authorization |
| --- | --- | --- | --- | --- |
| _TBD_ | _TBD_ | _TBD_ | _TBD_ | Authenticated user / _TBD_ |

The chatbot should expose only these explicitly defined tools to the model. Validate tool inputs and enforce user authorization in the API before querying the database.

## Retrieval storage

The API embeds each question with Titan Text Embeddings V2 (1024 dimensions), retrieves up to five nearest indexed chunks, then streams Nova 2 Lite output. Model IDs can be overridden with `BEDROCK_EMBEDDING_MODEL_ID` and `BEDROCK_CHAT_MODEL_ID`.

The pgvector contract is in `migrations/001_chatbot_schema.sql`. Apply it once after enabling pgvector. `chatbot.ingestion_state` records each S3 source object and its indexing status; `chatbot.embeddings` stores the document chunks and 1024-dimension vectors. The API searches only rows whose ingestion state is `indexed`. Without indexed tables or documents, it still calls Bedrock and instructs the model to say the library is not indexed yet.
