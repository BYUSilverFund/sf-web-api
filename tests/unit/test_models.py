"""
Tests for Pydantic model validation.
"""

from datetime import date

import pytest

from app.models.fund import FundRequest, FundSummaryResponse
from app.models.portfolio import PortfolioRequest, PortfolioSummaryResponse


class TestFundRequest:
    """Test FundRequest model validation."""

    def test_valid_fund_request(self):
        """Test that valid date range is accepted."""
        start = date(2024, 1, 1)
        end = date(2024, 12, 31)

        request = FundRequest(start=start, end=end)
        assert request.start == start
        assert request.end == end

    def test_fund_request_with_string_dates(self):
        """Test that string dates are coerced to date objects."""
        request = FundRequest(start="2024-01-01", end="2024-12-31")
        assert request.start == date(2024, 1, 1)
        assert request.end == date(2024, 12, 31)

    def test_fund_request_missing_required_field(self):
        """Test that missing required fields raise validation error."""
        with pytest.raises(ValueError):
            FundRequest(start="2024-01-01")

    def test_fund_request_invalid_date_format(self):
        """Test that invalid date format raises validation error."""
        with pytest.raises(ValueError):
            FundRequest(start="01-01-2024", end="2024-12-31")


class TestPortfolioRequest:
    """Test PortfolioRequest model validation."""

    def test_valid_portfolio_request(self):
        """Test that valid portfolio request is accepted."""
        request = PortfolioRequest(
            fund="grad", start=date(2024, 1, 1), end=date(2024, 12, 31)
        )
        assert request.fund == "grad"
        assert request.start == date(2024, 1, 1)
        assert request.end == date(2024, 12, 31)

    def test_portfolio_request_case_sensitivity(self):
        """Test that portfolio names are case-sensitive."""
        request = PortfolioRequest(fund="GRAD", start="2024-01-01", end="2024-12-31")
        # Fund name should be stored as provided (no case conversion)
        assert request.fund == "GRAD"

    def test_portfolio_request_missing_fund_name(self):
        """Test that missing fund name raises validation error."""
        with pytest.raises(ValueError):
            PortfolioRequest(start="2024-01-01", end="2024-12-31")

    def test_portfolio_request_empty_fund_name_allowed(self):
        """Test that empty fund name is technically allowed by Pydantic."""
        # This tests current behavior - may want to add validation
        request = PortfolioRequest(fund="", start="2024-01-01", end="2024-12-31")
        assert request.fund == ""


class TestFundSummaryResponse:
    """Test FundSummaryResponse model."""

    def test_valid_summary_response(self):
        """Test creating a valid summary response."""
        response = FundSummaryResponse(
            start=date(2024, 1, 1),
            end=date(2024, 12, 31),
            trading_days=252,
            value=125000.50,
            total_return=5.2,
            sharpe_ratio=1.8,
            volatility=12.5,
            dividends=500.0,
            dividend_yield=0.5,
            alpha=2.1,
            beta=0.95,
            tracking_error=3.2,
            information_ratio=0.65,
        )
        assert response.total_return == 5.2
        assert response.sharpe_ratio == 1.8
        assert response.trading_days == 252

    def test_negative_total_return_allowed(self):
        """Test that negative returns are allowed."""
        response = FundSummaryResponse(
            start=date(2024, 1, 1),
            end=date(2024, 12, 31),
            trading_days=252,
            value=95000.0,
            total_return=-5.0,
            sharpe_ratio=-0.5,
            volatility=15.2,
            dividends=100.0,
            dividend_yield=0.1,
            alpha=-1.5,
            beta=1.05,
            tracking_error=4.1,
            information_ratio=-0.36,
        )
        assert response.total_return == -5.0


class TestPortfolioSummaryResponse:
    """Test PortfolioSummaryResponse model."""

    def test_valid_portfolio_summary_response(self):
        """Test creating a valid portfolio summary response."""
        response = PortfolioSummaryResponse(
            fund="grad",
            start=date(2024, 1, 1),
            end=date(2024, 12, 31),
            trading_days=252,
            value=50000.0,
            total_return=4.5,
            sharpe_ratio=1.6,
            volatility=11.2,
            dividends=250.0,
            dividend_yield=0.5,
            alpha=1.8,
            beta=0.92,
            tracking_error=2.9,
            information_ratio=0.62,
        )
        assert response.fund == "grad"
        assert response.total_return == 4.5
        assert response.value == 50000.0
