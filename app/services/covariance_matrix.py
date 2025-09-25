import polars as pl
from app import s3
from app.models.covariance_matrix import TickersList, Fund
from app.db import engine


def get_covariance_matrix(tickers: TickersList) -> pl.DataFrame:
    return (
        s3.get_parquet(
            bucket_name="barra-covariance-matrices",
            file_key="latest.parquet",
        )
        .filter(pl.col("ticker").is_in(tickers.tickers))
        .sort("ticker")
        .select("date", "ticker", *sorted(tickers.tickers))
    )


def get_tickers() -> list[str]:
    return (
        s3.get_parquet(
            bucket_name="barra-covariance-matrices",
            file_key="latest.parquet",
        )["ticker"]
        .unique()
        .sort()
        .to_list()
    )


def get_fund_tickers(request: Fund) -> list[str]:
    account_map = {
        "undergrad": "U4297056",
        "quant": "U12702120",
        "brigham_capital": "U10797691",
        "grad": "U12702064",
    }

    client_account_id = account_map[request.fund]

    return (
        pl.read_database(
            query=f"""
                SELECT DISTINCT ticker
                FROM holding_returns
                WHERE client_account_id = '{client_account_id}'
                AND date = (SELECT MAX(date) FROM holding_returns WHERE client_account_id = '{client_account_id}');
            """,
            connection=engine,
        )["ticker"]
        .unique()
        .sort()
        .to_list()
    )
