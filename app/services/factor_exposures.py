import polars as pl

from app import s3
from app.db import engine
from app.utils import get_account_id_from_name


def get_factor_exposures() -> pl.DataFrame:
    return (
        s3.scan_parquet(
            bucket_name="barra-factor-exposures",
            file_key="latest_exposures.parquet",
        )
        .with_columns(
            # replace "." with " " in ticker column. need to use literal=True becuase . is a special character in regex
            pl.col("ticker").str.replace_all(".", " ", literal=True)
        )
        .collect()
    )


# you need to convert fund to client account id
#  holding returns already has weights calculated
def fund_holding_weights(client_account_id: str) -> pl.DataFrame:
    weights = pl.read_database(
        query=f"""
            SELECT
                client_account_id,
                ticker,
                weight
            FROM holding_returns
            WHERE date = (select max(date) from holding_returns)
                AND client_account_id = '{client_account_id}'
            """,
        connection=engine,
    )
    return pl.DataFrame(weights)


def all_fund_holding_weights() -> pl.DataFrame:
    quant_paper_id = get_account_id_from_name("quant_paper")
    weights = pl.read_database(
        query=f"""
            SELECT 
                ticker,
                SUM(value) / SUM(SUM(value)) OVER () AS weight
            FROM holding_returns
            WHERE date = (SELECT MAX(date) FROM holding_returns)
                AND client_account_id != '{quant_paper_id}'
            GROUP BY ticker;
            """,
        connection=engine,
    )
    return pl.DataFrame(weights)


def compute_exposure_weights(
    exposures: pl.DataFrame, weights: pl.DataFrame
) -> pl.DataFrame:
    positions_not_in_exposures = (
        weights.select("ticker")
        .join(exposures.select("ticker"), on="ticker", how="anti")
        .to_series()
        .to_list()
    )
    combo = exposures.join(weights, on="ticker", how="inner").drop(
        [
            col
            for col in ["client_account_id", "date", "ticker"]
            if col in exposures.columns
        ]
    )
    portfolio_exposure = combo.fill_null(0).select(
        (pl.col("^USSLOWL_.*$") * pl.col("weight")).sum()
    )
    return portfolio_exposure.to_dicts()[0], positions_not_in_exposures


def fund_weighted_exposures(fund: str):
    client_account_id = get_account_id_from_name(fund)
    return compute_exposure_weights(
        get_factor_exposures(), fund_holding_weights(client_account_id)
    )


def all_fund_weighted_exposures():
    return compute_exposure_weights(get_factor_exposures(), all_fund_holding_weights())
