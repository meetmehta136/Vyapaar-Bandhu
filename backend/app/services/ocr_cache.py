"""Optional Redis cache for OCR results.
Gracefully falls back to in-memory dict if Redis is unavailable.
Supports both sync and async callers."""
import os, hashlib, json, logging
from typing import Optional

log = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "")
CACHE_TTL = int(os.getenv("OCR_CACHE_TTL", "3600"))  # 1 hour default


class OCRCache:
    """Cache for OCR results keyed by image content hash.

    Redis-backed with graceful fallback to in-memory dict when Redis is unavailable.
    Both `get` and `set` work in sync and async contexts.
    """

    def __init__(self):
        self._client: Optional[any] = None
        self._available = False
        self._local: dict[str, dict] = {}

    def _connect(self):
        if self._available or not REDIS_URL:
            return
        try:
            import redis
            self._client = redis.from_url(REDIS_URL, decode_responses=True)
            self._available = True
            log.info("Connected to Redis for OCR caching")
        except Exception as e:
            log.warning(f"Redis unavailable, using in-memory fallback: {e}")

    @staticmethod
    def _image_key(image_bytes: bytes) -> str:
        return f"ocr:{hashlib.sha256(image_bytes).hexdigest()}"

    # ── Sync API ──────────────────────────────────────────────────────────

    def get_sync(self, image_bytes: bytes) -> Optional[dict]:
        key = self._image_key(image_bytes)
        self._connect()
        if self._available and self._client:
            try:
                data = self._client.get(key)
                if data:
                    log.info(f"OCR cache HIT: {key[:20]}...")
                    return json.loads(data)
            except Exception as e:
                log.warning(f"Redis get failed: {e}")
        return self._local.get(key)

    def set_sync(self, image_bytes: bytes, result: dict):
        key = self._image_key(image_bytes)
        self._connect()
        if self._available and self._client:
            try:
                self._client.setex(key, CACHE_TTL, json.dumps(result))
                log.info(f"OCR cache SET: {key[:20]}...")
                return
            except Exception as e:
                log.warning(f"Redis set failed: {e}")
        self._local[key] = result

    # ── Async API ─────────────────────────────────────────────────────────

    async def get(self, image_bytes: bytes) -> Optional[dict]:
        return self.get_sync(image_bytes)

    async def set(self, image_bytes: bytes, result: dict):
        self.set_sync(image_bytes, result)

    async def clear(self):
        self._connect()
        if self._available and self._client:
            try:
                self._client.flushdb()
            except Exception:
                pass
        self._local.clear()


# Singleton
ocr_cache = OCRCache()
