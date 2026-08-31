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
        stk["date"].max()
        if len(stk) > 0
        else (bmk["date"].max() if len(bmk) > 0 else request.end)
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
                    t.benchmark_price,
                    b.adjusted_close AS benchmark_close,
                    h.current_price
                FROM trades t
                LEFT JOIN latest_prices h ON t.symbol = h.symbol
                LEFT JOIN benchmark b ON t.report_date = b.date
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
            pl.col(
                "quantity",
                "trade_price",
                "current_price",
                "benchmark_price",
                "benchmark_close",
            ).cast(pl.Float64)
        )
        .select(
            pl.col("report_date").alias("date"),
            pl.col("buy_sell").alias("type"),
            pl.col("quantity").alias("shares"),
            pl.col("trade_price").alias("price"),
            pl.col("symbol").alias("ticker"),
            pl.col("quantity").mul("trade_price").alias("value"),
            pl.col("current_price"),
            pl.col("benchmark_price"),
            pl.col("benchmark_close"),
        )
        .group_by(
            [
                "date",
                "price",
                "type",
                "ticker",
                "current_price",
                "benchmark_price",
                "benchmark_close",
            ]
        )
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
                    SELECT report_date as date, symbol as ticker, mark_price, daily_return as return
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
        ).with_columns(pl.col("mark_price", "return").cast(pl.Float64))

        bmk_all = get_benchmark_timeseries(min_date, max_date)
        rf_all = get_risk_free_timeseries(min_date, max_date)

        unique_combinations = (
            trades.select(
                "ticker", "date", "price", "benchmark_price", "benchmark_close"
            )
            .unique()
            .to_dicts()
        )
        alpha_map = {}

        for combo in unique_combinations:
            t_symbol = combo["ticker"]
            t_date = combo["date"]
            t_price = combo["price"]
            t_bmk_price = combo["benchmark_price"]
            t_bmk_close = combo["benchmark_close"]

            stk_sub = stk_all.filter(
                (pl.col("ticker") == t_symbol) & (pl.col("date") >= t_date)
            )
            bmk_sub = bmk_all.filter(pl.col("date") >= t_date)
            rf_sub = rf_all.filter(pl.col("date") >= t_date)

            # Adjust Day 0 returns to reflect intraday trade and benchmark entry prices (skip for IWV benchmark ticker)
            if t_symbol != "IWV":
                day0_stk_row = stk_sub.filter(pl.col("date") == t_date)
                if (
                    t_price
                    and t_price > 0
                    and not day0_stk_row.is_empty()
                    and day0_stk_row["mark_price"][0] is not None
                ):
                    day0_stk = (day0_stk_row["mark_price"][0] - t_price) / t_price
                    stk_sub = stk_sub.with_columns(
                        pl.when(pl.col("date") == t_date)
                        .then(day0_stk)
                        .otherwise("return")
                        .alias("return")
                    )

                if t_bmk_price and t_bmk_close and t_bmk_price > 0 and len(bmk_sub) > 0:
                    day0_bmk = (t_bmk_close - t_bmk_price) / t_bmk_price
                    bmk_sub = bmk_sub.with_columns(
                        pl.when(pl.col("date") == t_date)
                        .then(day0_bmk)
                        .otherwise("return")
                        .alias("return")
                    )

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

            alpha_map[(t_symbol, t_date, t_price, t_bmk_price)] = alpha

        trade_dicts = trades.drop("benchmark_close").to_dicts()
        for t in trade_dicts:
            t["alpha"] = alpha_map.get(
                (t["ticker"], t["date"], t.get("price"), t.get("benchmark_price")), None
            )

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
