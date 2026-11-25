"""
Rate limiting (tiêu chí 7) — sliding window 60 giây bằng Redis sorted set.

  • Mỗi API key tối đa RATE_LIMIT_PER_MINUTE request trong 60 giây
  • Vượt giới hạn → HTTP 429 kèm header Retry-After
  • State nằm trong Redis: mọi worker / instance dùng chung, restart không mất
"""
import hashlib
import uuid

from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

WINDOW_SECONDS = 60

# Redis chạy cả script như một bước, nên nhiều request đồng thời không thể cùng "lọt".
# Trả về 0 nếu cho qua, ngược lại là số giây phải chờ.
SLIDING_WINDOW = """
local t = redis.call('TIME')
local now = tonumber(t[1]) + tonumber(t[2]) / 1000000
local window = tonumber(ARGV[1])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - window)
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[2]) then
  local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
  if oldest[2] then
    return math.max(1, math.ceil(tonumber(oldest[2]) + window - now))
  end
  return window
end
redis.call('ZADD', KEYS[1], now, ARGV[3])
redis.call('EXPIRE', KEYS[1], window)
return 0
"""


def check_rate_limit(key: str) -> None:
    # Lưu hash của API key, không lưu key thật vào Redis
    redis_key = "ratelimit:" + hashlib.sha256(key.encode()).hexdigest()[:16]
    retry_after = r.eval(
        SLIDING_WINDOW,
        1,
        redis_key,
        WINDOW_SECONDS,
        settings.rate_limit_per_minute,
        uuid.uuid4().hex,
    )
    if retry_after:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )
