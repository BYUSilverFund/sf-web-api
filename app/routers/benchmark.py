from fastapi import APIRouter
from app.services.benchmark import get_benchmark_summary, get_benchmark_time_series
from app.models.benchmark import BenchmarkRequest, BenchmarkSummaryResponse, BenchmarkTimeSeriesResponse
router = APIRouter()

@router.post(
    "/summary",
    response_model=BenchmarkSummaryResponse,
    summary="Get Benchmark Summary",
    description="Returns summary statistics for benchmark over a date range.",
    response_description="Summary metrics for benchmark.",
    tags=["Benchmark"]
)
def fund_summary(holding_request: BenchmarkRequest) -> BenchmarkSummaryResponse:
    return BenchmarkSummaryResponse(**get_benchmark_summary(holding_request))

@router.post(
    "/time-series",
    response_model=BenchmarkTimeSeriesResponse,
    summary="Get Benchmark Time Series Values",
    description="Returns time series values for benchmark over a date range.",
    response_description="Time series values for benchmark.",
    tags=["Benchmark"]
)
def fund_time_series(holding_request: BenchmarkRequest) -> BenchmarkTimeSeriesResponse:
    return BenchmarkTimeSeriesResponse(**get_benchmark_time_series(holding_request))
