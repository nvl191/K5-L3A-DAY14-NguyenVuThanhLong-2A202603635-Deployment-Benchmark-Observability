"""
Production AI Agent — Part 6 Final Project

Luồng của POST /ask:
    API key (401) → kiểm tra input (422) → rate limit (429) → budget (402) → LLM → ghi chi phí
"""
import json
import logging
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import redis
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import r, redis_healthy
from utils.mock_llm import ask as llm_ask


# ── Structured logging: mỗi dòng log là 1 JSON object ──
class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "event": record.getMessage(),
            **getattr(record, "fields", {}),
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
logger = logging.getLogger("agent")
logger.handlers = [handler]
logger.setLevel(settings.log_level)
logger.propagate = False

START_TIME = time.time()


# ── Graceful shutdown ──
# uvicorn nhận SIGTERM, ngừng nhận kết nối mới, chờ request đang chạy xong
# rồi mới chạy phần sau `yield` để dọn dẹp.
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup", extra={"fields": {"environment": settings.environment}})
    if not settings.agent_api_key:
        logger.warning("AGENT_API_KEY is not set: every /ask request will get 401")
    yield
    r.close()
    logger.info("shutdown")


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        # Chi tiết lỗi chỉ ghi vào log, client không thấy stack trace
        logger.exception("unhandled_error", extra={"fields": {"path": request.url.path}})
        response = JSONResponse(status_code=500, content={"detail": "Internal server error"})
    logger.info("request", extra={"fields": {
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "ms": round((time.perf_counter() - start) * 1000, 1),
    }})
    return response


# ── Xử lý lỗi ──
@app.exception_handler(RequestValidationError)
async def invalid_input(request: Request, exc: RequestValidationError):
    # Chỉ trả vị trí và lý do, không lặp lại dữ liệu client gửi lên
    errors = [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})


@app.exception_handler(redis.RedisError)
async def redis_unavailable(request: Request, exc: redis.RedisError):
    # Không kiểm tra được rate limit / budget thì không gọi LLM
    logger.error("redis_error", extra={"fields": {"error": type(exc).__name__}})
    return JSONResponse(status_code=503, content={"detail": "Service temporarily unavailable"})


# ── Endpoints ──
class AskRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(..., min_length=1, max_length=2000)
    user_id: str | None = Field(default=None, max_length=128)


@app.get("/health")
def health():
    """Liveness: process còn chạy là 200, không phụ thuộc Redis."""
    return {"status": "ok", "uptime_seconds": round(time.time() - START_TIME, 1)}


@app.get("/ready")
def ready():
    """Readiness: chỉ nhận traffic khi Redis kết nối được."""
    if not redis_healthy():
        raise HTTPException(status_code=503, detail="Redis is not available")
    return {"status": "ready"}


def _estimate_tokens(text: str) -> int:
    # Mock LLM không trả số token: ước tính khoảng 4 ký tự = 1 token
    return max(1, len(text) // 4)


@app.post("/ask")
def ask(body: AskRequest, api_key: str = Depends(verify_api_key)):
    check_rate_limit(api_key)
    check_budget()
    answer = llm_ask(body.question)
    cost = record_cost(_estimate_tokens(body.question), _estimate_tokens(answer))
    logger.info("llm_call", extra={"fields": {
        "user_id": body.user_id,
        "question_length": len(body.question),
        "cost_usd": round(cost, 8),
    }})
    return {"question": body.question, "answer": answer}
