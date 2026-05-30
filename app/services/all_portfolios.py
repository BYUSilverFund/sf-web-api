import polars as pl
import polars_ols as pls  # noqa: F401

from app.db import engine
from app.models.all_portfolios import AllPortfoliosRequest
from app.utils import account_id_to_name


def get_all_portfolios_summary(request: AllPortfoliosRequest) -> dict[str, any]:
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
        .with_columns(pl.col("value", "return", "dividends").cast(pl.Float64))
        .with_columns(pl.col("return").replace({-1: 0}))
        .sort("date")
        .with_columns(
            pl.col("return")
            .add(1)
            .cum_prod()
            .sub(1)
            .over("client_account_id")
            .alias("cummulative_return"),
            pl.col("client_account_id")
            .replace(account_id_to_name())
            .alias("portfolio"),
        )
        .select(
            "date", "portfolio", "value", "return", "cummulative_return", "dividends"
        )
    )

    bmk = pl.read_database(
        query=f"""
                SELECT 
                    date,
                    return
                FROM benchmark
                WHERE date BETWEEN '{request.start}' AND '{request.end}'
                ORDER BY date;
            """,
        connection=engine,
    ).select("date", pl.col("return").cast(pl.Float64))

    rf = (
        pl.read_database(
            query=f"""
                SELECT * 
                FROM risk_free_rate
                WHERE date BETWEEN '{request.start}' AND '{request.end}'
                ORDER BY date;
            """,
            connection=engine,
        )
        .with_columns(pl.col("return").cast(pl.Float64))
        .sort("date")
    )

    portfolios = (
        stk.join(rf, on="date", how="left", suffix="_rf")
        .join(bmk, on="date", how="left", suffix="_bmk")
        .with_columns(
            pl.col("return_rf").fill_null(strategy="forward")  # Fill last value
        )
        .with_columns(
            pl.col("return_rf")
            .add(1)
            .cum_prod()
            .sub(1)
            .over("portfolio")
            .alias("cummulative_return_rf"),
            pl.col("return_bmk")
            .add(1)
            .cum_prod()
            .sub(1)
            .over("portfolio")
            .alias("cummulative_return_bmk"),
        )
        .with_columns(
            pl.col("return").sub("return_rf").alias("xs_return"),
            pl.col("return_bmk").sub("return_rf").alias("xs_return_bmk"),
            pl.col("return").sub(pl.col("return_bmk")).alias("active_return"),
        )
        .sort("date")
        .group_by("portfolio")
        .agg(
            pl.col("date").n_unique().alias("n_days"),
            pl.col("value").last(),
            pl.col("cummulative_return").last().alias("total_return"),
            pl.col("cummulative_return_rf").last().alias("total_return_rf"),
            pl.col("cummulative_return_bmk").last().alias("total_return_bmk"),
            pl.col("return").mean().alias("avg_daily_return"),
            pl.col("return_rf").mean().alias("avg_daily_rf_return"),
            pl.col("active_return").mean().alias("avg_daily_active_return"),
            pl.col("return").std().alias("volatility"),
            pl.col("dividends").sum(),
            pl.col("active_return").std().alias("tracking_error"),
            pl.col("xs_return").least_squares.ols(
                pl.col("xs_return_bmk"), mode="coefficients", add_intercept=True
            ),
        )
        .unnest("coefficients")
        .rename({"xs_return_bmk": "beta", "const": "alpha"})
        .with_columns(
            pl.col("alpha").mul(252).alias("alpha"),
            pl.col("tracking_error")
            .mul(pl.lit(252).sqrt())
            .alias("tracking_error_annualized"),
            pl.col("avg_daily_return").mul(252).alias("total_return_annualized"),
            pl.col("avg_daily_rf_return").mul(252).alias("total_return_rf_annualized"),
            pl.col("avg_daily_active_return")
            .mul(252)
            .alias("annualized_active_return"),
            pl.col("volatility").mul(pl.lit(252).sqrt()).alias("volatility_annualized"),
        )
        .with_columns(
            pl.col("total_return_annualized")
            .sub("total_return_rf_annualized")
            .truediv("volatility_annualized")
            .alias("sharpe_ratio"),
            pl.col("dividends").truediv("value").alias("dividend_yield"),
            pl.col("annualized_active_return")
            .truediv("tracking_error_annualized")
            .alias("information_ratio"),
        )
        .with_columns(
            pl.col(
                "total_return",
                "total_return_rf",
                "dividend_yield",
                "alpha",
            ).mul(100)
        )
        .with_columns(
            pl.col("volatility_annualized").mul(100).alias("volatility"),
            pl.col("tracking_error_annualized").mul(100).alias("tracking_error"),
        )
        .select(
            "portfolio",
            "value",
            "total_return",
            "total_return_rf",
            "volatility",
            "sharpe_ratio",
            "dividends",
            "dividend_yield",
            "alpha",
            "beta",
            "tracking_error",
            "information_ratio",
        )
        .sort("value", descending=True)
        .to_dicts()
    )

    min_date = stk["date"].min()
    max_date = stk["date"].max()

    result = {
        "start": min_date,
        "end": max_date,
        "trading_days": stk["date"].n_unique(),
        "portfolios": portfolios,
    }

    return result


def get_all_portfolios_timeseries_csv(request: AllPortfoliosRequest) -> bytes:
    stk = (
        pl.read_database(
            query=f"""
                SELECT *
                FROM fund_returns
                WHERE date BETWEEN '{request.start}' AND '{request.end}'
                ORDER BY date;
            """,
            connection=engine,
        )
        .with_columns(pl.col("value", "return", "dividends").cast(pl.Float64))
        .with_columns(pl.col("return").replace({-1: 0}))
        .sort("date")
        .with_columns(
            pl.col("return")
            .add(1)
            .cum_prod()
            .sub(1)
            .over("client_account_id")
            .alias("cummulative_return"),
            pl.col("client_account_id")
            .replace(account_id_to_name())
            .alias("portfolio"),
        )
        .select(
            "date",
            "portfolio",
            "value",
            "return",
            "cummulative_return",
            "dividends",
        )
    )

    bmk = pl.read_database(
        query=f"""
                SELECT date, return
                FROM benchmark
                WHERE date BETWEEN '{request.start}' AND '{request.end}'
                ORDER BY date;
            """,
        connection=engine,
    ).select(
        "date",
        pl.col("return").cast(pl.Float64).alias("benchmark_return"),
    )

    rf = pl.read_database(
        query=f"""
                SELECT date, return
                FROM risk_free_rate
                WHERE date BETWEEN '{request.start}' AND '{request.end}'
                ORDER BY date;
            """,
        connection=engine,
    ).select(
        "date",
        pl.col("return").cast(pl.Float64).alias("risk_free_return"),
    )

    ts = (
        stk.join(bmk, on="date", how="left")
        .join(rf, on="date", how="left")
        .with_columns(
            pl.col("risk_free_return").fill_null(strategy="forward"),
            pl.col("benchmark_return")
            .add(1)
            .cum_prod()
            .sub(1)
            .over("portfolio")
            .alias("benchmark_cummulative_return"),
        )
        .select(
            pl.col("date"),
            pl.col("portfolio"),
            pl.col("value").alias("portfolio_value"),
            pl.col("return").alias("return_"),
            pl.col("cummulative_return"),
            pl.col("dividends"),
            pl.col("benchmark_return"),
            pl.col("benchmark_cummulative_return"),
            pl.col("risk_free_return"),
        )
        .sort(["date", "portfolio"], descending=[False, False])
    )

    return ts.write_csv().encode("utf-8")
