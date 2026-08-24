import polars as pl

from app import s3
from app.db import engine
from app.models.covariance_matrix import Fund, TickersList
from app.utils import get_account_id_from_name


def get_covariance_matrix(tickers: TickersList) -> pl.DataFrame:
    # Sort tickers with IWV last
    sorted_tickers = sorted([t for t in tickers.tickers if t != "IWV"])
    sorted_tickers.append("IWV")  # Include IWV even if it wasn't requested.

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
    client_account_id = get_account_id_from_name(request.fund)

    return (
        pl.read_database(
            query="""
                SELECT DISTINCT ticker
                FROM holding_returns
                WHERE client_account_id = :account_id
                AND date = (SELECT MAX(date) FROM holding_returns WHERE client_account_id = :account_id);
            """,
            connection=engine,
            execute_options={"parameters": {"account_id": client_account_id}},
        )["ticker"]
        .unique()
        .sort()
        .to_list()
    )
