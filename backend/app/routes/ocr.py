"""OCR routes — sync, async, and upload variants with Redis caching."""
from fastapi import APIRouter, UploadFile, File, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import Optional
import base64

from app.services.ocr_async import task_manager, TaskStatus
from app.services.ocr_cache import ocr_cache
from app.core.auth_utils import get_current_ca
from app.core.security import limiter, validate_file_upload

router = APIRouter(prefix="/ocr", tags=["OCR"])


# ── Request/Response Models ──────────────────────────────────────────────────

class OCRRequest(BaseModel):
    image_base64: str


class OCRResponse(BaseModel):
    success: bool
    fields: dict
    overall_confidence: float
    error: Optional[str] = None
    cached: bool = False


class OCRAsyncSubmitResponse(BaseModel):
    task_id: str
    status: str


class OCRAsyncStatusResponse(BaseModel):
    task_id: str
    status: str
    created_at: float
    completed_at: Optional[float] = None
    error: Optional[str] = None


class OCRAsyncResultResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[dict] = None
    error: Optional[str] = None


# ── Sync Endpoints (with caching) ────────────────────────────────────────────

@router.post("/", response_model=OCRResponse)
@limiter.limit("20/minute")
async def ocr_invoice(request: Request, ocr_req: OCRRequest, auth = Depends(get_current_ca)):
    """Process an invoice image synchronously with Redis caching."""
    try:
        from app.services.ocr_service import parse_invoice_with_openrouter

        image_bytes = base64.b64decode(ocr_req.image_base64)

        # Check cache
        cached = await ocr_cache.get(image_bytes)
        if cached:
            return OCRResponse(
                success=True,
                fields=cached.get("fields", {}),
                overall_confidence=cached.get("overall_confidence", 0),
                cached=True,
            )

        # Run OCR
        result = parse_invoice_with_openrouter(ocr_req.image_base64)

        # Cache on success
        if result.get("success"):
            await ocr_cache.set(image_bytes, result)

        return OCRResponse(
            success=result.get("success", False),
            fields=result.get("fields", {}),
            overall_confidence=result.get("overall_confidence", 0),
            error=result.get("error"),
        )
    except Exception as e:
        return OCRResponse(
            success=False, fields={}, overall_confidence=0, error=str(e),
        )


@router.post("/upload")
@limiter.limit("20/minute")
async def upload_invoice(request: Request, file: UploadFile = File(...), auth = Depends(get_current_ca)):
    """Upload + OCR + classify with caching."""
    try:
        from app.services.ocr_service import parse_invoice_with_openrouter
        from app.services.classification_service import classify_invoice

        validate_file_upload(file.content_type or "image/jpeg", 0)  # size checked after read
        contents = await file.read()
        validate_file_upload(file.content_type or "image/jpeg", len(contents))

        # Check cache
        cached = await ocr_cache.get(contents)
        if cached:
            classification = classify_invoice(cached.get("fields", {}))
            return {
                "success": True,
                "filename": file.filename,
                "fields": cached.get("fields", {}),
                "overall_confidence": cached.get("overall_confidence", 0),
                "classification": classification,
                "cached": True,
            }

        image_base64 = base64.b64encode(contents).decode("utf-8")

        result = parse_invoice_with_openrouter(image_base64)
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "OCR failed"))

        classification = classify_invoice(result.get("fields", {}))

        # Cache on success
        await ocr_cache.set(contents, result)

        return {
            "success": True,
            "filename": file.filename,
            "fields": result.get("fields", {}),
            "overall_confidence": result.get("overall_confidence", 0),
            "classification": classification,
            "cached": False,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Async Endpoints ──────────────────────────────────────────────────────────

@router.post("/async", response_model=OCRAsyncSubmitResponse)
@limiter.limit("30/minute")
async def ocr_async_submit(request: Request, ocr_req: OCRRequest, auth = Depends(get_current_ca)):
    """Submit an OCR job for async processing. Returns task_id immediately."""
    task = task_manager.submit(ocr_req.image_base64)
    return OCRAsyncSubmitResponse(task_id=task.task_id, status=task.status.value)


@router.post("/async/upload", response_model=OCRAsyncSubmitResponse)
@limiter.limit("20/minute")
async def ocr_async_upload(request: Request, file: UploadFile = File(...), auth = Depends(get_current_ca)):
    """Upload image + submit async OCR job."""
    validate_file_upload(file.content_type or "image/jpeg", 0)
    contents = await file.read()
    validate_file_upload(file.content_type or "image/jpeg", len(contents))
    image_base64 = base64.b64encode(contents).decode("utf-8")
    task = task_manager.submit(image_base64, filename=file.filename)
    return OCRAsyncSubmitResponse(task_id=task.task_id, status=task.status.value)


@router.get("/async/{task_id}/status", response_model=OCRAsyncStatusResponse)
async def ocr_async_status(task_id: str):
    """Check the status of an async OCR task."""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return OCRAsyncStatusResponse(
        task_id=task.task_id,
        status=task.status.value,
        created_at=task.created_at,
        completed_at=task.completed_at,
        error=task.error,
    )


@router.get("/async/{task_id}/result", response_model=OCRAsyncResultResponse)
async def ocr_async_result(task_id: str):
    """Get the result of a completed async OCR task."""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    if task.status == TaskStatus.PENDING or task.status == TaskStatus.PROCESSING:
        raise HTTPException(status_code=425, detail="Task still processing")
    return OCRAsyncResultResponse(
        task_id=task.task_id,
        status=task.status.value,
        result=task.result,
        error=task.error,
    )
