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
    tickers = sorted(tickers)
    tickers_list = TickersList(tickers=tickers)
    cov_df = get_covariance_matrix(tickers_list)

    # Align covariance matrix rows/cols to portfolio tickers (exclude IWV from matrix)
    cov_matrix = (
        cov_df.filter(pl.col("ticker").is_in(tickers))
        .sort("ticker")
        .select(tickers)
        .to_numpy()
    )

    # Portfolio variance and volatility
    variance = float(weights @ cov_matrix @ weights.T)
    volatility = float(np.sqrt(variance))

    # Asset-to-benchmark covariances (column IWV)
    asset_to_benchmark_cov = (
        cov_df.filter(pl.col("ticker").is_in(tickers))
        .sort("ticker")
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

    # IWV benchmark weights
    iwv_weights = (
        cov_df.filter(pl.col("ticker").is_in(tickers))
        .sort("ticker")
        .select("IWV")
        .to_numpy()
        .flatten()
    )

    active_weights = weights - iwv_weights
    tracking_error_variance = float(active_weights @ cov_matrix @ active_weights.T)
    tracking_error = float(np.sqrt(max(tracking_error_variance, 0)))

    return {
        "tickers": tickers,
        "weights": weights.tolist(),
        "volatility": volatility,
        "beta": beta,
        "tracking_error": tracking_error,
    }


def all_funds_risk_forecast() -> dict:
    weights_df = _all_fund_holding_weights()
    tickers = weights_df["ticker"].to_list()
    weights = np.array(weights_df["weight"], dtype=float)
    return _compute_portfolio_risk(tickers, weights)


def fund_risk_forecast(fund: str) -> dict:
    client_account_id = get_account_id_from_name(fund)
    weights_df = _fund_holding_weights(client_account_id)
    print(weights_df)
    tickers = weights_df["ticker"].to_list()
    weights = np.array(weights_df["weight"], dtype=float)
    return _compute_portfolio_risk(tickers, weights)


def fund_holding_risk_forecast(fund: str) -> dict:
    client_account_id = get_account_id_from_name(fund)
    weights_df = _fund_holding_weights(client_account_id)
    tickers = weights_df["ticker"].to_list()
    weights = np.array(weights_df["weight"], dtype=float)
    fund_risk = _compute_portfolio_risk(tickers, weights)
    sorted_tickers = sorted(tickers)
    tickers_list = TickersList(tickers=sorted_tickers)
    cov_df = get_covariance_matrix(tickers_list)

    cov_matrix = (
        cov_df.filter(pl.col("ticker").is_in(sorted_tickers))
        .sort("ticker")
        .select(sorted_tickers)
        .to_numpy()
    )

    # Covariance of each asset with the benchmark (IWV column)
    asset_to_benchmark_cov = (
        cov_df.filter(pl.col("ticker").is_in(sorted_tickers))
        .sort("ticker")
        .select("IWV")
        .to_numpy()
        .flatten()
    )

    # Benchmark variance (IWV row/column)
    benchmark_variance = (
        cov_df.filter(pl.col("ticker") == "IWV").select("IWV").to_numpy()[0, 0]
    )

    benchmark_weights = asset_to_benchmark_cov

    index_by_ticker = {t: i for i, t in enumerate(sorted_tickers)}
    holdings: list[dict] = []

    for ticker, fund_weight in zip(tickers, weights):
        idx = index_by_ticker[ticker]

        holding_variance = float(cov_matrix[idx, idx])
        holding_volatility = float(np.sqrt(max(holding_variance, 0.0)))
        holding_benchmark_cov = float(asset_to_benchmark_cov[idx])
        holding_beta = holding_benchmark_cov / benchmark_variance

        # Portfolio that is 100% in this holding
        single_name_portfolio_weights = np.zeros_like(benchmark_weights, dtype=float)
        single_name_portfolio_weights[idx] = 1.0

        # Active weights vs benchmark
        active_weights_vs_benchmark = single_name_portfolio_weights - benchmark_weights

        # Tracking error for this holding vs benchmark
        holding_te_variance = float(
            active_weights_vs_benchmark @ cov_matrix @ active_weights_vs_benchmark.T
        )
        holding_tracking_error = float(np.sqrt(max(holding_te_variance, 0.0)))

        holdings.append(
            {
                "ticker": ticker,
                "fund_weight": float(fund_weight),
                "volatility": holding_volatility,
                "beta": holding_beta,
                "tracking_error": holding_tracking_error,
            }
        )

    return {
        "fund": fund,
        "fund_level": fund_risk,
        "holdings": holdings,
    }
