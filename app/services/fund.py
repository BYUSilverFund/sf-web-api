import polars as pl
from app.db import engine
import statsmodels.formula.api as smf
from app.models.fund import FundRequest


def get_fund_summary(request: FundRequest) -> dict[str, any]:
    stk = (
        pl.read_database(
            query=f"""
                SELECT * 
                FROM all_fund_returns 
                WHERE date BETWEEN '{request.start}' AND '{request.end}'
                ORDER BY date
                ;
            """,
            connection=engine,
        )
        .with_columns(pl.col("value", "return", "dividends").cast(pl.Float64))
        .sort("date")
        .with_columns(
            pl.col("return").add(1).cum_prod().sub(1).alias("cummulative_return")
        )
        .select("date", "value", "return", "cummulative_return", "dividends")
    )

    bmk = pl.read_database(
        query=f"""
                SELECT 
                    date,
                    return
                FROM benchmark_new
                WHERE date BETWEEN '{request.start}' AND '{request.end}'
                ORDER BY date;
            """,
        connection=engine,
    ).select("date", pl.col("return").cast(pl.Float64))

    rf = pl.read_database(
        query=f"""
                SELECT * 
                FROM risk_free_rate_new
                WHERE date BETWEEN '{request.start}' AND '{request.end}'
                ORDER BY date;
            """,
        connection=engine,
    ).with_columns(pl.col("return").cast(pl.Float64)).sort('date').with_columns(
        pl.col('return').add(1).cum_prod().sub(1).alias('cummulative_return')
    )

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

    model = smf.ols("return_stk ~ return_bmk", df_wide).fit()

    alpha = model.params["Intercept"].item() * 252
    beta = model.params["return_bmk"].item()

    total_return_rf = rf['cummulative_return'].tail(1).item() * 100

    value = stk["value"].tail(1).item()
    total_return = stk["cummulative_return"].tail(1).item() * 100
    volatility = stk["return"].std() * (252**0.5) * 100
    dividends = stk["dividends"].sum()
    dividend_yield = dividends / value * 100
    sharpe_ratio = (total_return - total_return_rf) / volatility
    tracking_error = df_wide["return_active"].std() * (252**0.5) * 100
    information_ratio = alpha / tracking_error

    result = {
        "start": request.start,
        "end": request.end,
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
            query=f"""
                SELECT * 
                FROM all_fund_returns 
                WHERE date BETWEEN '{request.start}' AND '{request.end}'
                ORDER BY date
                ;
            """,
            connection=engine,
        )
        .with_columns(pl.col("value", "return", "dividends").cast(pl.Float64))
        .sort("date")
        .with_columns(
            pl.col("return").add(1).cum_prod().sub(1).alias("cummulative_return")
        )
        .select("date", "value", "return", "cummulative_return", "dividends")
    )

    bmk = (
        pl.read_database(
            query=f"""
                SELECT 
                    date,
                    return
                FROM benchmark_new
                WHERE date BETWEEN '{request.start}' AND '{request.end}'
                ORDER BY date;
            """,
            connection=engine,
        )
        .with_columns(pl.col("return").cast(pl.Float64))
        .select(
            "date",
            "return",
            pl.col("return").add(1).cum_prod().sub(1).alias("cummulative_return"),
        )
    )

    records = (
        stk.join(bmk, on=["date"], suffix="_bmk", how="left")
        .sort("date")
        .with_columns(
            pl.col("return_bmk").fill_null(0),
            pl.col("cummulative_return_bmk").fill_null(strategy="forward"),
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

    result = {
        "start": request.start,
        "end": request.end,
        "records": records,
    }

    return result
