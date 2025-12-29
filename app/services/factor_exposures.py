import polars as pl
from fastapi import HTTPException

from app import s3
from app.db import engine
from app.utils import get_account_id_from_name


def get_factor_exposures(holding: str | None = None) -> pl.DataFrame:
    lf = s3.scan_parquet(
        bucket_name="barra-factor-exposures",
        file_key="latest_exposures.parquet",
    )

    lf = lf.with_columns(
        # replace "." with " " in ticker column. need to use literal=True becuase . is a special character in regex
        pl.col("ticker").str.replace_all(".", " ", literal=True)
    )

    if holding is not None:
        lf = lf.filter(pl.col("ticker") == holding).select(pl.col("^USSLOWL_.*$"))
    return lf.collect()


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


def get_factor_and_tickers(factor: str) -> pl.DataFrame:
    return (
        s3.scan_parquet(
            bucket_name="barra-factor-exposures",
            file_key="latest_exposures.parquet",
        )
        .select([pl.col("ticker"), pl.col(factor)])
        .drop_nulls()
        .collect()
    )


def compute_holding_weights(factor: str, weights: pl.DataFrame) -> pl.DataFrame:
    df = get_factor_and_tickers(factor=factor)
    combo = df.join(weights, on="ticker", how="inner")
    if combo.is_empty():
        raise HTTPException(
            status_code=404, detail=f"No holdings exposed to factor {factor}"
        )
    ticker_and_exposure_weight = (
        combo.with_columns(
            # 1. Calculate the absolute exposure contribution for each row
            (pl.col("weight") * pl.col(factor)).alias("weighted_exposure")
        )
        .with_columns(
            # 2. Divide by the sum of all weighted exposures to get the percentage each holding contributes to total exposure
            (pl.col("weighted_exposure") / pl.col("weighted_exposure").sum()).alias(
                "exposure_contribution"
            )
        )
        .select(pl.col("ticker"), pl.col("exposure_contribution"))
    )
    return ticker_and_exposure_weight


def fund_weighted_exposures(fund: str):
    client_account_id = get_account_id_from_name(fund)
    return compute_exposure_weights(
        get_factor_exposures(), fund_holding_weights(client_account_id)
    )


def all_fund_weighted_exposures():
    return compute_exposure_weights(get_factor_exposures(), all_fund_holding_weights())


def factor_breakdown(fund: str, factor: str) -> dict:
    if fund == "all_funds":
        weights = all_fund_holding_weights()
    else:
        weights = fund_holding_weights(get_account_id_from_name(fund))
    df = compute_holding_weights(factor, weights)
    return dict(zip(df["ticker"], df["exposure_contribution"]))


def holding_exposures(holding: str) -> dict:
    df = get_factor_exposures(holding=holding)
    if df.is_empty():
        raise HTTPException(
            status_code=404, detail=f"Holding '{holding}' not found in exposure data."
        )
    exposures = {k: v for k, v in df.row(0, named=True).items() if v is not None}
    return exposures
