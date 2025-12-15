import polars as pl
import polars_ols as pls  # noqa: F401
from app.models.download_data import (
    DownloadDataAllPortfolioRequest,
)

from app.db import engine
from app.utils import account_id_to_name


def get_portfolio_performance(
    request: DownloadDataAllPortfolioRequest,
) -> dict[str, any]:
    # (Date, Profile, Value, Returns, Dividends) for each fund
    stk = (
        pl.read_database(
            query=f"""
                SELECT *
                FROM fund_returns
                WHERE date BETWEEN '{request.start}' AND '{request.end}'
                ORDER BY date
                ;
            """,
            connection=engine,
        )
        .with_columns(pl.col(["value", "return", "dividends"]).cast(pl.Float64))
        .with_columns(pl.col("return").replace({-1: 0}))
        .with_columns(
            pl.col("client_account_id").replace(account_id_to_name()).alias("portfolio")
        )
        .sort("date")
        .select(
            "date",
            "portfolio",
            "value",
            "return",
            "dividends",
        )
    )
    if stk.is_empty():
        return {
            "start": request.start,
            "end": request.end,
            "timeseries_performance": [],
        }
    # (Benchmark Return) for each fund
    bmk = pl.read_database(
        query=f"""
                SELECT 
                    date,
                    return AS return_bmk
                FROM benchmark_new
                WHERE date BETWEEN '{request.start}' AND '{request.end}'
                ORDER BY date
                ;
            """,
        connection=engine,
    ).with_columns(pl.col("return_bmk").cast(pl.Float64))
    # (Risk Free rate ) for each fund
    rf = pl.read_database(
        query=f"""
                SELECT 
                    date,
                    return AS return_rf
                FROM risk_free_rate_new
                WHERE date BETWEEN '{request.start}' AND '{request.end}'
                ORDER BY date
                ;
            """,
        connection=engine,
    ).with_columns(pl.col("return_rf").cast(pl.Float64))

    # Join stk,bmk,rf together order by date
    df = (
        stk.join(rf, on="date", how="left")
        .join(bmk, on="date", how="left")
        .select(
            "date",
            "portfolio",
            "value",
            "return",
            "dividends",
            "return_bmk",
            "return_rf",
        )
        .sort("date", descending=True)
    )

    # gets the min and max date form the df (which comes from user input)
    # providing the range
    min_date = df["date"].min()
    max_date = df["date"].max()

    # shows the full fund-level time-series rows for the date range
    result = {
        "start": min_date,
        "end": max_date,
        "timeseries_performance": df.to_dicts(),
    }

    return result
