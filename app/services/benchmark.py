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

    adjusted_close = bmk["adjusted_close"].tail(1).item()
    total_return = bmk["cummulative_return"].tail(1).item() * 100
    volatility = bmk["return"].std() * (252**0.5) * 100
    dividends_per_share = bmk["dividends_per_share"].sum()
    dividend_yield = dividends_per_share / adjusted_close * 100
    sharpe_ratio = total_return / volatility

    result = {
        "start": request.start,
        "end": request.end,
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

    result = {
        "start": request.start,
        "end": request.end,
        "records": records,
    }

    return result
