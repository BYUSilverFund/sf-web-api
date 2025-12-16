import polars as pl

from app import s3


def get_factor_exposures() -> pl.DataFrame:
    return s3.scan_parquet(
        bucket_name="barra-factor-exposures",
        file_key="latest.parquet",
    ).collect()
