import polars as pl
from app import s3
from app.models.covariance_matrix import CovarianceMatrixRequest


def get_covariance_matrix(request: CovarianceMatrixRequest) -> pl.DataFrame:
    return (
        s3.get_parquet(
            bucket_name="barra-covariance-matrices",
            file_key="latest.parquet",
        )
        .filter(pl.col("ticker").is_in(request.tickers))
        .sort("ticker")
        .select("date", "ticker", *sorted(request.tickers))
    )
