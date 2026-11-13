from unittest.mock import Mock

import pytest

from app.telemetry_costs import record_usage_cost


def attributes(model, usage, region="us-west-2"):
    span = Mock()
    record_usage_cost(span, model, region, usage)
    return {call.args[0]: call.args[1] for call in span.set_attribute.call_args_list}


def test_verified_nova_price_calculation():
    result = attributes(
        "us.amazon.nova-2-lite-v1:0",
        {"inputTokens": 1000, "outputTokens": 100, "totalTokens": 1100},
    )
    assert result["llm.cost.prompt"] == pytest.approx(0.00033)
    assert result["llm.cost.completion"] == pytest.approx(0.000275)
    assert result["llm.cost.total"] == pytest.approx(0.000605)
    assert result["silverfund.cost.status"] == "estimated"


def test_embedding_cost_uses_reported_tokens():
    result = attributes(
        "amazon.titan-embed-text-v2:0", {"inputTokens": 1000, "outputTokens": 0}
    )
    assert result["llm.cost.total"] == pytest.approx(0.00002)


@pytest.mark.parametrize(
    "model,region,usage,status",
    [
        (
            "unknown",
            "us-west-2",
            {"inputTokens": 3, "outputTokens": 4},
            "unknown_price",
        ),
        (
            "us.amazon.nova-2-lite-v1:0",
            "eu-west-1",
            {"inputTokens": 3, "outputTokens": 4},
            "unknown_price",
        ),
        (
            "us.amazon.nova-2-lite-v1:0",
            "us-west-2",
            {"inputTokens": 3, "outputTokens": 4, "cacheReadInputTokens": 20},
            "cache_pricing_unavailable",
        ),
    ],
)
def test_unknown_price_is_explicit_not_zero(model, region, usage, status):
    result = attributes(model, usage, region)
    assert result["silverfund.cost.status"] == status
    assert "llm.cost.total" not in result


def test_missing_usage_never_fabricates_cost():
    result = attributes("us.amazon.nova-2-lite-v1:0", {"inputTokens": 3})
    assert "llm.cost.total" not in result
