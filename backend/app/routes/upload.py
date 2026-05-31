from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Request, Depends
from pydantic import BaseModel
from typing import Optional, List
from app.core.auth_utils import get_current_ca
from app.core.security import limiter, validate_file_upload

router = APIRouter(prefix="/upload", tags=["Upload"])


class ComplianceResult(BaseModel):
    status: str  # pass, fail, warning
    itc_eligible: float
    itc_blocked: float
    category: str
    reason: str
    gstin_valid: bool


class UploadResponse(BaseModel):
    success: bool
    invoice_id: Optional[int] = None
    extracted_data: dict
    compliance: ComplianceResult
    message: str


@router.post("/", response_model=UploadResponse)
@limiter.limit("10/minute")
async def upload_invoice(
    request: Request,
    file: UploadFile = File(...),
    phone: Optional[str] = Form(None),
    user_id: Optional[int] = Form(None),
    auth = Depends(get_current_ca)
):
    """
    Upload invoice image, extract data via OCR, run compliance check, save to DB.
    
    - If phone provided: associates with user by phone
    - If user_id provided: associates with specific user
    """
    import base64
    from datetime import datetime
    from app.services.ocr_service import parse_invoice_with_openrouter
    from app.services.classification_service import classify_invoice
    from app.services.gstin_validator import validate_gstin
    from app.services.invoice_service import save_invoice
    from app.core.database import SessionLocal
    from app.models.base import User

    try:
        # Validate file
        validate_file_upload(file.content_type or "image/jpeg", 0)
        contents = await file.read()
        validate_file_upload(file.content_type or "image/jpeg", len(contents))
        image_base64 = base64.b64encode(contents).decode("utf-8")

        # Run OCR
        ocr_result = parse_invoice_with_openrouter(image_base64)

        if not ocr_result.get("success"):
            raise HTTPException(status_code=400, detail=ocr_result.get("error", "OCR failed"))

        fields = ocr_result.get("fields", {})

        # Validate GSTIN
        gstin_val = fields.get("seller_gstin", {}).get("value", "")
        gstin_check = validate_gstin(gstin_val) if gstin_val else {"is_valid": False}

        # Classify invoice
        classification = classify_invoice(fields)

        # Determine compliance status
        if classification.get("itc_blocked", 0) > 0:
            status = "blocked"
            message = f"ITC blocked under {classification.get('reason', 'Section 17(5)')}"
        elif not gstin_check.get("is_valid"):
            status = "warning"
            message = "Invalid GSTIN - ITC claim at risk"
        else:
            status = "pass"
            message = "Invoice compliant - ITC eligible"

        compliance = ComplianceResult(
            status=status,
            itc_eligible=classification.get("itc_eligible", 0),
            itc_blocked=classification.get("itc_blocked", 0),
            category=classification.get("category", "Other"),
            reason=classification.get("reason", ""),
            gstin_valid=gstin_check.get("is_valid", False)
        )

        # Save to database if user context provided
        invoice_id = None
        if phone:
            db_result = save_invoice(phone, fields)
            if db_result.get("success"):
                invoice_id = db_result.get("invoice_id")

        return UploadResponse(
            success=True,
            invoice_id=invoice_id,
            extracted_data=fields,
            compliance=compliance,
            message=message
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compliance-check")
@limiter.limit("20/minute")
async def compliance_check(request: Request, file: UploadFile = File(...), auth = Depends(get_current_ca)):
    """
    Upload invoice and get compliance check without saving.
    Quick check for CA dashboard.
    """
    import base64
    from app.services.ocr_service import parse_invoice_with_openrouter
    from app.services.classification_service import classify_invoice
    from app.services.gstin_validator import validate_gstin

    try:
        validate_file_upload(file.content_type or "image/jpeg", 0)
        contents = await file.read()
        validate_file_upload(file.content_type or "image/jpeg", len(contents))
        image_base64 = base64.b64encode(contents).decode("utf-8")

        ocr_result = parse_invoice_with_openrouter(image_base64)

        if not ocr_result.get("success"):
            raise HTTPException(status_code=400, detail=ocr_result.get("error", "OCR failed"))

        fields = ocr_result.get("fields", {})

        # Run compliance checks
        gstin_val = fields.get("seller_gstin", {}).get("value", "")
        gstin_check = validate_gstin(gstin_val) if gstin_val else {"is_valid": False}
        classification = classify_invoice(fields)

        # Build compliance report
        checks = []
        
        # GSTIN check
        if gstin_check.get("is_valid"):
            checks.append({"check": "GSTIN Valid", "status": "pass", "detail": f"Valid GSTIN: {gstin_val}"})
        else:
            checks.append({"check": "GSTIN Valid", "status": "fail", "detail": "Invalid or missing GSTIN"})

        # ITC eligibility
        if classification.get("itc_blocked", 0) > 0:
            checks.append({
                "check": "ITC Eligibility", 
                "status": "fail", 
                "detail": f"Blocked: {classification.get('reason', 'Section 17(5)')}"
            })
        else:
            checks.append({
                "check": "ITC Eligibility", 
                "status": "pass", 
                "detail": f"Eligible: Rs.{classification.get('itc_eligible', 0):,.2f}"
            })

        # Invoice amount check
        total = fields.get("total_amount", {}).get("value", 0) or 0
        if total > 0:
            checks.append({"check": "Amount Valid", "status": "pass", "detail": f"Total: Rs.{total:,.2f}"})
        else:
            checks.append({"check": "Amount Valid", "status": "warning", "detail": "Amount not detected"})

        overall_status = "pass" if all(c["status"] == "pass" for c in checks) else "fail" if any(c["status"] == "fail" for c in checks) else "warning"

        return {
            "success": True,
            "overall_status": overall_status,
            "extracted_fields": fields,
            "classification": classification,
            "gstin_validation": gstin_check,
            "checks": checks
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
