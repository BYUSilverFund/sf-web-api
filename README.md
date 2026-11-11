poke 
# Silver Fund Web API

Web API written in Python FastAPI for use with the Silver Fund dashboard.

## Setup

### Prerequisites

Install Python 3.13+ and pip.

### Installation

Create and activate a virtual environment:

```bash
python -m venv .venv
```

```bash
source .venv/bin/activate
# On Windows:
.venv\Scripts\Activate.ps1
```

Install runtime and development dependencies:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt
```

### Environment Configuration

Copy `example.env` to `.env` and configure your credentials:

Refer to [`example.env`](example.env) for full variable descriptions

## Development Environment

Install pre-commit hooks (optional):

```bash
pre-commit install
```

View installed dependencies:

```bash
pip list
```

Add a new dependency:

```bash
pip install package-name
```

Freeze dependencies after dependency changes:

```bash
pip freeze > requirements.txt
```

For development-only packages, update [requirements-dev.txt](requirements-dev.txt).

## Development

Run the FastAPI app:

```bash
uvicorn app.main:app --reload
```

API routes are listed at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) (or ReDoc at [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)).

### Authentication (AWS Cognito)

Sensitive routes (for example, `POST /covariance-matrix/latest`) are protected using AWS Cognito JWTs.

Configure the following environment variables in each environment (Dev/Prod) to point at the appropriate user pool and app client:

- `COGNITO_REGION` – AWS region of the Cognito user pool (e.g. `us-west-2`).
- `COGNITO_USER_POOL_ID` – ID of the Cognito User Pool.
- `COGNITO_APP_CLIENT_ID` – App client ID whose tokens are accepted by the API.

User registration is restricted via a Pre-Sign-Up Lambda trigger provisioned in `sf-aws-terraform` to validate email domains. The backend expects an `Authorization: Bearer <JWT>` header containing a valid Cognito access or ID token. In the browser, ensure your frontend obtains the token from Cognito (e.g. via Amplify/Auth) and forwards it on API requests.

### Abuse controls

The API rejects request bodies over 64 KiB by default and applies per-instance
rate and concurrency limits to Bedrock chat and CSV export endpoints. It emits a
request ID and a structured audit log for those routes without logging request
bodies or credentials. Configure the environment variables in `example.env` to
fit the deployment, and set an AWS WAF or ALB rate rule for a shared edge limit
and Bedrock account-level budget alarms/Service Quotas.

## Testing & Coverage

Testing is powered by **pytest** and **pytest-cov** (configured in [`pytest.ini`](pytest.ini)).

```bash
# Run all tests and generate terminal + HTML coverage reports
pytest

# Run tests by marker category
pytest -m unit          # Unit tests (models & helper functions)
pytest -m route         # API route & endpoint tests
pytest -m auth          # Authentication & CORS tests
pytest -m service       # Service layer tests
pytest -m integration   # End-to-end integration workflows

# Run a specific test file
pytest tests/routes/test_holdings.py
```

* Coverage reports are printed in the terminal and saved to `htmlcov/index.html`.

## Deployment & CI/CD (AWS Elastic Beanstalk)

The API is hosted on **AWS Elastic Beanstalk** (configured via [`Procfile`](Procfile) and provisioned in `sf-aws-terraform`).

### Automated CI/CD (GitHub Actions)
Deployments are automated via [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml):
- Pushes to **`dev`** $\rightarrow$ Deploys to Development Elastic Beanstalk environment.
- Pushes to **`prod`** $\rightarrow$ Deploys to Production Elastic Beanstalk environment.
- Workflow steps:
  1. Authenticates via AWS Federated OIDC.
  2. Runs a local smoke test against the `/health` endpoint with the `Procfile` launch command.
  3. Bundles application into `app.zip` and uploads to the deployment S3 bucket.
  4. Calls `aws elasticbeanstalk create-application-version` and updates the active EB environment.

### Manual Deployment (EB CLI)
You can deploy manually using the AWS EB CLI:
```bash
eb deploy <environment-name>
```

## Code Quality

We use **Ruff** for both linting and formatting. Make sure to lint and format before pushing to Github. Github Actions is set up to fail if ruff fails.

### Format Code

Format all Python files:

```bash
ruff format
```

Check formatting without making changes:

```bash
ruff format --check
```

### Lint Code

Run linter:

```bash
ruff check
```

Auto-fix linting issues:

```bash
ruff check --fix
```

## Pre-commit Hooks

We use **pre-commit** to automatically run Ruff linting and formatting before every commit.

### Setup (one-time)

After installing dependencies, install pre-commit hooks:

```bash
pre-commit install
```

### Usage

Hooks run automatically on `git commit`. You can also run manually:

```bash
# Run on all files
pre-commit run --all-files

# Run on staged files only
pre-commit run

# Update hook versions
pre-commit autoupdate
```

### Skip hooks (emergency only)

```bash
git commit --no-verify -m "emergency commit"
```

## Debugging Server Errors

For 500 errors, CORS errors, or backend issues, connect to the EC2 instance and check `/var/log/web.stdout.log` first. You will often see CORS errors in the dev console, they are often not CORS errors and instead data issues. Most often rerunning an Airflow job will fix the issue.

Use to watch live while reproducing the issue.
```bash
tail -n 100 -f /var/log/web.stdout.log
```

## Chatbot ownership and evaluation

This repository is the authoritative implementation for chatbot system prompts,
user-message construction, Bedrock inference settings, retrieval/excerpt bounds,
read-only tool definitions/execution, citation formatting and SSE serialization.
The authenticated `POST /chat/stream` route accepts `{ "message": "..." }` and
emits `meta`, `delta`, `sources`, `done`, or `error`. The existing `sf-web-app`
assistant uses a Cognito access token; deployment authentication is unchanged.

`sf-chatbot` owns ingestion, chunking, embeddings/indexing and evaluation. Its
response evaluator calls this development endpoint with a legitimate Cognito
access token and explicit `--allow-paid`; no local answer model is maintained.
The `sources` event now includes additive `answerContexts`: the exact evidence
blocks used in model message construction. Existing frontend clients can ignore
this additional field. API prompt text, excerpt selection, model IDs and inference
settings remain unchanged. An older deployment without this field is rejected by
the evaluator rather than scored using reconstructed evidence.

Current retrieval reads `chatbot.ingestion_state` and `chatbot.embeddings`, with
1024-dimensional normalized Titan V2 vectors. `migrations/001_chatbot_schema.sql`
is a legacy manifest/chunks schema; `002_chatbot_ingestion_schema.sql` describes
the current contract. Apply schema changes only as a separately reviewed action;
these files do not automatically migrate existing tables. No schema is applied
as part of the consolidation. Fund/document filtering and complete extraction
span/revision persistence are not currently implemented in this contract.

Offline verification runs with `pytest`; tests cover the actual production API
code with external services mocked. `tests/services/test_chatbot_evaluation_contract.py`
checks evidence parity, current SQL and the actual sibling `sf-chatbot` SSE parser
when available. Set `SF_EVALUATION_ADAPTER` to that parser's absolute path for other
checkout layouts. With an isolated API checkout, only the sibling consumer check
skips. No permanent development server is needed for these tests.

Phoenix remains future work: developer-only trace access, authenticated response
ratings tied to request IDs, and possible agent-assisted diagnosis with reviewed
changes. No Phoenix dependencies, service or instrumentation are introduced here.
See the sibling `sf-chatbot/docs/evaluation.md` for authenticated development
commands, paid judge opt-in, historical rescoring and limitations.
