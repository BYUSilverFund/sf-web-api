import polars as pl
import psycopg2
from rich import print
import dotenv
import os
import seaborn as sns
import matplotlib.pyplot as plt
import datetime as dt
import polars_ols as pls
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

stk = (
    pl.read_database(
        query="SELECT * FROM returns;",
        connection=connection
    )
    .filter(
        pl.col('client_account_id').eq('U12702064'),
        pl.col('symbol').eq('AAPL'),
    )
    .with_columns(
        pl.col('return', 'dividends_per_share', 'close').cast(pl.Float64)
    )
    .sort('report_date', 'symbol')
    .with_columns(
        pl.col('return').add(1).cum_prod().sub(1).over('symbol').alias('cummulative_return')
    )
    .select(
        pl.col('report_date').alias('date'),
        pl.col('symbol').alias('ticker'),
        'close',
        'return',
        'cummulative_return',
        'dividends_per_share'
    )
)

# print(stk)

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
        'dividends_per_share'
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

df_long = pl.concat([stk, bmk]).sort('date', 'ticker')

# Chart
plt.figure(figsize=(8, 6))
sns.lineplot(df_long, x='date', y='cummulative_return', hue='ticker')
plt.xlabel(None)
plt.ylabel('Cummulative Return (decimal)')
plt.legend(title='Ticker')
plt.show()

# Summary
print(
    df_long
    .group_by('ticker')
    .agg(
        pl.col('close').last().alias('price'),
        pl.col('cummulative_return').last().alias('total_return'),
        pl.col('return').std().mul(pl.lit(252).sqrt()).alias('volatility'),
        pl.col('dividends_per_share').sum()
    )
    .with_columns(
        pl.col('dividends_per_share').truediv('price').mul(100).alias('dividend_yield')
    )
    .sort('ticker')
)


df_wide = (
    stk
    .join(bmk, on=['date'], suffix='_bmk', how='left')
    .join(rf, on=['date'], suffix='_rf', how='left')
    .select(
        'date',
        'ticker',
        pl.col('return').alias('return_stk'),
        'return_bmk',
        'return_rf'
    )
    .with_columns(
        pl.col('return_stk', 'return_bmk').sub('return_rf').fill_null(0)
    )
)

model = smf.ols("return_stk ~ return_bmk", df_wide).fit()

alpha = model.params['Intercept'] * 252
beta = model.params['return_bmk']

# Summary
print("alpha:", alpha)
print("beta:", beta)