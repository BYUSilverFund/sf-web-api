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
            pl.col("return", "dividends", "dividends_per_share", "price").cast(
                pl.Float64
            )
        )
        .sort("date", "ticker")
        .with_columns(
            pl.col("return")
            .add(1)
            .cum_prod()
            .sub(1)
            .over("ticker")
            .alias("cummulative_return")
        )
        .select(
            "date",
            "ticker",
            "shares",
            "price",
            "return",
            "cummulative_return",
            "dividends",
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
        .with_columns(
            pl.col("return_rf").add(1).cum_prod().sub(1).alias("cummulative_return_rf"),
            pl.col("return_bmk")
            .add(1)
            .cum_prod()
            .sub(1)
            .alias("cummulative_return_bmk"),
        )
        .with_columns(pl.col("return_stk", "return_bmk").sub("return_rf"))
    )

    max_date = pl.read_database(
        query=f"""
                SELECT MAX(date)
                FROM holding_returns
                WHERE date BETWEEN '{request.start}' AND '{request.end}';
            """,
        connection=engine,
    )["max"].item()

    n_days = len(df_wide["date"].unique())

    total_return = stk["cummulative_return"].last() * 100
    total_return_rf = df_wide["cummulative_return_rf"].last() * 100
    total_return_bmk = df_wide["cummulative_return_bmk"].last() * 100

    model = smf.ols("return_stk ~ return_bmk", df_wide).fit()
    beta = model.params["return_bmk"].item()
    alpha = (total_return - total_return_rf) - beta * (
        total_return_bmk - total_return_rf
    )

    active = stk["date"].last() == max_date
    shares = stk["shares"].last()
    price = stk["price"].last()
    value = shares * price
    volatility = stk["return"].std() * (n_days**0.5) * 100
    dividends = stk["dividends"].sum()
    dividends_per_share = stk["dividends_per_share"].sum()
    dividend_yield = dividends / value * 100

    min_date = stk["date"].min()
    max_date = stk["date"].max()

    result = {
        "fund": request.fund,
        "ticker": request.ticker,
        "start": min_date,
        "end": max_date,
        "active": active,
        "shares": shares,
        "price": price,
        "value": value,
        "total_return": total_return,
        "volatility": volatility,
        "dividends": dividends,
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
        "fund": request.fund,
        "ticker": request.ticker,
        "start": min_date,
        "end": max_date,
        "records": records,
    }

    return result


def get_dividends(request: HoldingRequest) -> dict[str, any]:
    account_map = {
        "undergrad": "U4297056",
        "quant": "U12702120",
        "brigham_capital": "U10797691",
        "grad": "U12702064",
    }

    client_account_id = account_map[request.fund]

    dividends = (
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
            pl.col("shares", "dividends", "dividends_per_share").cast(pl.Float64)
        )
        .filter(pl.col("dividends").ne(0))
        .sort("date")
        .select("date", "shares", "dividends_per_share", "dividends")
        .to_dicts()
    )

    result = {
        "fund": request.fund,
        "ticker": request.ticker,
        "start": request.start,
        "end": request.end,
        "dividends": dividends,
    }

    return result


def get_trades(request: HoldingRequest) -> dict[str, any]:
    account_map = {
        "undergrad": "U4297056",
        "quant": "U12702120",
        "brigham_capital": "U10797691",
        "grad": "U12702064",
    }

    client_account_id = account_map[request.fund]

    trades = (
        pl.read_database(
            query=f"""
                SELECT * 
                FROM trades_new 
                WHERE client_account_id = '{client_account_id}' 
                    AND symbol = '{request.ticker}'
                    AND report_date BETWEEN '{request.start}' AND '{request.end}'
                ORDER BY report_date
                ;
            """,
            connection=engine,
        )
        .with_columns(pl.col("quantity", "trade_price").cast(pl.Float64))
        .select(
            pl.col("report_date").alias("date"),
            pl.col("buy_sell").alias("type"),
            pl.col("quantity").alias("shares"),
            pl.col("trade_price").alias("price"),
            pl.col("quantity").mul("trade_price").alias("value"),
        )
        .sort("date", "value", descending=True)
        .to_dicts()
    )

    result = {
        "fund": request.fund,
        "ticker": request.ticker,
        "start": request.start,
        "end": request.end,
        "trades": trades,
    }

    return result
