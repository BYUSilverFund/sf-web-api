import polars as pl
import polars_ols as pls  # noqa: F401
from app.db import engine
from app.models.all_portfolios import AllPortfoliosRequest

def get_all_portfolios_summary(request: AllPortfoliosRequest) -> dict[str, any]:
    account_map = {
        "U4297056": "undergrad",
        "U12702120": "quant",
        "U10797691": "brigham_capital",
        "U12702064": "grad",
    }

    stk = (
        pl.read_database(
            query=f"""
                SELECT * 
                FROM fund_returns 
                WHERE date BETWEEN '{request.start}' AND '{request.end}'
                ORDER BY date
                ;
            """,
            connection=engine,
        )
        .with_columns(pl.col("value", "return", "dividends").cast(pl.Float64))
        .with_columns(
            pl.col('return').replace({-1: 0}) # TODO: Fix so that the first day in the max history isn't -1 return.
        )
        .sort("date")
        .with_columns(
            pl.col("return")
            .add(1)
            .cum_prod()
            .sub(1)
            .over("client_account_id")
            .alias("cummulative_return"),
            pl.col("client_account_id").replace(account_map).alias("portfolio"),
        )
        .select(
            "date", "portfolio", "value", "return", "cummulative_return", "dividends"
        )
    )

    bmk = pl.read_database(
        query=f"""
                SELECT 
                    date,
                    return
                FROM benchmark_new
                WHERE date BETWEEN '{request.start}' AND '{request.end}'
                ORDER BY date;
            """,
        connection=engine,
    ).select("date", pl.col("return").cast(pl.Float64))

    rf = pl.read_database(
        query=f"""
                SELECT * 
                FROM risk_free_rate_new
                WHERE date BETWEEN '{request.start}' AND '{request.end}'
                ORDER BY date;
            """,
        connection=engine,
    ).with_columns(pl.col("return").cast(pl.Float64)).sort('date')

    portfolios = (
        stk
        .join(rf, on='date', how='left', suffix='_rf')
        .join(bmk, on='date', how='left', suffix='_bmk')
        .with_columns(
            pl.col("return_rf").fill_null(strategy="forward")  # Fill last value
        )
        .with_columns(
            pl.col('return_rf').add(1).cum_prod().sub(1).over('portfolio').alias('cummulative_return_rf')
        )
        .with_columns(
            pl.col('return').sub('return_rf').alias('xs_return'),
            pl.col('return_bmk').sub('return_rf').alias('xs_return_bmk'),
            pl.col('return').sub(pl.col('return_bmk')).alias('active_return')
        )
        .sort("date")
        .group_by("portfolio")
        .agg(
            pl.col('date').n_unique().alias('n_days'),
            pl.col("value").last(),
            pl.col("cummulative_return").last().alias("total_return"),
            pl.col("cummulative_return_rf").last().alias('total_return_rf'),
            pl.col("return").std().mul(pl.lit(252).sqrt()).alias("volatility"),
            pl.col("dividends").sum(),
            pl.col('active_return').std().mul(pl.lit(252).sqrt()).alias('tracking_error'),
            pl.col("xs_return").least_squares.ols(pl.col('xs_return_bmk'), mode='coefficients', add_intercept=True)
        )
        .unnest('coefficients')
        .rename({'xs_return_bmk': 'beta', 'const': 'alpha'})
        .with_columns(
            pl.col('alpha').mul(252),
            pl.col('total_return').mul(252).truediv('n_days').alias('total_return_annualized'),
            pl.col('total_return_rf').mul(252).truediv('n_days').alias('total_return_rf_annualized'),
        )
        .with_columns(
            pl.col("total_return_annualized").sub('total_return_rf_annualized').truediv("volatility").alias("sharpe_ratio"),
            pl.col("dividends").truediv("value").alias("dividend_yield"),
            pl.col('alpha').truediv('tracking_error').alias('information_ratio')
        )
        .with_columns(pl.col("total_return", "total_return_rf", "volatility", "tracking_error", "dividend_yield", "alpha").mul(100))
        .select(
            'portfolio',
            'value',
            'total_return',
            'total_return_rf',
            'volatility',
            'sharpe_ratio',
            'dividends',
            'dividend_yield',
            'alpha',
            'beta',
            'tracking_error',
            'information_ratio'
        )
        .sort("value", descending=True)
        .to_dicts()
    )

    min_date = stk['date'].min()
    max_date = stk['date'].max()

    result = {"start": min_date, "end": max_date, "portfolios": portfolios}

    return result
