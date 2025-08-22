import polars as pl
from app.db import engine
from app.models.all_portfolios import AllPortfoliosRequest
from rich import print


def get_all_portfolios_summary(request: AllPortfoliosRequest) -> dict[str, any]:
    account_map = {
        "U4297056": "undergrad",
        "U12702120": "quant",
        "U10797691": "brigham_capital",
        "U12702064": "grad",
    }

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
        .sort("date")
        .with_columns(
            pl.col("return")
            .add(1)
            .cum_prod()
            .sub(1)
            .over("client_account_id")
            .alias("cummulative_return"),
            pl.col("client_account_id").replace(account_map).alias("portfolio"),
        )
        .select(
            "date", "portfolio", "value", "return", "cummulative_return", "dividends"
        )
    )

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

    total_return_rf = rf['cummulative_return'].tail(1).item() * 100

    portfolios = (
        stk.sort("date")
        .group_by("portfolio")
        .agg(
            pl.col("value").last(),
            pl.col("cummulative_return").last().alias("total_return"),
            pl.col("return").std().mul(pl.lit(252).sqrt()).alias("volatility"),
            pl.col("dividends").sum(),
        )
        .with_columns(
            pl.col("total_return").sub(total_return_rf).truediv("volatility").alias("sharpe_ratio"),
            pl.col("dividends").truediv("value").alias("dividend_yield"),
        )
        .with_columns(pl.col("total_return", "volatility", "dividend_yield").mul(100))
        .sort("portfolio")
        .to_dicts()
    )

    result = {"start": request.start, "end": request.end, "portfolios": portfolios}

    return result
