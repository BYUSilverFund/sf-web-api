import polars as pl
import statsmodels.formula.api as smf

from app.db import engine
from app.models.holding import HoldingRequest, TradeRecord
from app.models.portfolio import PortfolioRequest
from app.utils import get_account_id_from_name


def get_holding_summary(request: HoldingRequest) -> dict[str, any]:
    client_account_id = get_account_id_from_name(request.fund)

    stk = (
        pl.read_database(
            query=f"""
                SELECT * 
                FROM holding_returns 
                WHERE client_account_id = '{client_account_id}' 
                    AND ticker = '{request.ticker}'
                    AND date BETWEEN '{request.start}' AND '{request.end}'
                ORDER BY date
                ;
            """,
            connection=engine,
        )
        .with_columns(
            pl.col(
                "return", "dividends", "dividends_per_share", "price", "shares"
            ).cast(pl.Float64)
        )
        .sort("date", "ticker")
        .with_columns(
            pl.col("return")
            .add(1)
            .cum_prod()
            .sub(1)
            .over("ticker")
            .alias("cummulative_return")
        )
        .select(
            "date",
            "ticker",
            "shares",
            "price",
            "return",
            "cummulative_return",
            "dividends",
            "dividends_per_share",
        )
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

    rf = pl.read_database(
        query=f"""
                SELECT * 
                FROM risk_free_rate
                WHERE date BETWEEN '{request.start}' AND '{request.end}'
                ORDER BY date;
            """,
        connection=engine,
    ).with_columns(pl.col("return").cast(pl.Float64))

    df_wide = (
        stk.join(bmk, on=["date"], suffix="_bmk", how="left")
        .join(rf, on=["date"], suffix="_rf", how="left")
        .select(
            "date",
            "ticker",
            pl.col("return").alias("return_stk"),
            "return_bmk",
            pl.col("return_rf").fill_null(strategy="forward"),  # Fill last value
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

    max_date = pl.read_database(
        query=f"""
                SELECT MAX(date)
                FROM holding_returns
                WHERE date BETWEEN '{request.start}' AND '{request.end}';
            """,
        connection=engine,
    )["max"].item()

    side = stk["shares"].sign().last()

    n_days = len(df_wide["date"].unique())

    total_return = side * (stk["cummulative_return"].last() * 100)

    model = smf.ols("return_stk ~ return_bmk", df_wide).fit()
    beta = model.params["return_bmk"].item()
    daily_alpha = model.params["Intercept"].item()
    alpha = daily_alpha * 252 * 100

    active = stk["date"].last() == max_date
    shares = stk["shares"].last()
    price = stk["price"].last()
    value = shares * price
    volatility = stk["return"].std() * (252**0.5) * 100
    dividends = side * (stk["dividends"].sum())
    dividends_per_share = side * (stk["dividends_per_share"].sum())
    dividend_yield = dividends / value * 100

    min_date = stk["date"].min()
    max_date = stk["date"].max()

    result = {
        "fund": request.fund,
        "ticker": request.ticker,
        "start": min_date,
        "end": max_date,
        "trading_days": n_days,
        "active": active,
        "shares": shares,
        "price": price,
        "value": value,
        "total_return": total_return,
        "volatility": volatility,
        "dividends": dividends,
        "dividends_per_share": dividends_per_share,
        "dividend_yield": dividend_yield,
        "alpha": alpha,
        "beta": beta,
    }

    return result


def get_holding_time_series(request: HoldingRequest) -> dict[str, any]:
    client_account_id = get_account_id_from_name(request.fund)

    stk = (
        pl.read_database(
            query=f"""
                SELECT * 
                FROM holding_returns 
                WHERE client_account_id = '{client_account_id}' 
                    AND ticker = '{request.ticker}'
                    AND date BETWEEN '{request.start}' AND '{request.end}'
                ORDER BY date
                ;
            """,
            connection=engine,
        )
        .with_columns(
            pl.col(
                "weight",
                "price",
                "value",
                "return",
                "dividends",
                "dividends_per_share",
                "shares",
            ).cast(pl.Float64),
        )
        .sort("date", "ticker")
    )

    side = stk["shares"].sign().last()

    stk = stk.with_columns(
        pl.col("return").add(1).cum_prod().sub(1).mul(side).alias("cummulative_return")
    ).select(
        "date",
        "weight",
        "price",
        "shares",
        "value",
        "return",
        "cummulative_return",
        "dividends",
        "dividends_per_share",
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
        "ticker": request.ticker,
        "start": min_date,
        "end": max_date,
        "records": records,
    }

    return result


def get_dividends(request: HoldingRequest) -> dict[str, any]:
    client_account_id = get_account_id_from_name(request.fund)

    dividends = (
        pl.read_database(
            query=f"""
                SELECT * 
                FROM holding_returns 
                WHERE client_account_id = '{client_account_id}' 
                    AND ticker = '{request.ticker}'
                    AND date BETWEEN '{request.start}' AND '{request.end}'
                ORDER BY date
                ;
            """,
            connection=engine,
        )
        .with_columns(
            pl.col("shares", "dividends", "dividends_per_share").cast(pl.Float64)
        )
        .filter(pl.col("dividends").ne(0))
        .sort("date")
        .select("date", "shares", "dividends_per_share", "dividends")
        .to_dicts()
    )

    result = {
        "fund": request.fund,
        "ticker": request.ticker,
        "start": request.start,
        "end": request.end,
        "dividends": dividends,
    }

    return result


def get_trades(request: HoldingRequest | PortfolioRequest) -> dict[str, any]:
    client_account_id = get_account_id_from_name(request.fund)

    ticker = getattr(request, "ticker", None)
    ticker_filter = f"AND t.symbol = '{ticker}'" if ticker else ""

    trades = (
        pl.read_database(
            query=f"""
                WITH latest_positions AS (
                    SELECT symbol, mark_price AS current_price
                    FROM positions
                    WHERE client_account_id = '{client_account_id}'
                        AND report_date = (
                            SELECT MAX(report_date) 
                            FROM positions 
                            WHERE client_account_id = '{client_account_id}'
                        )
                )
                SELECT 
                    t.report_date,
                    t.buy_sell,
                    t.quantity,
                    t.trade_price,
                    t.symbol,
                    p.current_price
                FROM trades t
                LEFT JOIN latest_positions p ON t.symbol = p.symbol
                WHERE t.client_account_id = '{client_account_id}' 
                    {ticker_filter}
                    AND t.report_date BETWEEN '{request.start}' AND '{request.end}'
                ORDER BY t.report_date
                ;
            """,
            connection=engine,
        )
        .with_columns(
            pl.col("quantity", "trade_price", "current_price").cast(pl.Float64)
        )
        .select(
            pl.col("report_date").alias("date"),
            pl.col("buy_sell").alias("type"),
            pl.col("quantity").alias("shares"),
            pl.col("trade_price").alias("price"),
            pl.col("symbol").alias("ticker"),
            pl.col("quantity").mul("trade_price").alias("value"),
            pl.col("current_price"),
        )
        .group_by(["date", "price", "type", "ticker", "current_price"])
        .agg(
            pl.col("shares").sum(),
            pl.col("value").sum(),
        )
        .sort("date", "value", descending=True)
    )

    trade_records = [TradeRecord(**t) for t in trades.to_dicts()]

    result = {
        "fund": request.fund,
        "start": request.start,
        "end": request.end,
        "trades": trade_records,
    }

    if ticker:
        result["ticker"] = ticker

    return result


def get_portfolio_time_series_csv(request: HoldingRequest) -> bytes:
    holding_ts = get_holding_time_series(request)
    df = pl.DataFrame(holding_ts["records"]).sort("date", descending=False)

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
