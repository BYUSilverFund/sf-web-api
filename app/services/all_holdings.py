import polars as pl
from app.db import engine
from app.models.all_holdings import AllHoldingsRequest
from rich import print


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
            pl.col("return", "dividends_per_share", "value", "price").cast(pl.Float64)
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

    holdings = (
        stk.group_by("ticker")
        .agg(
            pl.col("date").max(),
            pl.col("value").last(),
            pl.col("cummulative_return").last().alias("total_return"),
            pl.col("return").std().mul(pl.lit(252).sqrt()).alias("volatility"),
            pl.col("dividends_per_share").mul("shares").sum().alias("dividends"),
        )
        .with_columns(
            pl.col("volatility").fill_null(0),  # TODO: This was a quick fix -- Andrew
            pl.col("date").eq(request.end).alias("active"),
        )
        .with_columns(
            pl.col('total_return', 'volatility').mul(100)
        )
        .select(
            'ticker',
            'active',
            'value',
            'total_return',
            'volatility',
            'dividends'
        )
        .sort("value", descending=True)
        .to_dicts()
    )

    result = {
        "fund": request.fund,
        "start": request.start,
        "end": request.end,
        "holdings": holdings,
    }

    return result
