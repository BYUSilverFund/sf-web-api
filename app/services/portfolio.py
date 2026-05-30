import polars as pl
import statsmodels.formula.api as smf

from app.db import engine
from app.models.portfolio import PortfolioRequest
from app.utils import get_account_id_from_name


def _get_portfolio_frames(
    request: PortfolioRequest,
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    client_account_id = get_account_id_from_name(request.fund)

    stk = (
        pl.read_database(
            query=f"""
                SELECT *
                FROM fund_returns
                WHERE client_account_id = '{client_account_id}'
                    AND date BETWEEN '{request.start}' AND '{request.end}'
                ORDER BY date
                ;
            """,
            connection=engine,
        )
        .with_columns(pl.col("value", "return", "dividends").cast(pl.Float64))
        .with_columns(pl.col("return").replace({-1: 0}))
        .sort("date")
        .with_columns(
            pl.col("return").add(1).cum_prod().sub(1).alias("cummulative_return")
        )
        .select("date", "value", "return", "cummulative_return", "dividends")
    )

    bmk = pl.read_database(
        query=f"""
                SELECT
                    date,
                    return
                FROM benchmark
                WHERE date BETWEEN '{request.start}' AND '{request.end}'
                ORDER BY date;
            """,
        connection=engine,
    ).select("date", pl.col("return").cast(pl.Float64))

    rf = (
        pl.read_database(
            query=f"""
                SELECT *
                FROM risk_free_rate
                WHERE date BETWEEN '{request.start}' AND '{request.end}'
                ORDER BY date;
            """,
            connection=engine,
        )
        .with_columns(pl.col("return").cast(pl.Float64))
        .sort("date")
    )

    return stk, bmk, rf


def get_portfolio_summary(request: PortfolioRequest) -> dict[str, any]:
    stk, bmk, rf = _get_portfolio_frames(request)

    df_wide = (
        stk.join(bmk, on=["date"], suffix="_bmk", how="left")
        .join(rf, on=["date"], suffix="_rf", how="left")
        .select(
            "date",
            pl.col("return").alias("return_stk"),
            "return_bmk",
            pl.col("return_rf").fill_null(strategy="forward"),  # Fill last value
            pl.col("return").sub("return_bmk").alias("return_active"),
        )
        .sort("date")
        .with_columns(
            pl.col("return_rf").add(1).cum_prod().sub(1).alias("cummulative_return_rf"),
            pl.col("return_bmk")
            .add(1)
            .cum_prod()
            .sub(1)
            .alias("cummulative_return_bmk"),
        )
        .with_columns(pl.col("return_stk", "return_bmk").sub("return_rf"))
    )

    n_days = len(stk["date"].unique())

    total_return = stk["cummulative_return"].last() * 100

    avg_daily_return = stk["return"].mean()
    total_return_annualized = avg_daily_return * 252 * 100

    avg_daily_rf_return = df_wide["return_rf"].mean()
    total_return_rf_annualized = avg_daily_rf_return * 252 * 100

    model = smf.ols("return_stk ~ return_bmk", df_wide).fit()

    beta = model.params["return_bmk"].item()

    daily_alpha = model.params["Intercept"].item()
    alpha = daily_alpha * 252 * 100

    value = stk["value"].last()

    volatility = stk["return"].std() * (252**0.5) * 100

    dividends = stk["dividends"].sum()
    dividend_yield = dividends / value * 100

    sharpe_ratio = (total_return_annualized - total_return_rf_annualized) / volatility

    tracking_error = df_wide["return_active"].std() * (252**0.5) * 100

    annualized_active_return = df_wide["return_active"].mean() * 252 * 100

    information_ratio = (
        annualized_active_return / tracking_error if tracking_error != 0 else 0
    )

    min_date = stk["date"].min()
    max_date = stk["date"].max()

    result = {
        "fund": request.fund,
        "start": min_date,
        "end": max_date,
        "trading_days": n_days,
        "value": value,
        "total_return": total_return,
        "volatility": volatility,
        "sharpe_ratio": sharpe_ratio,
        "dividends": dividends,
        "dividend_yield": dividend_yield,
        "alpha": alpha,
        "beta": beta,
        "tracking_error": tracking_error,
        "information_ratio": information_ratio,
    }

    return result


def get_portfolio_active_summary(request: PortfolioRequest) -> dict[str, any]:
    stk, bmk, rf = _get_portfolio_frames(request)

    client_account_id = get_account_id_from_name(request.fund)
    end_date = value = stk["date"].last()

    # get the holding value for the benchmark on the end date
    bmk_holding_value = pl.read_database(
        query=f"""
            SELECT value
            FROM holding_returns
            WHERE client_account_id = '{client_account_id}'
                AND date = '{end_date}'
                AND ticker = 'IWV'
            LIMIT 1
        """,
        connection=engine,
    )

    # check to make sure it has a value (if not there is no holding value for the benchmark, so we will assume 0). convert df to float type
    if bmk_holding_value.is_empty():
        bmk_holding_value = 0
    else:
        bmk_holding_value = float(bmk_holding_value["value"].item())

    dividends = pl.read_database(
        query=f"""
            SELECT sum(net_amount) AS dividends  FROM dividends
            WHERE symbol != 'IWV'
                AND ex_date BETWEEN '{request.start}' AND '{request.end}'
            GROUP BY client_account_id
            HAVING client_account_id = '{client_account_id}'
        """,
        connection=engine,
    )

    if dividends.is_empty():
        dividends = 0
    else:
        dividends = float(dividends["dividends"].item())

    df_wide = (
        stk.join(bmk, on=["date"], suffix="_bmk", how="left")
        .join(rf, on=["date"], suffix="_rf", how="left")
        .select(
            "date",
            pl.col("return").alias("return_stk"),
            "return_bmk",
            pl.col("return_rf").fill_null(strategy="forward"),
        )
        .with_columns(
            pl.col("return_stk").sub("return_bmk").alias("return_active"),
            pl.col("return_stk", "return_bmk").sub("return_rf"),
        )
        .sort("date")
        .with_columns(
            pl.col("return_rf").add(1).cum_prod().sub(1).alias("cummulative_return_rf"),
            pl.col("return_bmk")
            .add(1)
            .cum_prod()
            .sub(1)
            .alias("cummulative_return_bmk"),
            pl.col("return_active")
            .add(1)
            .cum_prod()
            .sub(1)
            .alias("cummulative_return_active"),
        )
    )

    n_days = len(stk["date"].unique())
    total_return = df_wide["cummulative_return_active"].last() * 100
    avg_daily_active_return = df_wide["return_active"].mean()
    total_return_annualized = avg_daily_active_return * 252 * 100

    avg_daily_rf_return = df_wide["return_rf"].mean()
    total_return_rf_annualized = avg_daily_rf_return * 252 * 100

    model = smf.ols("return_stk ~ return_bmk", df_wide).fit()
    beta = model.params["return_bmk"].item()
    daily_alpha = model.params["Intercept"].item()
    alpha = daily_alpha * 252 * 100

    value = stk["value"].last() - bmk_holding_value
    active_return_std = df_wide["return_active"].std()
    volatility = active_return_std * (252**0.5) * 100
    dividend_yield = dividends / value * 100
    sharpe_ratio = (
        (total_return_annualized - total_return_rf_annualized) / volatility
        if volatility != 0
        else 0
    )
    tracking_error = active_return_std * (252**0.5) * 100
    information_ratio = (
        total_return_annualized / tracking_error if tracking_error != 0 else 0
    )

    max_date = stk["date"].max()
    min_date = stk["date"].min()

    result = {
        "fund": request.fund,
        "start": min_date,
        "end": max_date,
        "trading_days": n_days,
        "value": value,
        "total_return": total_return,
        "volatility": volatility,
        "sharpe_ratio": sharpe_ratio,
        "dividends": dividends,
        "dividend_yield": dividend_yield,
        "alpha": alpha,
        "beta": beta,
        "tracking_error": tracking_error,
        "information_ratio": information_ratio,
    }
    return result


def get_portfolio_time_series(request: PortfolioRequest) -> dict[str, any]:
    client_account_id = get_account_id_from_name(request.fund)

    stk = (
        pl.read_database(
            query=f"""
                SELECT * 
                FROM fund_returns 
                WHERE client_account_id = '{client_account_id}' 
                    AND date BETWEEN '{request.start}' AND '{request.end}'
                ORDER BY date
                ;
            """,
            connection=engine,
        )
        .with_columns(pl.col("value", "return", "dividends").cast(pl.Float64))
        .with_columns(pl.col("return").replace({-1: 0}))
        .sort("date")
        .with_columns(
            pl.col("return").add(1).cum_prod().sub(1).alias("cummulative_return")
        )
        .select("date", "value", "return", "cummulative_return", "dividends")
    )

    bmk = (
        pl.read_database(
            query=f"""
                SELECT 
                    date,
                    return
                FROM benchmark
                WHERE date BETWEEN '{request.start}' AND '{request.end}'
                ORDER BY date;
            """,
            connection=engine,
        )
        .with_columns(pl.col("return").cast(pl.Float64))
        .select(
            "date",
            "return",
        )
    )

    records = (
        stk.join(bmk, on=["date"], suffix="_bmk", how="left")
        .sort("date")
        .with_columns(
            pl.col("return_bmk")
            .add(1)
            .cum_prod()
            .sub(1)
            .fill_null(strategy="forward")
            .alias("cummulative_return_bmk"),
        )
        .rename(
            {
                "return": "return_",
                "return_bmk": "benchmark_return",
                "cummulative_return_bmk": "benchmark_cummulative_return",
            }
        )
        .with_columns(
            pl.col(
                "return_",
                "cummulative_return",
                "benchmark_return",
                "benchmark_cummulative_return",
            ).mul(100)
        )
        .to_dicts()
    )

    min_date = stk["date"].min()
    max_date = stk["date"].max()

    result = {
        "fund": request.fund,
        "start": min_date,
        "end": max_date,
        "records": records,
    }

    return result


def get_portfolio_time_series_csv(request: PortfolioRequest) -> bytes:
    portfolio_ts = get_portfolio_time_series(request)
    df = pl.DataFrame(portfolio_ts["records"]).sort("date", descending=False)

    rf = (
        pl.read_database(
            query=f"""
                SELECT
                    date,
                    return AS risk_free_return
                FROM risk_free_rate
                WHERE date BETWEEN '{request.start}' AND '{request.end}'
                ORDER BY date;
            """,
            connection=engine,
        )
        .with_columns(pl.col("risk_free_return").cast(pl.Float64))
        .sort("date")
    )

    df = df.join(rf, on="date", how="left").with_columns(
        pl.col("risk_free_return").fill_null(strategy="forward")
    )

    df = df.with_columns(pl.col("risk_free_return").mul(100))

    return df.write_csv().encode("utf-8")


def get_portfolio_trades(request: PortfolioRequest) -> dict[str, any]:
    client_account_id = get_account_id_from_name(request.fund)

    trades = pl.read_database(
        query=f"""
                SELECT * 
                FROM trades 
                WHERE client_account_id = '{client_account_id}' 
                    AND report_date BETWEEN '{request.start}' AND '{request.end}'
                ORDER BY report_date
                ;
            """,
        connection=engine,
    ).cast({"report_date": pl.String})

    records = trades.to_dicts()

    min_date = trades["report_date"].min()
    max_date = trades["report_date"].max()

    result = {
        "fund": request.fund,
        "start": min_date,
        "end": max_date,
        "records": records,
    }

    return result
