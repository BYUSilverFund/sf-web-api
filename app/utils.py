import polars as pl
from datetime import date

import statsmodels.formula.api as smf
from app.db import engine


def account_id_to_name() -> dict:
    return {
        "U4297056": "undergrad",
        "U12702120": "quant",
        "U10797691": "brigham_capital",
        "U12702064": "grad",
        "DU8843649": "quant_paper",
    }


def get_account_id_from_name(name: str) -> str:
    account_map = {
        "undergrad": "U4297056",
        "quant": "U12702120",
        "brigham_capital": "U10797691",
        "grad": "U12702064",
        "quant_paper": "DU8843649",
    }

    if name in account_map:
        return account_map[name]
    else:
        raise ValueError(f"fund name not supported: {name}")


def calculate_alpha_beta(df: pl.DataFrame) -> tuple[float, float]:
    """
    calculate alpha and beta from a df with columns return_bmk and return_stk
        - return_bmk: a time series of benchmark returns
        - return_stk: a time series of asset returns
    """
    model = smf.ols("return_stk ~ return_bmk", df).fit()
    beta = model.params["return_bmk"].item()
    daily_alpha = model.params["Intercept"].item()
    alpha = daily_alpha * 252 * 100
    return alpha, beta


def get_benchmark_timeseries(start: date, end: date) -> pl.DataFrame:
    return pl.read_database(
        query="""
                SELECT 
                    date,
                    return
                FROM benchmark
                WHERE date BETWEEN :start AND :end
                ORDER BY date;
            """,
        connection=engine,
        execute_options={"parameters": {"start": start, "end": end}},
    ).select("date", pl.col("return").cast(pl.Float64))


def get_risk_free_timeseries(start: date, end: date) -> pl.DataFrame:
    return (
        pl.read_database(
            query="""
                SELECT * 
                FROM risk_free_rate
                WHERE date BETWEEN :start AND :end
                ORDER BY date;
            """,
            connection=engine,
            execute_options={"parameters": {"start": start, "end": end}},
        )
        .with_columns(pl.col("return").cast(pl.Float64))
        .sort("date")
    )
