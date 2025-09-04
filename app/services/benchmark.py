import polars as pl
from app.db import engine
from app.models.benchmark import BenchmarkRequest


def get_benchmark_summary(request: BenchmarkRequest) -> dict[str, any]:
    bmk = (
        pl.read_database(
            query=f"""
                SELECT 
                    date,
                    adjusted_close,
                    return,
                    dividends_per_share
                FROM benchmark_new
                WHERE date BETWEEN '{request.start}' AND '{request.end}'
                ORDER BY date;
            """,
            connection=engine,
        )
        .with_columns(
            pl.col("adjusted_close", "return", "dividends_per_share").cast(pl.Float64)
        )
        .sort("date")
        .select(
            "date",
            "adjusted_close",
            "return",
            pl.col("return").add(1).cum_prod().sub(1).alias("cummulative_return"),
            "dividends_per_share",
        )
    )

    print(bmk)

    rf = (
        pl.read_database(
            query=f"""
                SELECT * 
                FROM risk_free_rate_new
                WHERE date BETWEEN '{request.start}' AND '{request.end}'
                ORDER BY date;
            """,
            connection=engine,
        )
        .with_columns(pl.col("return").cast(pl.Float64))
        .sort("date")
    )

    df_wide = (
        bmk.join(rf, on=["date"], suffix="_rf", how="left")
        .select(
            "date",
            "adjusted_close",
            "return",
            "cummulative_return",
            "dividends_per_share",
            pl.col("return_rf").fill_null(strategy="forward"),  # Fill last value
        )
        .with_columns(
            pl.col("return_rf").add(1).cum_prod().sub(1).alias("cummulative_return_rf"),
        )
        .sort("date")
    )

    n_days = len(df_wide["date"].unique())

    total_return_rf = df_wide["cummulative_return_rf"].last() * 100
    total_return_rf_annualized = total_return_rf * 252 / n_days

    total_return = df_wide["cummulative_return"].last() * 100
    total_return_annualized = total_return * 252 / n_days

    adjusted_close = df_wide["adjusted_close"].last()
    volatility = df_wide["return"].std() * (n_days**0.5) * 100
    volatility_annualized = df_wide["return"].std() * (252**0.5) * 100
    dividends_per_share = df_wide["dividends_per_share"].sum()
    dividend_yield = dividends_per_share / adjusted_close * 100
    sharpe_ratio = (
        total_return_annualized - total_return_rf_annualized
    ) / volatility_annualized

    min_date = bmk["date"].min()
    max_date = bmk["date"].max()

    result = {
        "start": min_date,
        "end": max_date,
        "adjusted_close": adjusted_close,
        "total_return": total_return,
        "volatility": volatility,
        "sharpe_ratio": sharpe_ratio,
        "dividends_per_share": dividends_per_share,
        "dividend_yield": dividend_yield,
    }

    return result


def get_benchmark_time_series(request: BenchmarkRequest) -> dict[str, any]:
    bmk = (
        pl.read_database(
            query=f"""
                SELECT 
                    date,
                    adjusted_close,
                    return,
                    dividends_per_share
                FROM benchmark_new
                WHERE date BETWEEN '{request.start}' AND '{request.end}'
                ORDER BY date;
                ;
            """,
            connection=engine,
        )
        .with_columns(
            pl.col("adjusted_close", "return", "dividends_per_share").cast(pl.Float64)
        )
        .sort("date")
        .select(
            "date",
            "adjusted_close",
            "return",
            pl.col("return").add(1).cum_prod().sub(1).alias("cummulative_return"),
            "dividends_per_share",
        )
    )

    records = (
        bmk.rename(
            {
                "return": "return_",
            }
        )
        .with_columns(
            pl.col(
                "return_",
                "cummulative_return",
            ).mul(100)
        )
        .to_dicts()
    )

    min_date = bmk["date"].min()
    max_date = bmk["date"].max()

    result = {
        "start": min_date,
        "end": max_date,
        "records": records,
    }

    return result
