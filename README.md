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
