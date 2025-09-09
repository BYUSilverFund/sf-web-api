import polars as pl
from app.db import engine
from app.models.all_holdings import AllHoldingsRequest
import polars_ols as pls  # noqa: F401


def get_all_holdings_summary(request: AllHoldingsRequest) -> dict[str, any]:
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
                    AND date BETWEEN '{request.start}' AND '{request.end}'
                ORDER BY date
                ;
            """,
            connection=engine,
        )
        .with_columns(
            pl.col("return", "dividends_per_share", "value", "price", "shares").cast(pl.Float64),
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
            "value",
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

    max_date = pl.read_database(
        query=f"""
                SELECT MAX(date)
                FROM holding_returns
                WHERE date BETWEEN '{request.start}' AND '{request.end}';
            """,
        connection=engine,
    )["max"].item()

    holdings = (
        stk.join(rf, on="date", how="left", suffix="_rf")
        .join(bmk, on="date", how="left", suffix="_bmk")
        .with_columns(
            pl.col("return_rf").fill_null(strategy="forward")  # Fill last value
        )
        .with_columns(
            pl.col("return").sub("return_rf").alias("xs_return"),
            pl.col("return_bmk").sub("return_rf").alias("xs_return_bmk"),
        )
        .sort("ticker", "date")
        .with_columns(
            pl.col("return_rf")
            .add(1)
            .cum_prod()
            .sub(1)
            .over("ticker")
            .alias("cummulative_return_rf"),
            pl.col("return_bmk")
            .add(1)
            .cum_prod()
            .sub(1)
            .over("ticker")
            .alias("cummulative_return_bmk"),
        )
        .group_by("ticker")
        .agg(
            pl.col("date").max(),
            pl.col("date").n_unique().alias("n_days"),
            pl.col("shares").last(),
            pl.col("price").last(),
            pl.col("value").last(),
            pl.col("cummulative_return").last().alias("total_return"),
            pl.col("cummulative_return_rf").last().alias("total_return_rf"),
            pl.col("cummulative_return_bmk").last().alias("total_return_bmk"),
            pl.col("return").std().alias("volatility"),
            pl.col("dividends_per_share").mul("shares").sum().alias("dividends"),
            pl.col("dividends_per_share").sum(),
            pl.col("xs_return").least_squares.ols(
                pl.col("xs_return_bmk"), mode="coefficients", add_intercept=True
            ),
        )
        .unnest("coefficients")
        .rename({"xs_return_bmk": "beta", "const": "alpha"})
        .with_columns(
            (
                pl.col("total_return")
                - pl.col("total_return_rf")
                - pl.col("beta")
                * (pl.col("total_return_bmk") - pl.col("total_return_rf"))
            ).alias("alpha")
        )
        .with_columns(pl.col("dividends").truediv("value").alias("dividend_yield"))
        .with_columns(
            pl.col("volatility").fill_null(0),  # TODO: This was a quick fix -- Andrew
            pl.col("date").eq(max_date).alias("active"),
        )
        .with_columns(pl.col("volatility").mul(pl.col("n_days").sqrt()))
        .with_columns(
            pl.col("total_return", "volatility", "dividend_yield", "alpha").mul(100)
        )
        .select(
            "ticker",
            "active",
            "shares",
            "price",
            "value",
            "total_return",
            "volatility",
            "dividends",
            "dividends_per_share",
            "dividend_yield",
            "alpha",
            "beta",
        )
        .sort("value", descending=True)
    )

    print(holdings.tail(10).glimpse())

    min_date = stk["date"].min()
    max_date = stk["date"].max()

    result = {
        "fund": request.fund,
        "start": min_date,
        "end": max_date,
        "holdings": holdings.to_dicts(),
    }

    return result
