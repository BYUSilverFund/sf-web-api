# Chatbot fund-selector recovery

The original uncommitted implementation remains intact in the three
`.fund-selector/` worktrees on `feat/fund-selector`. Their baseline refs are
`sf-web-app:a2b4bd0`, `sf-web-api:3dc6bbf`, and `sf-chatbot:153ea05`.
The recovery integrates the reviewed feature into the active repositories without
replacing current source formatting, grounding prompts, evaluation evidence,
authentication, models, or Phoenix tracing. No Git merge/push or migration is needed.

## Runtime contract

`POST /chat/stream` accepts `{ "message": "...", "fund": "quant" }`.
`fund` is optional. Omitted/null/`all_funds`/`All funds`/`All Funds` preserves
unfiltered legacy retrieval. Reviewed aliases normalize to the five canonical IDs:
`grad`, `undergrad`, `quant`, `brigham_capital`, `quant_paper`. Invalid values return 422.

The UI defaults to All Funds, keeps selection through expanded/compact views,
labels historical messages, disables the selector while streaming, and retries
using the failed question's original selection. The adapter sends structured fund
metadata while retaining Cognito authentication and current SSE parsing.

A selected fund restricts document eligibility **before** cosine ordering and the
five-source limit. Eligible documents are that fund's explicitly assigned sources
plus explicitly shared sources with no fund. Unassigned sources remain available
only to All Funds. All Funds is not an aggregate financial tool.

Explicit questions naming another fund return clarification before any embedding,
retrieval, inference, or tool call. Tool execution injects the selection if its
fund is omitted and rejects conflicting tool arguments before financial services.
These are scope restrictions within existing authenticated access, not new access
permissions. Existing `sources` formatting and authoritative `answerContexts`
remain unchanged, including empty evidence for clarification responses.

All five pipeline spans retain metadata-only capture and asynchronous bounded
export. `silverfund.fund` records the canonical selection (`all_funds` for legacy
requests) on request, embedding, retrieval, inference and tool spans. Question,
answer, system prompt, retrieved text and tool payload capture remain disabled.

## Database and ingestion

The intended database already contains 109 indexed chunks for
`originals/manuals/quant/Quant Fund Manual.pdf`, assigned `quant`/`fund`. The
original migration evidence is retained in the original worktree. No backfill,
re-embedding or reindexing is needed. See [migration history](../migrations/README.md).

Recovered ingestion persists `fund` and `document_scope`. Missing incoming metadata
inherits a known persisted assignment; conflicting known metadata is rejected
before embedding and ownership is rechecked under the transaction's document lock
before replacement. This prevents a later extraction from silently discarding the
reviewed assignment. Document IDs, chunk IDs, text and physical page provenance
retain the existing contracts. The API-based evaluator remains authoritative;
no local RAG answer-generation runtime is restored in `sf-chatbot`.

## Start locally

From separate terminals:

```bash
cd /home/Gunnjake/projects/silverfund/sf-web-api
.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```bash
cd /home/Gunnjake/projects/silverfund/sf-web-app
NEXT_PUBLIC_FASTAPI_URL=http://localhost:8000 npm run dev -- --hostname 127.0.0.1 --port 3000
```

Stop any existing process occupying these ports first. The API's private `.env`
must allow `http://localhost:3000` in `CORS_ACCESS_LIST_CSV` and supply valid AWS,
Cognito, database and optional Phoenix settings. The existing env loader uses
`override=True`; setting API overrides only in the shell may be overwritten by
`.env`. No secret settings are included or changed by this recovery.

Open `http://localhost:3000`, sign in, and use Ask Silver Fund. The selector should
appear in both compact and expanded views. Network requests include the selected
fund. Asking for Grad while Quant is selected returns clarification without a
paid model call. A normal question needs the existing AWS/database access.

## Verification commands

API (from `sf-web-api`):

```bash
.venv/bin/pytest --no-cov -q
.venv/bin/ruff check app tests
```

Optional SELECT-only PostgreSQL filter fixtures:

```bash
FUND_FILTER_READ_ONLY_DB_TEST=1 .venv/bin/pytest tests/services/test_chatbot_fund_sql.py --no-cov -q
```

Ingestion/evaluation (from `sf-chatbot`; mocks only, opt-in database writes skipped):

```bash
.venv/bin/python -m unittest discover -s tests -q
```

