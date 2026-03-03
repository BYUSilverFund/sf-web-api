# Silver Fund API Test Suite

Comprehensive test suite covering service layers, routes, authentication, and integration workflows.

## Test Structure

```
tests/
├── conftest.py                    # Shared fixtures and configuration
├── unit/
│   └── test_models.py            # Pydantic model validation tests
├── services/
│   ├── test_fund_service.py       # Fund service business logic
│   └── test_portfolio_service.py  # Portfolio service business logic
├── routes/
│   ├── test_fund_routes.py        # Fund API endpoints
│   └── test_portfolio_routes.py   # Portfolio API endpoints
├── auth/
│   ├── test_cognito_auth.py       # Cognito JWT validation
│   └── test_cors.py               # CORS middleware and error handling
└── integration/
    └── test_workflows.py          # End-to-end workflows
```

## Running Tests

### Install test dependencies
```bash
uv sync --all-extras
```

### Run all tests
```bash
pytest
```

### Run with coverage report
```bash
pytest --cov=app --cov-report=html
# Open htmlcov/index.html to view coverage
```

### Run specific test file
```bash
pytest tests/unit/test_models.py
```

### Run specific test class
```bash
pytest tests/services/test_fund_service.py::TestGetFundSummary
```

### Run specific test
```bash
pytest tests/services/test_fund_service.py::TestGetFundSummary::test_fund_summary_returns_correct_keys
```

### Run tests with specific marker
```bash
pytest -m unit          # Run unit tests
pytest -m service       # Run service tests
pytest -m route         # Run route tests
pytest -m auth          # Run auth tests
pytest -m integration   # Run integration tests
```

### Run tests verbosely
```bash
pytest -v
```

### Run tests with output capture disabled (see print statements)
```bash
pytest -s
```

## Test Coverage by Category

### ⭐⭐⭐ High Priority (40+ tests)

**Unit Tests** - Model Validation (10 tests)
- FundRequest validation
- PortfolioRequest validation
- FundSummaryResponse validation
- PortfolioSummaryResponse validation

**Service Tests** - Business Logic (25+ tests)
- get_fund_summary: Returns correct keys, calculates metrics, handles data
- get_fund_time_series: Records structure, sorting, percentages
- get_all_fund_time_series_csv: CSV generation and validity
- Portfolio equivalents for all above

### ⭐⭐ Very High Priority (30+ tests)

**Route Tests** - API Endpoints (20 tests)
- Fund summary/time-series/CSV endpoints (200 status, response schema, validation)
- Portfolio summary/time-series/CSV endpoints (same coverage)

**Auth Tests** - Security (10+ tests)
- Cognito JWT verification (valid tokens, missing fields, invalid algorithms)
- CORS headers and origin validation
- Error handling and messages

### ⭐ High Priority (25+ tests)

**Integration Tests** - Workflows (25+ tests)
- Fund vs. Portfolio data consistency
- CSV export consistency with time series
- Multiple portfolio requests
- Date range handling (1-week, multi-year, with weekends)
- Response data integrity

## Test Fixtures

### Database Fixtures (conftest.py)
- `sample_fund_returns_df`: 252 days of simulated fund returns
- `sample_benchmark_df`: Matching benchmark data
- `sample_risk_free_rate_df`: Risk-free rate data
- `mock_fund_db_read_database`: Mocks pl.read_database calls

### Authentication Fixtures
- `mock_cognito_jwks`: Mocks Cognito JWKS endpoint
- `valid_jwt_token`: Sample JWT token string
- `set_test_env_vars`: Sets required env vars for tests

### Standard Fixtures
- `test_client`: FastAPI TestClient for endpoint testing
- `sample_date_range`: Standard test date range (365 days)
- `mock_db_engine`: Mocked database engine

## Mocking Strategy

### Database
- All calls to `pl.read_database()` are mocked
- Returns sample data based on query content
- No actual database connection required

### Authentication
- Cognito JWKS endpoint mocked
- JWT token verification mocked
- Test runs without AWS credentials

### Environment Variables
- All required env vars set automatically via fixtures
- No need to configure .env for tests

## Running Against Real Database (Optional)

To test against actual database (requires DB setup):

```bash
# Override mocking by not patching pl.read_database
# Requires: DB credentials in environment
pytest --live-db
```

## Common Test Patterns

### Testing a route
```python
def test_endpoint_returns_200(test_client, mocker, sample_fund_returns_df):
    mocker.patch("polars.read_database", return_value=sample_fund_returns_df)
    
    response = test_client.post(
        "/endpoint",
        json={"param": "value"}
    )
    
    assert response.status_code == 200
```

### Testing service logic
```python
def test_calculation(mocker, sample_fund_returns_df):
    mocker.patch("polars.read_database", return_value=sample_fund_returns_df)
    
    request = FundRequest(start=date(2024, 1, 1), end=date(2024, 12, 31))
    result = get_fund_summary(request)
    
    assert result["total_return"] > 0
```

### Testing validation
```python
def test_invalid_input():
    with pytest.raises(ValueError):
        FundRequest(start="invalid-date", end="2024-12-31")
```

## Continuous Integration

Tests are designed to run in CI/CD pipelines:
- No external service dependencies (all mocked)
- Deterministic (no randomness except Hypothesis tests)
- Fast execution (~30-60 seconds total)
- Full coverage reports generated

## Coverage Goals

- **Unit Tests**: >95% coverage
- **Service Tests**: >90% coverage
- **Route Tests**: >90% coverage
- **Auth Tests**: >85% coverage
- **Integration Tests**: >80% coverage
- **Overall**: >85% coverage

## Adding New Tests

1. Follow existing patterns in relevant test file
2. Name tests descriptively starting with `test_`
3. Use provided fixtures from conftest.py
4. Add docstring explaining what's being tested
5. Mark with appropriate marker (@pytest.mark.unit, etc.)
6. Run locally before committing: `pytest --cov`
