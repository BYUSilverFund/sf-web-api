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
        .with_columns(
            pl.col('return').replace({-1: 0}) # TODO: Fix so that the first day in the max history isn't -1 return.
        )
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
    ).with_columns(pl.col("return").cast(pl.Float64)).sort('date')

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
        .with_columns(
            pl.col('return_rf').add(1).cum_prod().sub(1).alias('cummulative_return_rf')
        )
        .sort("date")
        .with_columns(pl.col("return_stk", "return_bmk").sub("return_rf"))
    )

    model = smf.ols("return_stk ~ return_bmk", df_wide).fit()


    alpha = model.params["Intercept"].item() * 100 * 252
    beta = model.params["return_bmk"].item()

    n_days = len(stk['date'].unique())
    total_return_rf = df_wide['cummulative_return_rf'].last() * 100 
    total_return_rf_annualized = total_return_rf * 252 / n_days

    value = stk["value"].last()
    total_return = stk["cummulative_return"].last() * 100
    total_return_annualized = total_return * 252 / n_days
    volatility = stk["return"].std() * 100 * (252**0.5)
    dividends = stk["dividends"].sum()
    dividend_yield = dividends / value * 100
    sharpe_ratio = (total_return_annualized - total_return_rf_annualized) / volatility
    tracking_error = df_wide["return_active"].std() * (252**0.5) * 100
    information_ratio = alpha / tracking_error

    min_date = stk['date'].min()
    max_date = stk['date'].max()

    result = {
        "start": min_date,
        "end": max_date,
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
        .with_columns(
            pl.col('return').replace({-1: 0}) # TODO: Fix so that the first day in the max history isn't -1 return.
        )
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
        )
    )

    records = (
        stk.join(bmk, on=["date"], suffix="_bmk", how="left")
        .sort("date")
        .with_columns(
            pl.col("return_bmk").add(1).cum_prod().sub(1).fill_null(strategy="forward").alias("cummulative_return_bmk"),
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

    min_date = stk['date'].min()
    max_date = stk['date'].max()

    result = {
        "start": min_date,
        "end": max_date,
        "records": records,
    }

    return result
