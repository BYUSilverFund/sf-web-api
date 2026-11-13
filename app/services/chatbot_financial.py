"""Bounded read-only financial lookups that do not need model-guessed dates."""

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import text

from app.db import engine
from app.funds import FUND_ALIASES
from app.utils import get_account_id_from_name


def get_latest_dividends(fund: str, ticker: str | None = None) -> dict:
    """Positive recorded dividends on the latest available date for this fund."""
    with engine.connect() as connection:
        rows = (
            connection.execute(
                text("""
            WITH received AS (
                SELECT date, ticker, shares, dividends_per_share, dividends,
                       MAX(date) OVER () AS latest_date
                FROM holding_returns
                WHERE client_account_id = :account_id
                  AND dividends > 0 AND date <= CURRENT_DATE
                  AND (:ticker IS NULL OR ticker = :ticker)
            )
            SELECT date, ticker, shares, dividends_per_share, dividends
            FROM received WHERE date = latest_date
            ORDER BY ticker ASC LIMIT 51
        """),
                {"account_id": get_account_id_from_name(fund), "ticker": ticker},
            )
            .mappings()
            .all()
        )
    return {
        "fund": fund,
        "ticker": ticker,
        "date": rows[0]["date"] if rows else None,
        "dividends": [dict(row) for row in rows[:50]],
        "truncated": len(rows) > 50,
    }


FUND_VALUE_MAX_AGE_DAYS = 7


def compare_fund_values() -> dict:
    """Compare dashboard-reported values on one recent common date, never mixed dates."""
    funds = tuple(FUND_ALIASES)
    parameters = {}
    placeholders = []
    for index, fund in enumerate(funds):
        parameters[f"fund{index}"] = fund
        parameters[f"account{index}"] = get_account_id_from_name(fund)
        placeholders.append(f"(:fund{index}, :account{index})")
    query = text(
        """
        WITH allowed(fund, account_id) AS (VALUES """
        + ",".join(placeholders)
        + """),
        latest AS (
            SELECT a.fund, a.account_id, MAX(f.date) AS latest_date
            FROM allowed a LEFT JOIN fund_returns f
              ON f.client_account_id = a.account_id AND f.date <= CURRENT_DATE
             AND f.value IS NOT NULL
             AND f.value::text NOT IN ('NaN', 'Infinity', '-Infinity')
            GROUP BY a.fund, a.account_id
        )
        SELECT l.fund, l.latest_date, f.date, f.value,
               CURRENT_DATE AS reference_date
        FROM latest l LEFT JOIN fund_returns f
          ON f.client_account_id = l.account_id
         AND f.date BETWEEN CURRENT_DATE - 7 AND CURRENT_DATE
         AND f.value IS NOT NULL
         AND f.value::text NOT IN ('NaN', 'Infinity', '-Infinity')
        ORDER BY l.fund, f.date DESC
    """
    )
    with engine.connect() as connection:
        rows = connection.execute(query, parameters).mappings().all()
    if not rows:
        raise RuntimeError("Fund comparison returned no coverage metadata")
    reference_date = rows[0]["reference_date"]
    cutoff = reference_date - timedelta(days=FUND_VALUE_MAX_AGE_DAYS)
    coverage = {}
    values = {fund: {} for fund in funds}
    for row in rows:
        latest = row["latest_date"]
        coverage[row["fund"]] = {
            "fund": row["fund"],
            "latest_date": latest,
            "status": "unavailable"
            if latest is None
            else ("stale" if latest < cutoff else "included"),
        }
        if row["date"] is not None:
            values[row["fund"]][row["date"]] = Decimal(str(row["value"]))
    eligible = [fund for fund in funds if coverage[fund]["status"] == "included"]
    common = (
        set.intersection(*(set(values[fund]) for fund in eligible))
        if eligible
        else set()
    )
    as_of = max(common) if common else None
    ranking = (
        sorted(
            ({"fund": fund, "value": values[fund][as_of]} for fund in eligible),
            key=lambda row: row["value"],
            reverse=True,
        )
        if as_of
        else []
    )
    status = (
        "insufficient_data"
        if len(eligible) < 2
        else "no_common_date"
        if not common
        else "complete"
        if len(eligible) == len(funds)
        else "partial"
    )
    return {
        "metric": "reported_portfolio_value",
        "definition": "fund_returns.value: ending account value minus same-day net deposits/withdrawals; not per-share NAV, return, profit, or largest holding",
        "currency_note": "Stored reporting units; currency metadata is unavailable. No currency conversion or verified common currency is implied.",
        "reference_date": reference_date,
        "as_of_date": as_of,
        "max_age_days": FUND_VALUE_MAX_AGE_DAYS,
        "comparison_status": status,
        "coverage": [coverage[fund] for fund in funds],
        "ranking": ranking,
        "leaders": [
            row["fund"] for row in ranking if row["value"] == ranking[0]["value"]
        ]
        if len(ranking) >= 2
        else [],
        "scope_note": "Ranking covers included funds only. Excluded funds cannot be claimed smaller. All ranked values use the same date.",
    }
