"""Async OCR task manager.
In-memory task store with status tracking. Supports background OCR processing.

⚠️ LIMITATION: The task store is a plain dict — all tasks are lost on
process restart or crash. Not suitable for production unless replaced
with Redis/DB-backed storage (see `REDIS_URL` env var)."""
import uuid, asyncio, time, logging, base64
from enum import Enum
from typing import Optional

log = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"


class OCRTask:
    """Represents a single async OCR task."""

    def __init__(self, image_base64: str, filename: Optional[str] = None):
        self.task_id = uuid.uuid4().hex[:12]
        self.status = TaskStatus.PENDING
        self.image_base64 = image_base64
        self.filename = filename
        self.result: Optional[dict] = None
        self.error: Optional[str] = None
        self.created_at = time.time()
        self.completed_at: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "filename": self.filename,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "error": self.error,
        }


class OCRTaskManager:
    """In-memory async OCR task manager.
    
    Processes tasks in the background using asyncio.
    """

    def __init__(self):
        self._tasks: dict[str, OCRTask] = {}

    def submit(self, image_base64: str, filename: Optional[str] = None) -> OCRTask:
        task = OCRTask(image_base64, filename)
        self._tasks[task.task_id] = task
        # Start background processing
        asyncio.create_task(self._process(task))
        return task

    def get_task(self, task_id: str) -> Optional[OCRTask]:
        return self._tasks.get(task_id)

    async def _process(self, task: OCRTask):
        """Background processing: OCR + optional classification."""
        from app.services.ocr_service import parse_invoice_with_openrouter
        from app.services.ocr_cache import ocr_cache

        task.status = TaskStatus.PROCESSING

        try:
            image_bytes = base64.b64decode(task.image_base64)

            # Check cache first
            cached = await ocr_cache.get(image_bytes)
            if cached:
                task.result = cached
                task.status = TaskStatus.DONE
                task.completed_at = time.time()
                log.info(f"Task {task.task_id}: cache hit")
                return

            # Run OCR
            result = parse_invoice_with_openrouter(task.image_base64)

            if result.get("success"):
                # Classify
                try:
                    from app.services.classification_service import classify_invoice
                    result["classification"] = classify_invoice(result.get("fields", {}))
                except Exception as e:
                    log.warning(f"Classification failed for {task.task_id}: {e}")

                # Cache result
                await ocr_cache.set(image_bytes, result)

                task.result = result
                task.status = TaskStatus.DONE
            else:
                task.error = result.get("error", "OCR failed")
                task.status = TaskStatus.ERROR

        except Exception as e:
            task.error = str(e)
            task.status = TaskStatus.ERROR
            log.error(f"Task {task.task_id} failed: {e}")

        task.completed_at = time.time()


# Singleton
task_manager = OCRTaskManager()