Frontend (from `sf-web-app`):

```bash
npm test -- --run
npx next typegen
npx tsc --noEmit
npx eslint src/components/FundTabsBar.tsx src/components/assistant/SilverFundAssistant.tsx src/components/assistant/SilverFundAssistant.test.tsx src/lib/assistant/live.ts src/lib/assistant/live.test.ts src/lib/assistant/adapter.ts
```


## Recovery verification — November 12, 2026

- API: `FUND_FILTER_READ_ONLY_DB_TEST=1 .venv/bin/pytest --no-cov -q` —
  **218 passed**, including actual PostgreSQL SELECT-only filter checks, current
  evaluation consumer contract, tool isolation and streaming/tracing tests.
- Frontend: `npm test -- --run` — **187 passed**; route type generation,
  TypeScript `--noEmit`, focused ESLint and Prettier checks passed.
- Ingestion/evaluation: unittest discovery — **109 tests, 105 passed, 4 skipped**.
  Skipped tests require an explicitly isolated loopback pgvector database named
  `sf_test_*` via `SF_TEST_PGVECTOR_DSN`; no database-writing integration tests
  were run against the intended existing database. Existing API evaluator,
  saved-answer evaluation and retrieval experiment tests passed with mocks.
- Ruff lint and formatting checks passed for changed Python files.
- Read-only verification found exactly 109 Quant/fund chunks and the same
  protected embedding fingerprint as the original migration baseline. Actual
  API retrieval using one existing stored vector returned five sources for
  All Funds/Quant and zero for each other fund. No embedding/model call was used.
- Local Phoenix was initially stopped. The existing Docker service was started
  without changing its configuration or volume. Real authenticated OTLP export
  and read-back succeeded: trace `0c1b6339ed063f1025f086fca0519702`, six spans
  covering request, embedding, retrieval, two inference rounds and a tool.
  Every span carried `silverfund.fund=quant`; content attributes were absent.
  This smoke used real database reads but mocked model/financial service
  boundaries. A live Cognito-authenticated browser/Bedrock session was not run.
- The stream also completed during the initial collector outage. Offline tests
  continue to cover bounded asynchronous export and unavailable collectors.
- Original selector source/evidence hashes match the pre-recovery snapshot.
  All pre-existing dirty work was backed up to
  `/tmp/silverfund-selector-recovery-1794499689059924221/existing-work.tar.gz`.
  Private env files and generated dependency/cache directories were inventoried,
  left untouched, and excluded from the archive.
- No database writes, migrations, reindexing, model-setting changes, local RAG
  runtime restoration, branch merges, pushes, deployments or PRs were performed.

## Files changed by this recovery

Paths are relative to each repository. This inventory distinguishes recovery
changes from the pre-existing dirty chatbot UI and observability implementation.

sf-web-app:

- `README.md`
- `src/components/FundTabsBar.tsx`
- `src/components/assistant/SilverFundAssistant.test.tsx`
- `src/components/assistant/SilverFundAssistant.tsx`
- `src/components/assistant/assistant.css`
- `src/lib/assistant/adapter.ts`
- `src/lib/assistant/live.test.ts`
- `src/lib/assistant/live.ts`

sf-web-api:

- `README.md`
- `app/funds.py`
- `app/observability.py`
- `app/routers/chatbot.py`
- `app/services/chatbot.py`
- `app/services/chatbot_tools.py`
- `docs/chatbot-observability.md`
- `docs/fund-selector-recovery.md`
- `migrations/003_chatbot_fund_metadata.sql`
- `migrations/README.md`
- `tests/routes/test_chatbot.py`
- `tests/services/test_chatbot_fund_sql.py`
- `tests/services/test_chatbot_funds.py`
- `tests/services/test_chatbot_observability.py`

sf-chatbot:

- `app/funds.py`
- `app/ingestion/chunking.py`
- `app/ingestion/document.py`
- `app/retrieval/vector.py`
- `db/init/02-fund-metadata.sql`
- `docs/ingestion.md`
- `scripts/chunk_document.py`
- `scripts/ingest.py`
- `scripts/ingest_local.py`
- `tests/pgvector_fakes.py`
- `tests/test_document_ingestion.py`
- `tests/test_fund_metadata.py`
- `tests/test_pgvector_integration.py`
- `tests/test_vector.py`
