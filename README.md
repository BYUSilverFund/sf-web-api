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
```

## Development

Run the FastAPI app

```bash
uvicorn app.main:app --reload
```

Navigate to [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
