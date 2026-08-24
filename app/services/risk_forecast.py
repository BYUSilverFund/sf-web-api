import numpy as np
import polars as pl

from app.db import engine
from app.models.covariance_matrix import TickersList
from app.services.covariance_matrix import get_covariance_matrix, get_tickers
from app.utils import get_account_id_from_name


def _fund_holding_weights(client_account_id: str) -> pl.DataFrame:
    return pl.read_database(
        query="""
            SELECT
                ticker,
                weight
            FROM holding_returns
            WHERE date = (SELECT MAX(date) FROM holding_returns)
              AND client_account_id = :account_id;
        """,
        connection=engine,
        execute_options={"parameters": {"account_id": client_account_id}},
    )


def _all_fund_holding_weights() -> pl.DataFrame:
    quant_paper_id = get_account_id_from_name("quant_paper")
    return pl.read_database(
        query="""
            SELECT
                ticker,
                SUM(value) / SUM(SUM(value)) OVER () AS weight
            FROM holding_returns
            WHERE date = (SELECT MAX(date) FROM holding_returns)
              AND client_account_id != :quant_paper_id
            GROUP BY ticker;
        """,
        connection=engine,
        execute_options={"parameters": {"quant_paper_id": quant_paper_id}},
    )


def _sort_tickers_and_weights(
    tickers: list[str], weights: np.ndarray
) -> tuple[list[str], np.ndarray]:
    sorted_tickers = sorted(t for t in tickers if t != "IWV")
    if "IWV" in tickers:
        sorted_tickers.append("IWV")
    idx = {t: i for i, t in enumerate(tickers)}
    order = [idx[t] for t in sorted_tickers]
    sorted_weights = weights[order]
    return sorted_tickers, sorted_weights


def _compute_portfolio_risk(
    tickers: list[str], weights: np.ndarray
) -> tuple[dict, list[str]]:
    tickers, weights = _sort_tickers_and_weights(tickers, weights)

    valid_cov_tickers = set(get_tickers())
    positions_not_in_data = [t for t in tickers if t not in valid_cov_tickers]
    filtered = [(t, w) for t, w in zip(tickers, weights) if t in valid_cov_tickers]
    tickers = [t for t, _ in filtered]
    weights = np.array([w for _, w in filtered], dtype=float)

    tickers_list = TickersList(tickers=tickers)
    cov_df = get_covariance_matrix(tickers_list)

    cov_matrix = (
        cov_df.filter(pl.col("ticker").is_in(tickers))
        .sort(by=pl.col("ticker").replace({"IWV": "zzzIWV"}))
        .select(tickers)
        .to_numpy()
    )

    variance = float(weights @ cov_matrix @ weights.T)
    volatility = float(np.sqrt(max(variance, 0.0)))

    # Asset-to-benchmark covariances (column IWV)
    asset_to_benchmark_cov = (
        cov_df.filter(pl.col("ticker").is_in(tickers))
        .sort(by=pl.col("ticker").replace({"IWV": "zzzIWV"}))
        .select("IWV")
        .to_numpy()
        .flatten()
    )

    # Benchmark variance (IWV row/column)
    benchmark_variance = (
        cov_df.filter(pl.col("ticker") == "IWV").select("IWV").to_numpy()[0, 0]
    )

    portfolio_to_benchmark_cov = float(weights @ asset_to_benchmark_cov)
    beta = (
        portfolio_to_benchmark_cov / benchmark_variance
        if benchmark_variance != 0
        else float("nan")
    )

    # IWV benchmark weights: 0 for all assets, 1 for IWV
    iwv_weights = np.zeros_like(weights, dtype=float)
    if "IWV" in tickers:
        iwv_idx = tickers.index("IWV")
        iwv_weights[iwv_idx] = 1.0

    active_weights = weights - iwv_weights
    tracking_error_variance = float(active_weights @ cov_matrix @ active_weights.T)
    tracking_error = float(np.sqrt(max(tracking_error_variance, 0.0)))

    return {
        "tickers": tickers,
        "weights": weights.tolist(),
        "volatility": volatility,
        "beta": beta,
        "tracking_error": tracking_error,
    }, positions_not_in_data


def all_funds_risk_forecast() -> tuple[dict, list[str]]:
    weights_df = _all_fund_holding_weights()
    tickers = weights_df["ticker"].to_list()
    weights = np.array(weights_df["weight"], dtype=float)
    return _compute_portfolio_risk(tickers, weights)


def fund_risk_forecast(fund: str) -> tuple[dict, list[str]]:
    client_account_id = get_account_id_from_name(fund)
    weights_df = _fund_holding_weights(client_account_id)
    tickers = weights_df["ticker"].to_list()
    weights = np.array(weights_df["weight"], dtype=float)
    portfolio_risk, positions_not_in_data = _compute_portfolio_risk(tickers, weights)
    portfolio_risk["fund"] = fund
    return portfolio_risk, positions_not_in_data


def fund_holding_risk_forecast(fund: str, ticker: str) -> tuple[dict, list[str]]:
    client_account_id = get_account_id_from_name(fund)
    weights_df = _fund_holding_weights(client_account_id)
    tickers = weights_df["ticker"].to_list()
    weights = np.array(weights_df["weight"], dtype=float)
    sorted_tickers, sorted_weights = _sort_tickers_and_weights(tickers, weights)

    # get the holding weight in fund portfolio
    holding_idx = sorted_tickers.index(ticker)
    fund_weight = float(sorted_weights[holding_idx])

    # Build a portfolio that is 100% in this holding for the rest of metrics
    single_holding_weights = np.zeros_like(sorted_weights, dtype=float)
    single_holding_weights[holding_idx] = 1.0
    single_name_risk, positions_not_in_data = _compute_portfolio_risk(
        sorted_tickers, single_holding_weights
    )

    single_name_risk.update(
        {
            "fund": fund,
            "ticker": ticker,
            "fund_weight": fund_weight,
        }
    )
    return single_name_risk, positions_not_in_data
