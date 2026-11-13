"""Offline list-price estimates for the verified local Bedrock configuration.

Source: AWS public Oregon catalog, published 2026-11-11T01:30:37Z.
No network, billing queries or content capture occurs in request processing.
"""

from decimal import Decimal

from openinference.semconv.trace import SpanAttributes as A

PRICE_SOURCE = "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonBedrock/20261111013037/us-west-2/index.json"
# USD per million tokens: standard on-demand Oregon/US Nova, not global/flex.
PRICES = {
    ("us-west-2", "us.amazon.nova-2-lite-v1:0"): ("0.33", "2.75"),
    ("us-west-2", "amazon.titan-embed-text-v2:0"): ("0.02", "0"),
}


def initialize_cost(span, model_id, region):
    span.set_attribute(A.LLM_PROVIDER, "aws")
    span.set_attribute(A.LLM_SYSTEM, "amazon")
    span.set_attribute("cloud.region", region)
    span.set_attribute("silverfund.cost.status", "usage_unavailable")
    span.set_attribute("silverfund.cost.currency", "USD")


def record_usage_cost(span, model_id, region, usage):
    """Never turn missing usage/rates into an invented zero cost."""
    names = [
        ("inputTokens", A.LLM_TOKEN_COUNT_PROMPT),
        ("outputTokens", A.LLM_TOKEN_COUNT_COMPLETION),
        ("totalTokens", A.LLM_TOKEN_COUNT_TOTAL),
        ("cacheReadInputTokens", "llm.token_count.prompt_details.cache_read"),
        ("cacheWriteInputTokens", "llm.token_count.prompt_details.cache_write"),
    ]
    for key, attr in names:
        if type(usage.get(key)) is int and usage[key] >= 0:
            span.set_attribute(attr, usage[key])
    rates = PRICES.get((region, model_id))
    if rates is None:
        span.set_attribute("silverfund.cost.status", "unknown_price")
        return
    if any(
        type(usage.get(key)) is not int or usage[key] < 0
        for key in ("inputTokens", "outputTokens")
    ):
        return
    cache_read = usage.get("cacheReadInputTokens", 0)
    cache_write = usage.get("cacheWriteInputTokens", 0)
    if any(type(value) is not int or value < 0 for value in (cache_read, cache_write)):
        return
    if cache_read or cache_write:
        # Current requests do not enable prompt caching. Do not assume a cached
        # billing formula for a future model/configuration; expose unknown cost.
        span.set_attribute("silverfund.cost.status", "cache_pricing_unavailable")
        return
    prompt = Decimal(usage["inputTokens"]) * Decimal(rates[0]) / Decimal(1_000_000)
    completion = Decimal(usage["outputTokens"]) * Decimal(rates[1]) / Decimal(1_000_000)
    span.set_attribute(A.LLM_COST_PROMPT, float(prompt))
    span.set_attribute(A.LLM_COST_COMPLETION, float(completion))
    span.set_attribute(A.LLM_COST_TOTAL, float(prompt + completion))
    span.set_attribute("silverfund.cost.status", "estimated")
    span.set_attribute("silverfund.cost.source", PRICE_SOURCE)
