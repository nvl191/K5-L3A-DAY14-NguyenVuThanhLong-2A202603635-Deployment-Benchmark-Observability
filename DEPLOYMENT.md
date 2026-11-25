# Deployment Information

## Public URL

https://day14-agent-production-43e12fb4.up.railway.app

## Platform

Railway. Deploy thư mục `06-lab-complete/` bằng Dockerfile (`railway.toml`), kèm một service Redis trong cùng project.

## Cách deploy

```bash
cd 06-lab-complete
railway login
railway init --name day14-agent
railway add --database redis
railway add --service day14-agent
railway variable set ENVIRONMENT=production PORT=8000 LOG_LEVEL=INFO RATE_LIMIT_PER_MINUTE=10 DAILY_BUDGET_USD=1.0 'REDIS_URL=${{ Redis.REDIS_URL }}' --service day14-agent --skip-deploys
KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
printf '%s' "$KEY" | railway variable set AGENT_API_KEY --stdin --service day14-agent --skip-deploys
railway up --service day14-agent
railway domain
```

## Test Commands

Đặt `AGENT_API_KEY` bằng key đã cấu hình trên Railway (không ghi key vào repo).

```bash
BASE=https://day14-agent-production-43e12fb4.up.railway.app
```

### Health và readiness

```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"     # 200
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"      # 200
```

### API không có key và có key

```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -d '{"question":"Hello"}'   # 401
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" -d '{"question":"Hello"}'   # 200
```

Kết quả chạy ngày 2026-11-25: `200`, `200`, `401`, `200`.

## Environment Variables Set

| Biến | Giá trị |
|---|---|
| `ENVIRONMENT` | `production` |
| `PORT` | `8000` |
| `LOG_LEVEL` | `INFO` |
| `RATE_LIMIT_PER_MINUTE` | `10` |
| `DAILY_BUDGET_USD` | `1.0` |
| `REDIS_URL` | tham chiếu `${{ Redis.REDIS_URL }}` |
| `AGENT_API_KEY` | secret, chỉ đặt trên Railway |

## Screenshots

- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
