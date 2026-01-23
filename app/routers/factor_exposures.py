from fastapi import APIRouter, Depends

from app.auth import cognito_auth
from app.services.factor_exposures import (
    all_fund_weighted_exposures,
    factor_breakdown,
    fund_weighted_exposures,
    holding_exposures,
)


router = APIRouter()

# # saving for future implementation
# @router.get(
#     "/latest",
#     summary="Get Factor Exposure Matrix",
#     description="Returns entire factor exposures matrix",
#     response_description="Latest factor exposure matrix",
#     tags=["Factor Exposures"],
# )
# def factor_exposures() -> StreamingResponse:
#     factor_exposures = get_factor_exposures()
#     csv_string = factor_exposures.write_csv()
#     csv_io = io.StringIO(csv_string)
#     headers = {"Content-Disposition": "attachment; filename=factor_exposures.csv"}
#     media_type = "text/csv"
#     return StreamingResponse(content=csv_io, headers=headers, media_type=media_type)


@router.get(
    "/all_funds",
    summary="Get All Funds Factor Exposures",
    description="Returns factor exposures for all funds",
    response_description="Factor exposures and positions not found in factor exposures for all funds",
    tags=["Factor Exposures"],
)
def all_fund_exposures(_claims=Depends(cognito_auth)) -> dict:
    exposure, positions_not_in_exposures = all_fund_weighted_exposures()
    return {
        "exposures": exposure,
        "positions_not_in_exposures": positions_not_in_exposures,
    }


@router.get(
    "/holdings/{holding}",
)
def holding_factor_exposures(holding: str, _claims=Depends(cognito_auth)) -> dict:
    return holding_exposures(holding)


@router.get(
    "/{fund}",
    summary="Get Fund Factor Exposures",
    description="Returns factor exposures for a specific fund",
    response_description="Factor exposures and positions not found in factor exposures for the specified fund",
    tags=["Factor Exposures"],
)
def fund_exposures(fund: str, _claims=Depends(cognito_auth)) -> dict:
    exposure, positions_not_in_exposures = fund_weighted_exposures(fund)
    return {
        "exposures": exposure,
        "positions_not_in_exposures": positions_not_in_exposures,
    }


@router.get(
    "/{fund}/{factor}",
    summary="Get Fund Factor Exposure Breakdown",
    description="Get a breakdown of what holdings contribute to this factor",
    response_description="Breakdown of holdings contributing to the specified factor for the specified fund",
    tags=["Factor Exposures"],
)
def fund_factor_breakdown(
    fund: str, factor: str, _claims=Depends(cognito_auth)
) -> dict:
    factor = factor.upper()
    if not factor.startswith("USSLOWL_"):
        factor = "USSLOWL_" + factor
    return factor_breakdown(fund, factor)
