from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from typing import Any, Dict
import json, os, time, uuid
from datetime import datetime, timezone

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "app.log")
os.makedirs(LOG_DIR, exist_ok=True)

class JsonLineWriter:
    def __init__(self, path: str):
        self.path = path
    def write(self, record: Dict[str, Any]) -> None:
        record["_ts"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, separators=(",", ":"), ensure_ascii=False) + "\n")

_writer = JsonLineWriter(LOG_FILE)

class Audit:
    def event(self, kind: str, **fields: Any) -> None:
        _writer.write({"kind": kind, **fields})

audit = Audit()

class StructuredAuditMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    async def dispatch(self, request, call_next):
        cid = str(uuid.uuid4())
        t0 = time.perf_counter()
        try:
            try:
                body = await request.body()
                body_len = len(body or b"")
            except Exception:
                body_len = -1
            audit.event(
                "http_request",
                cid=cid,
                method=request.method,
                path=request.url.path,
                query=str(request.url.query),
                body_len=body_len,
                client=getattr(request.client, "host", None),
            )
            response = await call_next(request)
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            audit.event(
                "http_response",
                cid=cid,
                status=response.status_code,
                latency_ms=latency_ms,
            )
            return response
        except Exception as e:
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            audit.event("http_exception", cid=cid, error=str(e), latency_ms=latency_ms)
            raise
