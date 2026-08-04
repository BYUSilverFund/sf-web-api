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


## Debugging Server Errors

For 500 errors, CORS errors, or backend issues, connect to the EC2 instance and check `/var/log/web.stdout.log` first. You will often see CORS errors in the dev console, they are often not CORS errors and instead data issues. Most often rerunning an Airflow job will fix the issue.

Use to watch live while reproducing the issue.
```bash
tail -n 100 -f /var/log/web.stdout.log
```