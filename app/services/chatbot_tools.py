"""Allowlisted, read-only database tools for Nova chatbot requests."""

import math
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.models.all_holdings import (
    AllHoldingsRequest,
    AllHoldingsSummaryResponse,
)
from app.models.holding import (
    DividendsResponse,
    HoldingRequest,
    HoldingSummaryResponse,
    TradesResponse,
)
from app.models.portfolio import PortfolioRequest, PortfolioSummaryResponse
from app.models.top_positions import TopPositionsRequest, TopPositionsResponse
from app.services.all_holdings import get_all_holdings_summary
from app.services.holding import get_dividends, get_holding_summary, get_trades
from app.services.portfolio import get_portfolio_summary
from app.services.top_positions import get_top_positions


SUPPORTED_FUNDS = (
    "undergrad",
    "quant",
    "brigham_capital",
    "grad",
    "quant_paper",
)
MAX_RETURNED_ROWS = 50


class _ToolArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _FundRangeArgs(_ToolArgs):
    fund: Literal["undergrad", "quant", "brigham_capital", "grad", "quant_paper"]
    start_date: date
    end_date: date

    @field_validator("end_date")
    @classmethod
    def end_must_not_precede_start(cls, value: date, info) -> date:
        start_date = info.data.get("start_date")
        if start_date and value < start_date:
            raise ValueError("end_date must be on or after start_date")
        return value


class _HoldingArgs(_FundRangeArgs):
    ticker: str = Field(min_length=1, max_length=32)

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise ValueError("ticker must not be blank")
        return value


class _TradesArgs(_FundRangeArgs):
    ticker: str | None = Field(default=None, min_length=1, max_length=32)

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().upper()
        if not value:
            raise ValueError("ticker must not be blank")
        return value


class _TopPositionsArgs(_ToolArgs):
    fund: Literal["undergrad", "quant", "brigham_capital", "grad", "quant_paper"]


_FUND_SCHEMA = {
    "type": "string",
    "enum": list(SUPPORTED_FUNDS),
    "description": "Fund name from the supported list.",
}
_DATE_SCHEMA = {"type": "string", "format": "date"}


def _range_properties(*, ticker: bool = False) -> dict:
    properties = {
        "fund": _FUND_SCHEMA,
        "start_date": {**_DATE_SCHEMA, "description": "Inclusive start date."},
        "end_date": {**_DATE_SCHEMA, "description": "Inclusive end date."},
    }
    if ticker:
        properties["ticker"] = {
            "type": "string",
            "description": "Stock ticker symbol.",
        }
    return properties


def _tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "toolSpec": {
            "name": name,
            "description": description,
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                }
            },
        }
    }


CHATBOT_TOOL_CONFIG = {
    "tools": [
        _tool(
            "get_portfolio_summary",
            "Get performance and risk metrics for one fund over a date range.",
            _range_properties(),
            ["fund", "start_date", "end_date"],
        ),
        _tool(
            "get_top_positions",
            "Get the latest 10 positions by value for one fund.",
            {"fund": _FUND_SCHEMA},
            ["fund"],
        ),
        _tool(
            "get_holdings_summary",
            "Get performance and risk metrics for all holdings in one fund over a date range.",
            _range_properties(),
            ["fund", "start_date", "end_date"],
        ),
        _tool(
            "get_holding_summary",
            "Get performance and risk metrics for one ticker in one fund over a date range.",
            _range_properties(ticker=True),
            ["fund", "ticker", "start_date", "end_date"],
        ),
        _tool(
            "get_trades",
            "Get trades for one fund, optionally filtered to a ticker, over a date range.",
            _range_properties(ticker=True),
            ["fund", "start_date", "end_date"],
        ),
        _tool(
            "get_dividends",
            "Get dividend history for one ticker in one fund over a date range.",
            _range_properties(ticker=True),
            ["fund", "ticker", "start_date", "end_date"],
        ),
    ],
    "toolChoice": {"auto": {}},
}


class InvalidToolRequest(ValueError):
    """Raised when Nova requests an unknown tool or invalid arguments."""


def _range_request(args: _FundRangeArgs) -> dict:
    return {
        "fund": args.fund,
        "start": args.start_date,
        "end": args.end_date,
    }


def _json_model(model: type[BaseModel], result: dict) -> dict:
    return _sanitize_non_finite(model.model_validate(result).model_dump(mode="json"))


def _sanitize_non_finite(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _sanitize_non_finite(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_non_finite(item) for item in value]
    return value


def _cap_rows(result: dict, key: str) -> dict:
    rows = result.get(key)
    if isinstance(rows, list) and len(rows) > MAX_RETURNED_ROWS:
        result[key] = rows[:MAX_RETURNED_ROWS]
        result["truncated"] = True
    return result


def execute_chatbot_tool(name: str, raw_input: object) -> dict:
    """Validate Nova's tool request and call only an explicit service function."""
    if not isinstance(raw_input, dict):
        raise InvalidToolRequest("Tool input must be a JSON object.")

    try:
        if name == "get_portfolio_summary":
            args = _FundRangeArgs.model_validate(raw_input)
            result = get_portfolio_summary(PortfolioRequest(**_range_request(args)))
            return _json_model(PortfolioSummaryResponse, result)

        if name == "get_top_positions":
            args = _TopPositionsArgs.model_validate(raw_input)
            result = get_top_positions(TopPositionsRequest(fund=args.fund))
            return _json_model(TopPositionsResponse, result)

        if name == "get_holdings_summary":
            args = _FundRangeArgs.model_validate(raw_input)
            result = get_all_holdings_summary(
                AllHoldingsRequest(**_range_request(args))
            )
            return _cap_rows(
                _json_model(AllHoldingsSummaryResponse, result), "holdings"
            )

        if name == "get_holding_summary":
            args = _HoldingArgs.model_validate(raw_input)
            result = get_holding_summary(
                HoldingRequest(**_range_request(args), ticker=args.ticker)
            )
            return _json_model(HoldingSummaryResponse, result)

        if name == "get_trades":
            args = _TradesArgs.model_validate(raw_input)
            result = get_trades(
                HoldingRequest(**_range_request(args), ticker=args.ticker)
            )
            return _cap_rows(_json_model(TradesResponse, result), "trades")

        if name == "get_dividends":
            args = _HoldingArgs.model_validate(raw_input)
            result = get_dividends(
                HoldingRequest(**_range_request(args), ticker=args.ticker)
            )
            return _cap_rows(_json_model(DividendsResponse, result), "dividends")

    except ValidationError as error:
        raise InvalidToolRequest(
            "Tool arguments are invalid or unsupported."
        ) from error

    raise InvalidToolRequest("Tool name is not allowlisted.")
