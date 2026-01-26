import numpy as np
import polars as pl

from app.db import engine
from app.models.covariance_matrix import TickersList
from app.services.covariance_matrix import get_covariance_matrix
from app.utils import get_account_id_from_name


def _fund_holding_weights(client_account_id: str) -> pl.DataFrame:
    return pl.read_database(
        query=f"""
            SELECT
                ticker,
                weight
            FROM holding_returns
            WHERE date = (SELECT MAX(date) FROM holding_returns)
              AND client_account_id = '{client_account_id}';
        """,
        connection=engine,
    )


def _all_fund_holding_weights() -> pl.DataFrame:
    quant_paper_id = get_account_id_from_name("quant_paper")
    return pl.read_database(
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


def _compute_portfolio_risk(tickers: list[str], weights: np.ndarray) -> dict:
    tickers_list = TickersList(tickers=tickers)
    cov_df = get_covariance_matrix(tickers_list)

    # Align covariance matrix rows/cols to portfolio tickers (exclude IWV from matrix)
    cov_tickers = tickers  # already sorted the same way we selected
    cov_matrix = (
        cov_df.filter(pl.col("ticker").is_in(cov_tickers))
        .select(cov_tickers)  # only portfolio tickers, no IWV
        .to_numpy()
    )

    # Portfolio variance and volatility
    variance = float(weights @ cov_matrix @ weights.T)
    volatility = float(np.sqrt(variance))

    # Asset-to-benchmark covariances (column IWV)
    asset_to_benchmark_cov = (
        cov_df.filter(pl.col("ticker").is_in(cov_tickers))
        .select("IWV")
        .to_numpy()
        .flatten()
    )

    # Benchmark variance (IWV row/column)
    benchmark_variance = (
        cov_df.filter(pl.col("ticker") == "IWV").select("IWV").to_numpy()[0, 0]
    )

    portfolio_to_benchmark_cov = float(weights @ asset_to_benchmark_cov)
    beta = portfolio_to_benchmark_cov / benchmark_variance

    return {
        "tickers": tickers,
        "weights": weights.tolist(),
        "variance": variance,
        "volatility": volatility,
        "beta": beta,
    }


def all_funds_risk_forecast() -> dict:
    weights_df = _all_fund_holding_weights()
    tickers = weights_df["ticker"].to_list()
    weights = np.array(weights_df["weight"], dtype=float)
    return _compute_portfolio_risk(tickers, weights)


def fund_risk_forecast(fund: str) -> dict:
    client_account_id = get_account_id_from_name(fund)
    weights_df = _fund_holding_weights(client_account_id)
    tickers = weights_df["ticker"].to_list()
    weights = np.array(weights_df["weight"], dtype=float)
    return _compute_portfolio_risk(tickers, weights)
