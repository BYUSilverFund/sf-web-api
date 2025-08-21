import polars as pl
from app.db import engine
import statsmodels.formula.api as smf
from app.models.holding import HoldingRequest


def get_holding_summary(request: HoldingRequest) -> dict[str, any]:
    account_map = {
        "undergrad": "U4297056",
        "quant": "U12702120",
        "brigham_capital": "U10797691",
        "grad": "U12702064",
    }

    client_account_id = account_map[request.fund]

    stk = (
        pl.read_database(
            query=f"""
                SELECT * 
                FROM returns 
                WHERE client_account_id = '{client_account_id}' 
                    AND symbol = '{request.ticker}'
                    AND report_date BETWEEN '{request.start}' AND '{request.end}'
                ORDER BY report_date
                ;
            """,
            connection=engine,
        )
        .with_columns(pl.col("return", "dividends_per_share", "close").cast(pl.Float64))
        .sort("report_date", "symbol")
        .with_columns(
            pl.col("return")
            .add(1)
            .cum_prod()
            .sub(1)
            .over("symbol")
            .alias("cummulative_return")
        )
        .select(
            pl.col("report_date").alias("date"),
            pl.col("symbol").alias("ticker"),
            "shares",
            "close",
            "return",
            "cummulative_return",
            "dividends_per_share",
        )
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
    ).with_columns(pl.col("return").cast(pl.Float64))

    df_wide = (
        stk.join(bmk, on=["date"], suffix="_bmk", how="left")
        .join(rf, on=["date"], suffix="_rf", how="left")
        .select(
            "date",
            "ticker",
            pl.col("return").alias("return_stk"),
            "return_bmk",
            pl.col("return_rf").fill_null(strategy="forward"),  # Fill last value
        )
        .sort("date")
        .with_columns(pl.col("return_stk", "return_bmk").sub("return_rf"))
    )

    model = smf.ols("return_stk ~ return_bmk", df_wide).fit()

    alpha = model.params["Intercept"].item() * 252
    beta = model.params["return_bmk"].item()

    shares = stk["shares"].last()
    price = stk["close"].last()
    value = shares * price
    total_return = stk["cummulative_return"].last() * 100
    volatility = stk["return"].std() * (252**0.5) * 100
    dividends_per_share = stk["dividends_per_share"].sum()
    dividend_yield = dividends_per_share / price * 100

    result = {
        "fund": request.fund,
        "ticker": request.ticker,
        "start": request.start,
        "end": request.end,
        "shares": shares,
        "price": price,
        "value": value,
        "total_return": total_return,
        "volatility": volatility,
        "dividends_per_share": dividends_per_share,
        "dividend_yield": dividend_yield,
        "alpha": alpha,
        "beta": beta,
    }

    return result


def get_holding_time_series(request: HoldingRequest) -> dict[str, any]:
    account_map = {
        "undergrad": "U4297056",
        "quant": "U12702120",
        "brigham_capital": "U10797691",
        "grad": "U12702064",
    }

    client_account_id = account_map[request.fund]

    stk = (
        pl.read_database(
            query=f"""
                SELECT * 
                FROM holding_returns 
                WHERE client_account_id = '{client_account_id}' 
                    AND ticker = '{request.ticker}'
                    AND date BETWEEN '{request.start}' AND '{request.end}'
                ORDER BY date
                ;
            """,
            connection=engine,
        )
        .with_columns(
            pl.col(
                "weight", "price", "value", "return", "dividends", "dividends_per_share"
            ).cast(pl.Float64),
            pl.col("shares").cast(pl.Int32),
        )
        .sort("date", "ticker")
        .with_columns(
            pl.col("return").add(1).cum_prod().sub(1).alias("cummulative_return")
        )
        .select(
            "date",
            "weight",
            "price",
            "shares",
            "value",
            "return",
            "cummulative_return",
            "dividends",
            "dividends_per_share",
        )
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
        "fund": request.fund,
        "ticker": request.ticker,
        "start": request.start,
        "end": request.end,
        "records": records,
    }

    return result
