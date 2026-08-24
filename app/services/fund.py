import polars as pl

from app.db import engine
from app.models.fund import FundRequest
from app.utils import (
    calculate_alpha_beta,
    get_benchmark_timeseries,
    get_risk_free_timeseries,
)


def get_fund_summary(request: FundRequest) -> dict[str, any]:
    stk = (
        pl.read_database(
            query="""
                SELECT * 
                FROM all_fund_returns 
                WHERE date BETWEEN :start AND :end
                ORDER BY date;
            """,
            connection=engine,
            execute_options={
                "parameters": {"start": request.start, "end": request.end}
            },
        )
        .with_columns(pl.col("value", "return", "dividends").cast(pl.Float64))
        .with_columns(
            pl.col("return").replace(
                {-1: 0}
            )  # TODO: Fix so that the first day in the max history isn't -1 return.
        )
        .sort("date")
        .with_columns(
            pl.col("return").add(1).cum_prod().sub(1).alias("cummulative_return")
        )
        .select("date", "value", "return", "cummulative_return", "dividends")
    )

    bmk = get_benchmark_timeseries(request.start, request.end)

    rf = get_risk_free_timeseries(request.start, request.end)

    df_wide = (
        stk.join(bmk, on=["date"], suffix="_bmk", how="left")
        .join(rf, on=["date"], suffix="_rf", how="left")
        .select(
            "date",
            pl.col("return").alias("return_stk"),
            "return_bmk",
            pl.col("return_rf").fill_null(strategy="forward"),  # Fill last value
            pl.col("return").sub("return_bmk").alias("return_active"),
        )
        .sort("date")
        .with_columns(pl.col("return_stk", "return_bmk").sub("return_rf"))
    )

    n_days = len(stk["date"].unique())

    total_return = stk["cummulative_return"].last() * 100

    avg_daily_return = stk["return"].mean()
    total_return_annualized = avg_daily_return * 252 * 100

    avg_daily_rf_return = df_wide["return_rf"].mean()
    total_return_rf_annualized = avg_daily_rf_return * 252 * 100

    alpha, beta = calculate_alpha_beta(df_wide)

    value = stk["value"].last()

    volatility = stk["return"].std() * (252**0.5) * 100

    dividends = stk["dividends"].sum()
    dividend_yield = dividends / value * 100

    sharpe_ratio = (total_return_annualized - total_return_rf_annualized) / volatility

    tracking_error = df_wide["return_active"].std() * (252**0.5) * 100

    annualized_active_return = df_wide["return_active"].mean() * 252 * 100

    information_ratio = (
        annualized_active_return / tracking_error if tracking_error != 0 else 0
    )

    min_date = stk["date"].min()
    max_date = stk["date"].max()

    result = {
        "start": min_date,
        "end": max_date,
        "trading_days": n_days,
        "value": value,
        "total_return": total_return,
        "volatility": volatility,
        "sharpe_ratio": sharpe_ratio,
        "dividends": dividends,
        "dividend_yield": dividend_yield,
        "alpha": alpha,
        "beta": beta,
        "tracking_error": tracking_error,
        "information_ratio": information_ratio,
    }

    return result


def get_fund_time_series(request: FundRequest) -> dict[str, any]:
    stk = (
        pl.read_database(
            query="""
                SELECT * 
                FROM all_fund_returns 
                WHERE date BETWEEN :start AND :end
                ORDER BY date;
            """,
            connection=engine,
            execute_options={
                "parameters": {"start": request.start, "end": request.end}
            },
        )
        .with_columns(pl.col("value", "return", "dividends").cast(pl.Float64))
        .with_columns(
            pl.col("return").replace(
                {-1: 0}
            )  # TODO: Fix so that the first day in the max history isn't -1 return.
        )
        .sort("date")
        .with_columns(
            pl.col("return").add(1).cum_prod().sub(1).alias("cummulative_return")
        )
        .select("date", "value", "return", "cummulative_return", "dividends")
    )

    bmk = (
        pl.read_database(
            query="""
                SELECT 
                    date,
                    return
                FROM benchmark
                WHERE date BETWEEN :start AND :end
                ORDER BY date;
            """,
            connection=engine,
            execute_options={
                "parameters": {"start": request.start, "end": request.end}
            },
        )
        .with_columns(pl.col("return").cast(pl.Float64))
        .select(
            "date",
            "return",
        )
    )

    records = (
        stk.join(bmk, on=["date"], suffix="_bmk", how="left")
        .sort("date")
        .with_columns(
            pl.col("return_bmk")
            .add(1)
            .cum_prod()
            .sub(1)
            .fill_null(strategy="forward")
            .alias("cummulative_return_bmk"),
        )
        .rename(
            {
                "return": "return_",
                "return_bmk": "benchmark_return",
                "cummulative_return_bmk": "benchmark_cummulative_return",
            }
        )
        .with_columns(
            pl.col(
                "return_",
                "cummulative_return",
                "benchmark_return",
                "benchmark_cummulative_return",
            ).mul(100)
        )
        .to_dicts()
    )

    min_date = stk["date"].min()
    max_date = stk["date"].max()

    result = {
        "start": min_date,
        "end": max_date,
        "records": records,
    }

    return result


def get_all_fund_time_series_csv(request: FundRequest) -> bytes:
    time_series = get_fund_time_series(request)
    df = pl.DataFrame(time_series["records"]).sort("date", descending=False)

    rf = (
        pl.read_database(
            query="""
                SELECT
                    date,
                    return AS risk_free_return
                FROM risk_free_rate
                WHERE date BETWEEN :start AND :end
                ORDER BY date;
            """,
            connection=engine,
            execute_options={
                "parameters": {"start": request.start, "end": request.end}
            },
        )
        .with_columns(pl.col("risk_free_return").cast(pl.Float64))
        .sort("date")
    )
    df = df.join(rf, on="date", how="left").with_columns(
        pl.col("risk_free_return").fill_null(strategy="forward")
    )
    df = df.with_columns(pl.col("risk_free_return").mul(100))

    return df.write_csv().encode("utf-8")
