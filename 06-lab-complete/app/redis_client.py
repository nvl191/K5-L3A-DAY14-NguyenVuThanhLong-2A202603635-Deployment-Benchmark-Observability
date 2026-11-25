"""
Kết nối Redis dùng chung cho rate limiter và cost guard.

Tạo client không mở kết nối ngay, nên app vẫn khởi động được khi Redis chưa sẵn sàng.
Timeout ngắn để request không bị treo khi Redis gặp sự cố.
"""
import redis

from app.config import settings

r = redis.Redis.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_connect_timeout=2,
    socket_timeout=2,
)


def redis_healthy() -> bool:
    """Dùng cho GET /ready: Redis không kết nối được → False."""
    try:
        return bool(r.ping())
    except redis.RedisError:
        return False
