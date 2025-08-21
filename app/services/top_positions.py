import polars as pl
from app.db import engine
from app.models.top_positions import TopPositionsRequest


def get_top_positions(request: TopPositionsRequest) -> dict[str, any]:
    account_map = {
        "undergrad": "U4297056",
        "quant": "U12702120",
        "brigham_capital": "U10797691",
        "grad": "U12702064",
    }

    client_account_id = account_map[request.fund]

    max_date = pl.read_database(
        query=f"""
                SELECT MAX(report_date) AS max_date
                FROM positions_new
                WHERE client_account_id = '{client_account_id}'
            """,
        connection=engine,
    )["max_date"].last()

    records = (
        pl.read_database(
            query=f"""
            SELECT
                symbol AS ticker,
                quantity * mark_price AS value
            FROM positions_new
            WHERE client_account_id = '{client_account_id}'
                AND report_date = '{max_date}'
            ORDER BY value DESC
            LIMIT 10
            ;
            """,
            connection=engine,
        )
        .with_columns(pl.col("value").cast(pl.Float64))
        .to_dicts()
    )

    results = {"date": max_date, "fund": request.fund, "records": records}

    return results
