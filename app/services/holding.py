import polars as pl

from app.db import engine
from app.models.holding import HoldingRequest, TradeRecord
from app.models.portfolio import PortfolioRequest
from app.utils import (
    get_account_id_from_name,
    calculate_alpha_beta,
    get_benchmark_timeseries,
    get_risk_free_timeseries,
)


def get_holding_summary(request: HoldingRequest) -> dict[str, any]:
    client_account_id = get_account_id_from_name(request.fund)

    stk = (
        pl.read_database(
            query="""
                SELECT * 
                FROM holding_returns 
                WHERE client_account_id = :account_id 
                    AND ticker = :ticker
                    AND date BETWEEN :start AND :end
                ORDER BY date;
            """,
            connection=engine,
            execute_options={
                "parameters": {
                    "account_id": client_account_id,
                    "ticker": request.ticker,
                    "start": request.start,
                    "end": request.end,
                }
            },
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

    bmk = get_benchmark_timeseries(request.start, request.end)

    rf = get_risk_free_timeseries(request.start, request.end)

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

    max_date = (
        bmk["date"].max()
        if len(bmk) > 0
        else (stk["date"].max() if len(stk) > 0 else request.end)
    )

    side = stk["shares"].sign().last()

    n_days = len(df_wide["date"].unique())

    total_return = side * (stk["cummulative_return"].last() * 100)

    alpha, beta = calculate_alpha_beta(df_wide)

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
            query="""
                SELECT * 
                FROM holding_returns 
                WHERE client_account_id = :account_id 
                    AND ticker = :ticker
                    AND date BETWEEN :start AND :end
                ORDER BY date;
            """,
            connection=engine,
            execute_options={
                "parameters": {
                    "account_id": client_account_id,
                    "ticker": request.ticker,
                    "start": request.start,
                    "end": request.end,
                }
            },
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
            query="""
                SELECT 
                    date,
                    return
                FROM benchmark
                WHERE date BETWEEN :start AND :end
                ORDER BY date;
            """,
            connection=engine,
            execute_options={
                "parameters": {"start": request.start, "end": request.end}
            },
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
            query="""
                SELECT * 
                FROM holding_returns 
                WHERE client_account_id = :account_id 
                    AND ticker = :ticker
                    AND date BETWEEN :start AND :end
                ORDER BY date;
            """,
            connection=engine,
            execute_options={
                "parameters": {
                    "account_id": client_account_id,
                    "ticker": request.ticker,
                    "start": request.start,
                    "end": request.end,
                }
            },
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
    ticker_clause = "AND t.symbol = :ticker" if ticker else ""

    params = {
        "account_id": client_account_id,
        "start": request.start,
        "end": request.end,
    }
    if ticker:
        params["ticker"] = ticker

    trades = (
        pl.read_database(
            query=f"""
                WITH latest_prices AS (
                    SELECT DISTINCT ON (symbol) symbol, mark_price AS current_price
                    FROM historical_data
                    ORDER BY symbol, report_date DESC
                )
                SELECT 
                    t.report_date,
                    t.buy_sell,
                    t.quantity,
                    t.trade_price,
                    t.symbol,
                    h.current_price
                FROM trades t
                LEFT JOIN latest_prices h ON t.symbol = h.symbol
                WHERE t.client_account_id = :account_id 
                    {ticker_clause}
                    AND t.report_date BETWEEN :start AND :end
                ORDER BY t.report_date
                ;
            """,
            connection=engine,
            execute_options={"parameters": params},
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

    if trades.is_empty():
        trade_records = []
    else:
        min_date = trades["date"].min()
        max_date = request.end

        unique_tickers = trades["ticker"].unique().to_list()

        stk_all = pl.read_database(
            query="""
                    SELECT report_date as date, symbol as ticker, daily_return as return
                    FROM historical_data
                    WHERE symbol = ANY(:tickers)
                        AND report_date BETWEEN :min_date AND :max_date
                    ORDER BY date;
                """,
            connection=engine,
            execute_options={
                "parameters": {
                    "tickers": unique_tickers,
                    "min_date": min_date,
                    "max_date": max_date,
                }
            },
        ).with_columns(pl.col("return").cast(pl.Float64))

        bmk_all = get_benchmark_timeseries(min_date, max_date)
        rf_all = get_risk_free_timeseries(min_date, max_date)

        unique_combinations = trades.select("ticker", "date").unique().to_dicts()
        alpha_map = {}

        for combo in unique_combinations:
            t_symbol = combo["ticker"]
            t_date = combo["date"]

            stk_sub = stk_all.filter(
                (pl.col("ticker") == t_symbol) & (pl.col("date") >= t_date)
            )
            bmk_sub = bmk_all.filter(pl.col("date") >= t_date)
            rf_sub = rf_all.filter(pl.col("date") >= t_date)

            df_wide = (
                stk_sub.join(bmk_sub, on=["date"], suffix="_bmk", how="left")
                .join(rf_sub, on=["date"], suffix="_rf", how="left")
                .select(
                    "date",
                    "ticker",
                    pl.col("return").alias("return_stk"),
                    "return_bmk",
                    pl.col("return_rf").fill_null(
                        strategy="forward"
                    ),  # Fill last value
                )
                .sort("date")
                .with_columns(pl.col("return_stk", "return_bmk").sub("return_rf"))
            )

            alpha = None
            if len(df_wide) >= 2:
                try:
                    alpha, _ = calculate_alpha_beta(df_wide)
                except Exception as e:
                    print(e)
            else:
                print("not enough data to get alpha for", t_symbol, t_date)

            alpha_map[(t_symbol, t_date)] = alpha

        trade_dicts = trades.to_dicts()
        for t in trade_dicts:
            t["alpha"] = alpha_map.get((t["ticker"], t["date"]), None)

        trade_records = [TradeRecord(**t) for t in trade_dicts]

    result = {
        "fund": request.fund,
        "start": request.start,
        "end": request.end,
        "trades": trade_records,
    }

    if ticker:
        result["ticker"] = ticker

    return result


def get_recent_trades(request: HoldingRequest | PortfolioRequest) -> dict[str, any]:
    client_account_id = get_account_id_from_name(request.fund)

    ticker = getattr(request, "ticker", None)
    ticker_clause = "AND t.symbol = :ticker" if ticker else ""

    params = {
        "account_id": client_account_id,
        "start": request.start,
        "end": request.end,
    }
    if ticker:
        params["ticker"] = ticker

    trades = (
        pl.read_database(
            query=f"""
                SELECT 
                    t.report_date,
                    t.buy_sell,
                    t.quantity,
                    t.trade_price,
                    t.symbol
                FROM trades t
                WHERE t.client_account_id = :account_id 
                    {ticker_clause}
                    AND t.report_date BETWEEN :start AND :end
                ORDER BY t.report_date DESC
                ;
            """,
            connection=engine,
            execute_options={"parameters": params},
        )
        .with_columns(pl.col("quantity", "trade_price").cast(pl.Float64))
        .select(
            pl.col("report_date").alias("date"),
            pl.col("buy_sell").alias("type"),
            pl.col("quantity").alias("shares"),
            pl.col("trade_price").alias("price"),
            pl.col("symbol").alias("ticker"),
            pl.col("quantity").mul("trade_price").alias("value"),
        )
        .group_by(["date", "price", "type", "ticker"])
        .agg(
            pl.col("shares").sum(),
            pl.col("value").sum(),
        )
        .sort("date", descending=True)
        .head(5)
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
            query="""
                SELECT
                    date,
                    return AS risk_free_return
                FROM risk_free_rate
                WHERE date BETWEEN :start AND :end
                ORDER BY date;
            """,
            connection=engine,
            execute_options={
                "parameters": {"start": request.start, "end": request.end}
            },
        )
        .with_columns(pl.col("risk_free_return").cast(pl.Float64))
        .sort("date")
    )

    df = df.join(rf, on="date", how="left").with_columns(
        pl.col("risk_free_return").fill_null(strategy="forward")
    )

    df = df.with_columns(pl.col("risk_free_return").mul(100))

    return df.write_csv().encode("utf-8")
