import polars as pl
import psycopg2
from rich import print
import dotenv
import os
import seaborn as sns
import matplotlib.pyplot as plt
import statsmodels.formula.api as smf

dotenv.load_dotenv(override=True)

account_map = {
    'U4297056': 'undergrad',
    'U12702120': 'quant',
    'U10797691': 'brigham_capital',
    'U12702064': 'grad'
}

connection = psycopg2.connect(
    host=os.getenv("DB_ENDPOINT"),
    database=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    port=os.getenv("DB_PORT")
)

fund = (
    pl.read_database(
        query="SELECT * FROM all_fund_returns;",
        connection=connection
    )
    .with_columns(
        pl.col('ending_value', 'return', 'dividends').cast(pl.Float64)
    )
    .sort('date')
    .with_columns(
        pl.col('return').add(1).cum_prod().sub(1).alias('cummulative_return')
    )
    .select(
        'date',
        pl.lit('Silver Fund').alias('ticker'),
        pl.col('ending_value').alias('close'),
        'return',
        'cummulative_return',
        'dividends'
    )
)

bmk = (
    pl.read_database(
        query="SELECT * FROM benchmark_new;",
        connection=connection
    )
    .with_columns(
        pl.col('adjusted_close', 'return', 'dividends_per_share').cast(pl.Float64)
    )
    .sort('date')
    .with_columns(
        pl.col('return').add(1).cum_prod().sub(1).alias('cummulative_return')
    )
    .select(
        'date',
        'ticker',
        pl.col('adjusted_close').alias('close'),
        'return',
        'cummulative_return',
        pl.col('dividends_per_share').alias('dividends')
    )
)

rf = (
    pl.read_database(
        query="SELECT * FROM risk_free_rate_new;",
        connection=connection
    )
    .with_columns(
        pl.col('return').cast(pl.Float64)
    )
)

df_long = pl.concat([fund, bmk])

# # Chart
# plt.figure(figsize=(8, 6))
# sns.lineplot(df_long, x='date', y='cummulative_return', hue='ticker')
# plt.xlabel(None)
# plt.ylabel('Cummulative Return (decimal)')
# plt.legend(title='Ticker')
# plt.show()

# Summary
print(
    df_long
    .sort('date')
    .select(
        pl.col('close').last().alias('value'),
        pl.col('cummulative_return').last().alias('total_return'),
        pl.col('return').mean().mul(pl.lit(252)).alias('expected_return'),
        pl.col('return').std().mul(pl.lit(252).sqrt()).alias('volatility'),
        pl.col('dividends').sum()
    )
    .with_columns(
        pl.col('expected_return').truediv('volatility').alias('sharpe'),
        pl.col('dividends').truediv('value').mul(100).alias('dividend_yield')
    )
)

df_wide = (
    fund
    .join(bmk, on='date', how='left', suffix='_bmk')
    .join(rf, on='date', how='left', suffix='_rf')
    .select(
        'date',
        'ticker',
        pl.col('return').alias('return_fund'),
        'return_bmk',
        'return_rf'
    )
    .with_columns(
        pl.col('return_fund').sub('return_rf').alias('xs_return_fund'),
        pl.col('return_bmk').sub('return_rf').alias('xs_return_bmk'),
    )
    .with_columns(
        pl.col('return_fund').sub('return_bmk').alias('return_active')
    )
    .sort('date')
)

model = smf.ols("xs_return_fund ~ xs_return_bmk", df_wide).fit()

alpha = model.params['Intercept'] * 252
beta = model.params['xs_return_bmk']

# Summary
print("alpha:", alpha)
print("beta:", beta)

# Summary
print(
    df_wide
    .group_by('ticker')
    .agg(
        pl.col('return_active').mean().mul(pl.lit(252)).alias('active_return'),
        pl.col('return_active').std().mul(pl.lit(252).sqrt()).alias('tracking_error')
    )
    .with_columns(
        pl.col('active_return').truediv('tracking_error').alias('information_ratio')
    )
)