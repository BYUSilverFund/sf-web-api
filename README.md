# Silver Fund Web API

Web API written in Python FastAPI for use with the Silver Fund dashboard.

## Setup

Create virtual environemnt

```bash
python -m venv .venv
```

Activate virtual environment

```bash
source .venv/bin/activate
.venv\Scripts\Activate 
```

Install dependencies

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt  # For development tools
```

Install pre-commit hooks

```bash
pre-commit install
```

## Development

Run the FastAPI app

```bash
uvicorn app.main:app --reload
```

API routes are listed at to [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### Authentication (AWS Cognito)

Sensitive routes (for example, `POST /covariance-matrix/latest`) are protected using AWS Cognito JWTs.

Configure the following environment variables in each environment (Dev/Prod) to point at the appropriate user pool and app client:

- `COGNITO_REGION` – AWS region of the Cognito user pool (e.g. `us-east-1`).
- `COGNITO_USER_POOL_ID` – ID of the Cognito User Pool.
- `COGNITO_APP_CLIENT_ID` – App client ID whose tokens are accepted by the API.

The backend expects an `Authorization: Bearer <JWT>` header containing a valid Cognito access or ID token. In the browser, ensure your frontend obtains the token from Cognito (e.g. via Amplify/Auth) and forwards it on API requests.

## Code Quality

We use **Ruff** for both linting and formatting. Make sure to lint and format before pushing to Github. Github Actions is set up to fail ruff fails.

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
