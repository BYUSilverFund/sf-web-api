import polars as pl
from app import s3
from app.models.covariance_matrix import TickersList, Fund
from app.db import engine


def get_covariance_matrix(tickers: TickersList) -> pl.DataFrame:
    # Sort tickers with IWV last
    sorted_tickers = sorted([t for t in tickers.tickers if t != "IWV"])
    sorted_tickers.append("IWV") # Include IWV even if it wasn't requested.

    return (
        s3.scan_parquet(
            bucket_name="barra-covariance-matrices",
            file_key="latest.parquet",
        )
        .filter(pl.col("ticker").is_in(sorted_tickers))
        .select("date", "ticker", *sorted_tickers)
        .sort(by=pl.col("ticker").replace({"IWV": "zzzIWV"}))
        .collect()
    )


def get_tickers() -> list[str]:
    return (
        s3.scan_parquet(
            bucket_name="barra-covariance-matrices",
            file_key="latest.parquet",
        )
        .select("ticker")
        .collect()["ticker"]
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
