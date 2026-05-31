from fastapi import APIRouter, Depends
from app.core.auth_utils import get_current_ca
from app.models.base import CAPartner
from app.services.compliance_engine import (
    check_itc_eligibility,
    calculate_gst_liability,
    calculate_penalty,
    get_filing_deadlines
)

router = APIRouter(prefix="/compliance", tags=["Compliance"], dependencies=[Depends(get_current_ca)])


@router.get("/itc/{category}")
def itc_check(category: str, current_user: CAPartner = Depends(get_current_ca)):
    return check_itc_eligibility(category)


@router.get("/deadlines/{period}")
def deadlines(period: str, current_user: CAPartner = Depends(get_current_ca)):
    return get_filing_deadlines(period)


@router.get("/penalty/{return_type}/{days_late}/{tax_liability}")
def penalty(return_type: str, days_late: int, tax_liability: float, current_user: CAPartner = Depends(get_current_ca)):
    return calculate_penalty(return_type, days_late, tax_liability)


@router.post("/liability")
def liability(transactions: list, current_user: CAPartner = Depends(get_current_ca)):
    return calculate_gst_liability(transactions)