"""Opt-in PostgreSQL SELECT-only verification. No DDL, DML or embedding calls."""

import os

import pytest
from sqlalchemy import text

from app.db import engine
from app.services.chatbot import FUND_FILTER_SQL
from app.funds import FUND_ALIASES

pytestmark = pytest.mark.skipif(
    os.getenv("FUND_FILTER_READ_ONLY_DB_TEST") != "1",
    reason="requires read-only database connectivity",
)


@pytest.mark.parametrize(
    "fund,expected",
    [
        (
            None,
            {
                "quant",
                "alias",
                "grad",
                "shared",
                "blank",
                "unknown",
                "memo",
                "unknown_shared",
                "legacy",
            },
        ),
        ("quant", {"quant", "alias", "shared"}),
        ("grad", {"grad", "shared"}),
        ("undergrad", {"shared"}),
    ],
)
def test_fund_filter_with_real_postgres(fund, expected):
    query = (
        """
    WITH chunks(id, fund, document_scope) AS (VALUES
      ('quant', 'quant', 'fund'), ('alias','Quant Fund','fund'),
      ('grad', 'grad','fund'), ('shared',NULL,'shared'),
      ('blank','','unassigned'), ('unknown','bogus','fund'),
      ('memo',NULL,'unassigned'), ('unknown_shared','bogus','shared'),
      ('legacy','quant',NULL)
    )
    SELECT id FROM chunks WHERE TRUE
    """
        + FUND_FILTER_SQL
    )
    with engine.connect() as connection:
        connection.execute(text("SET TRANSACTION READ ONLY"))
        result = connection.execute(
            text(query),
            {"fund": fund, "fund_aliases": list(FUND_ALIASES.get(fund, ()))},
        )
        assert set(result.scalars()) == expected


def test_old_schema_is_unassigned_in_scoped_search():
    query = (
        "WITH chunks(id) AS (VALUES ('legacy')) SELECT id FROM chunks WHERE TRUE "
        + FUND_FILTER_SQL
    )
    with engine.connect() as connection:
        connection.execute(text("SET TRANSACTION READ ONLY"))
        assert (
            connection.execute(
                text(query), {"fund": "quant", "fund_aliases": ["quant"]}
            ).all()
            == []
        )
