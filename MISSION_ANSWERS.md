# Day 14 Lab - Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns trong `01-localhost-vs-production/develop/app.py`

| # | Dòng | Vấn đề | Hậu quả | Cách sửa |
|---|------|--------|---------|----------|
| 1 | 17–18 | API key và mật khẩu database viết thẳng trong code | Ai đọc được repo là lấy được secret; xoá sau đó vẫn còn trong lịch sử git; muốn đổi key phải sửa code và deploy lại | Đọc từ biến môi trường, không commit `.env` |
| 2 | 21–22 | `DEBUG` và `MAX_TOKENS` viết cứng | Không đổi được giữa dev và production nếu không sửa code | Gom cấu hình vào một chỗ, đọc từ env |
| 3 | 33, 38 | Dùng `print()` để ghi log | Không có thời gian, mức độ, định dạng cố định; khó lọc và tìm kiếm; in cả nội dung câu hỏi và câu trả lời | Dùng `logging` có cấu trúc, chỉ ghi thông tin cần thiết |
| 4 | 34 | In `OPENAI_API_KEY` ra log | Người xem được log (đồng đội, hệ thống gom log) lấy được key | Không bao giờ ghi secret vào log |
| 5 | Cả file (ghi chú ở dòng 42–43) | Không có health check | Nền tảng không có cách hỏi app còn phục vụ được không để restart khi app treo | Thêm `GET /health` (và `GET /ready`) |
| 6 | 51 | `host="localhost"` | Chỉ nhận kết nối từ chính máy hoặc container đó, bên ngoài không gọi vào được | Dùng `0.0.0.0` |
| 7 | 52 | Cổng cố định `8000` | Railway, Render cấp cổng qua biến `PORT`; app nghe sai cổng thì deploy thất bại | Đọc `PORT` từ env |
| 8 | 53 | `reload=True` luôn bật | Chạy thêm tiến trình theo dõi file, tốn tài nguyên; file thay đổi là app tự khởi động lại giữa lúc đang phục vụ | Chỉ bật khi `DEBUG=true` |
| 9 | 13, 47–54 | Không có bước xử lý khi tắt (không `lifespan`, không cờ sẵn sàng) | Không có chỗ để ngừng nhận traffic, đóng kết nối hay ghi log khi nền tảng tắt app; chỉ dựa vào mặc định của uvicorn | Dùng `lifespan` để dọn dẹp và xử lý SIGTERM |

### Exercise 1.2: Chạy bản develop

Lệnh chạy: `python app.py` trong `01-localhost-vs-production/develop/` (Python 3.11.18).

```text
$ curl -i -X POST "http://localhost:8000/ask?question=Hello"
HTTP/1.1 200 OK
{"answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}

$ curl -i -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{"question":"Hello"}'
HTTP/1.1 422 Unprocessable Entity
{"detail":[{"type":"missing","loc":["query","question"],"msg":"Field required","input":null}]}

$ curl -i http://localhost:8000/health
HTTP/1.1 404 Not Found
{"detail":"Not Found"}
```

Log của server (key đã che):

```text
[DEBUG] Got question: Hello
[DEBUG] Using key: sk-***
[DEBUG] Response: Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic.
INFO:     127.0.0.1:53723 - "POST /ask?question=Hello HTTP/1.1" 200 OK
```

Nhận xét:

- App chạy được trên máy, nhưng secret bị in ra log ở mỗi request.
- Bản develop nhận `question` trên URL, nên gửi JSON bị 422.
- Không có `/health` (404).
- Khi gửi SIGTERM (`kill -TERM`), uvicorn vẫn tự tắt êm với exit code 0. Điểm thiếu là app không có bước dọn dẹp của riêng nó.

### Exercise 1.3: So sánh develop và production

| Feature | Develop | Production | Why Important? |
|---------|---------|------------|----------------|
| Config | Viết cứng trong `app.py` (dòng 21–22) | Gom vào `config.py` (dòng 14–45), đọc từ env, có `validate()` | Cùng một bản code chạy được ở dev, staging, production. Thiếu `AGENT_API_KEY` khi `ENVIRONMENT=production` thì app dừng ngay lúc khởi động, thay vì chạy mà không được bảo vệ |
| Secrets | Key và mật khẩu trong code, còn in ra log (dòng 17–18, 34) | `os.getenv` (`config.py` dòng 27, 32); log chỉ ghi độ dài câu hỏi và IP (`app.py` dòng 111–115) | Đẩy code lên GitHub không làm lộ key; đổi key không cần sửa code |
| Host / Port | `localhost:8000` cố định (dòng 51–52) | `0.0.0.0` và `PORT` từ env (`app.py` dòng 196–197) | Container và nền tảng cloud cần gọi vào được, đúng cổng được cấp |
| Debug reload | Luôn bật (dòng 53) | Chỉ bật khi `DEBUG=true` (`app.py` dòng 198) | Tránh app tự khởi động lại ngoài ý muốn khi đang phục vụ |
| Health check | Không có | `/health` và `/ready` (`app.py` dòng 135–161) | Nền tảng gọi `/health`, lỗi thì restart container. Load balancer gọi `/ready`, trả 503 thì chưa gửi request vào |
| Logging | `print()` | `logging` kèm thời gian, mức độ, sự kiện (`app.py` dòng 28–31, 111–122) | Lọc và tìm được log khi có sự cố |
| Shutdown | Chỉ dựa vào mặc định của uvicorn | `lifespan` hạ cờ `is_ready` và chạy bước dọn dẹp (dòng 63–67), có handler SIGTERM ghi log (dòng 180–189) | Khi deploy bản mới, request đang xử lý được hoàn thành và kết nối được đóng đúng cách |

Ví dụ một anti-pattern đã được sửa: `develop/app.py` dòng 52 (`port=8000`) → `production/app.py` dòng 197 (`port=settings.port`), giá trị đọc ở `production/config.py` dòng 18.

#### Kết quả chạy bản production

```text
$ curl -i -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{"question":"Hello"}'
HTTP/1.1 200 OK
{"question":"Hello","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.","model":"gpt-4o-mini"}

$ curl -i http://localhost:8000/health
HTTP/1.1 200 OK
{"status":"ok","uptime_seconds":1.0,"version":"1.0.0","environment":"development","timestamp":"2026-11-25T07:53:01.144089+00:00"}

$ curl -i http://localhost:8000/ready
HTTP/1.1 200 OK
{"ready":true}
```

Thử nghiệm thêm:

| Lệnh | Kết quả |
|---|---|
| `PORT=9000 python app.py` | `/health` trả 200 ở cổng 9000, không sửa code |
| `ENVIRONMENT=production python app.py` | Dừng với exit code 1: `ValueError: AGENT_API_KEY must be set in production!` |
| `OPENAI_API_KEY=fake python app.py`, gọi `/ask`, gửi SIGTERM | Thấy log startup, request, response, shutdown; exit code 0 |

#### Những chỗ bản production vẫn chưa tốt

- Gọi `/ask?question=Hello` (không có JSON body) trả **500** thay vì 4xx, vì `request.json()` không được bắt lỗi (dòng 104).
- Log chưa phải JSON hợp lệ: JSON nằm lồng trong chuỗi `msg` mà dấu ngoặc kép không được escape, ví dụ `{"time":"...","level":"INFO","msg":"{"event": "startup", ...}"}`.
- Chạy mặc định (không có `OPENAI_API_KEY`) thì không thấy log INFO của app: `config.py` gọi `logging.warning` trước khi `app.py` gọi `basicConfig`, nên cấu hình log sau đó không có tác dụng.
- Code không gọi `load_dotenv()`, nên sửa file `.env` không đổi được cấu hình; chỉ biến môi trường của tiến trình có tác dụng.

### Điều rút ra (Checkpoint 1)

- **Vì sao hardcode secret nguy hiểm:** ai đọc được code là đọc được secret. Git giữ toàn bộ lịch sử, nên xoá ở commit sau vẫn chưa đủ: phải thu hồi key cũ và tạo key mới.
- **Dùng biến môi trường:** code đọc bằng `os.getenv`, giá trị thật được đặt trên máy hoặc nền tảng chạy app. Repo chỉ chứa `.env.example` không có secret.
- **Vai trò health check:** `/health` cho biết tiến trình còn sống, lỗi thì nền tảng restart. `/ready` cho biết app nhận request được chưa, lỗi thì tạm ngừng gửi traffic mà không restart.
- **Graceful shutdown:** khi nhận SIGTERM, app ngừng nhận request mới, làm xong request đang chạy, đóng kết nối rồi thoát. Nhờ vậy deploy bản mới không cắt ngang người dùng.

## Part 2: Docker

### Exercise 2.1: Dockerfile cơ bản (`02-docker/develop/Dockerfile`)

1. **Base image:** `python:3.11` (dòng 8), bản đầy đủ gồm hệ điều hành Debian, Python và nhiều công cụ build, nên dung lượng lớn.
2. **Working directory:** `/app` (dòng 11). Các lệnh `COPY`, `RUN`, `CMD` phía sau chạy tại thư mục này.
3. **Vì sao COPY `requirements.txt` trước (dòng 14–20):** mỗi lệnh tạo một layer và Docker dùng lại layer cũ nếu đầu vào không đổi. Thư viện ít đổi, code đổi thường xuyên. Đặt `COPY requirements.txt` và `pip install` trước thì khi chỉ sửa code, bước cài thư viện được lấy từ cache. Nếu copy code trước, mỗi lần sửa code đều phải cài lại.
4. **CMD và ENTRYPOINT:** `CMD` là lệnh hoặc tham số mặc định, bị thay khi gõ lệnh khác sau tên image. `ENTRYPOINT` là chương trình cố định, phần gõ sau tên image được nối thêm làm tham số (muốn đổi phải dùng `--entrypoint`). Image này dùng `CMD ["python", "app.py"]` (dòng 30), nên `docker run --rm my-agent:develop python --version` in `Python 3.11.18` thay vì chạy app.

Kiểm chứng cache (thêm một dòng comment vào `app.py` của bản sao rồi build lại):

```text
[2/7] WORKDIR /app                          CACHED
[3/7] COPY .../requirements.txt .           CACHED
[4/7] RUN pip install ... -r requirements   CACHED
[5/7] COPY .../app.py .                     chạy lại
[6/7] RUN mkdir -p utils                    chạy lại
[7/7] COPY utils/mock_llm.py utils/         chạy lại
```

### Exercise 2.2: Build và chạy bản develop

Lệnh chạy từ gốc repo:

```bash
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
docker run -p 8000:8000 my-agent:develop
```

```text
GET  /health                               200 {"status":"ok","uptime_seconds":0.9,"container":true}
POST /ask?question=Hello                   200 {"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
POST /ask  (JSON {"question": ...})        422 {"detail":[{"type":"missing","loc":["query","question"],"msg":"Field required","input":null}]}
```

Bản develop nhận `question` trên URL, nên gửi JSON bị 422. Container chạy bằng user `root`.

### Exercise 2.3: Multi-stage build (`02-docker/production/Dockerfile`)

```bash
docker build -f 02-docker/production/Dockerfile -t my-agent:advanced .
docker images my-agent
```

| Image | `docker images` | Byte (`docker image inspect`) | User |
|---|---|---|---|
| `my-agent:develop` | 1.17 GB | 1 169 510 072 | root |
| `my-agent:advanced` | 188 MB | 188 415 952 | appuser |

- Develop: **1169.5 MB**
- Production: **188.4 MB**
- Chênh lệch: giảm 981.1 MB, tức **83.9%**

**Stage 1, `builder` (dòng 16–29):** từ `python:3.11-slim`, cài `gcc`, `libpq-dev`, rồi `pip install --user` để gom thư viện vào `/root/.local`.

**Stage 2, `runtime` (dòng 36–72):** bắt đầu lại từ `python:3.11-slim` sạch, tạo user thường, chỉ `COPY --from=builder` thư viện đã cài (dòng 45) và code, thêm `HEALTHCHECK`, chạy bằng `appuser`.

**Vì sao image nhỏ hơn:**

- Phần lớn nhờ **đổi base image**: theo `docker history`, lớp `pip install` của develop chỉ 48.9 MB, nên phần nền chiếm khoảng 1.12 GB. `python:3.11-slim` chỉ 150 MB.
- **Multi-stage** giữ công cụ build ở stage 1: trong image cuối không có `gcc`. Image cuối chỉ thêm 38.2 MB thư viện và vài KB code.

Kết quả chạy: `/health` 200, `/ask` gửi JSON trả 200, sau khoảng 35 giây `docker ps` báo `healthy`. `/ask?question=Hello` trả 500 vì app bản này chỉ đọc JSON body. `HEALTHCHECK` của Docker chỉ đánh dấu `unhealthy` khi lỗi, không tự restart container (khác với ghi chú ở dòng 67).

### Exercise 2.4: Docker Compose stack

```text
Client
  │  localhost:80  (443 cũng được publish)
  ▼
┌────────────────┐      agent:8000      ┌──────────────────────┐
│ nginx          │ ───────────────────▶ │ agent (FastAPI,      │
│ reverse proxy, │                      │ 2 uvicorn workers)   │
│ rate limit     │                      └─────┬──────────┬─────┘
└────────────────┘                            │          │
                                  redis:6379  ▼          ▼  qdrant:6333
                                        ┌──────────┐  ┌──────────┐
                                        │  redis   │  │  qdrant  │
                                        └──────────┘  └──────────┘
                     tất cả nằm trong network "internal" (bridge)
```

- **Service được start:** `redis`, `qdrant`, `agent`, `nginx`.
- **Thứ tự:** `agent` chờ `redis` và `qdrant` đạt `healthy` (`depends_on`), `nginx` khởi động sau `agent`.
- **Giao tiếp:** qua network `internal`, gọi nhau bằng **tên service** (Docker DNS), ví dụ `redis://redis:6379/0`, `server agent:8000`.
- **Cổng ra ngoài:** chỉ `nginx` publish cổng (80, 443). `agent`, `redis`, `qdrant` không gọi trực tiếp được từ máy host.

Lệnh:

```bash
cd 02-docker/production
touch .env.local
docker compose -p k5-day14-docker up -d --build
docker compose -p k5-day14-docker down -v
```

Lưu ý khi chạy: nếu Docker Desktop báo `mounts denied` khi mount `nginx.conf`, cần thêm thư mục chứa repo vào Settings → Resources → File Sharing. Kết quả dưới đây chạy trực tiếp trong repo sau khi đã chia sẻ thư mục.

```text
SERVICE   IMAGE                    STATUS         PORTS
agent     k5-day14-docker-agent    Up (healthy)   8000/tcp
nginx     nginx:alpine             Up             0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp
qdrant    qdrant/qdrant:v1.9.0     Up (healthy)   6333-6334/tcp
redis     redis:7-alpine           Up (healthy)   6379/tcp
```

Test qua Nginx:

```text
$ curl -i http://localhost/health
HTTP/1.1 200 OK
Server: nginx
X-Frame-Options: DENY
{"status":"ok","uptime_seconds":4.8,"version":"2.0.0","timestamp":"2026-11-25T08:40:22.202711"}

$ curl -i -X POST http://localhost/ask -H "Content-Type: application/json" -d '{"question":"Explain microservices"}'
HTTP/1.1 200 OK
Server: nginx
{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

| Kiểm tra thêm | Kết quả |
|---|---|
| Gửi 60 request `/ask` cùng lúc | 21 request 200, 39 request **429** (Nginx giới hạn 10 request/giây, `burst=20`) |
| Gọi thẳng `localhost:8000` | Không kết nối được, vì agent không publish cổng |
| Từ container `agent` nối tới `redis:6379`, `qdrant:6333` | Kết nối được |
| Gọi `https://localhost` | Lỗi: cổng 443 được publish nhưng `nginx.conf` chỉ `listen 80` |

Nhận xét từ code: `main.py` chưa dùng Redis hay Qdrant dù compose khai báo; ghi chú đầu file nói agent có 2 replicas nhưng thực tế chỉ chạy 1 container.

## Part 4: API Security

Token JWT trong các output được thay bằng `<TOKEN>`; một số header HTTP được lược bớt cho gọn.

### Exercise 4.1: API Key (`04-api-gateway/develop/app.py`)

- **Key được kiểm tra ở đâu:** hàm `verify_api_key` (dòng 39–54) đọc header `X-API-Key` (dòng 36), so với biến môi trường `AGENT_API_KEY` (dòng 35). Endpoint `/ask` gắn hàm này bằng `Depends` (dòng 70). `/health` và `/` không cần key.
- **Sai hoặc thiếu key:** thiếu key trả **401**, sai key trả **403**; hàm xử lý `/ask` không được chạy.
- **Rotate key:** đổi `AGENT_API_KEY` rồi khởi động lại app. Đã thử: đổi sang key mới thì key cũ trả 403, key mới trả 200. Cách này không có thời gian chuyển tiếp; muốn đổi mà không gián đoạn thì server nên chấp nhận đồng thời key cũ và mới trong một khoảng ngắn.
- **Điểm yếu:** không đặt biến môi trường thì app dùng key mặc định `demo-key-change-in-production`, và key này gọi được (200). Production nên từ chối khởi động khi thiếu key.

```text
$ AGENT_API_KEY=secret-key-123 python app.py

$ curl -i -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{"question":"Hello"}'
HTTP/1.1 401 Unauthorized
{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}

$ curl -i -X POST http://localhost:8000/ask -H "X-API-Key: wrong" -H "Content-Type: application/json" -d '{"question":"Hello"}'
HTTP/1.1 403 Forbidden
{"detail":"Invalid API key."}

$ curl -i -X POST http://localhost:8000/ask -H "X-API-Key: secret-key-123" -H "Content-Type: application/json" -d '{"question":"Hello"}'
HTTP/1.1 200 OK
{"question":"Hello","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

### Exercise 4.2: JWT (`04-api-gateway/production/`)

Luồng:

1. Gửi username/password tới `POST /auth/token` (`app.py` dòng 105–118); `authenticate_user` kiểm tra (`auth.py` dòng 70–75).
2. `create_token` ký token HS256 chứa `sub`, `role`, `iat`, `exp`, hết hạn sau 60 phút (`auth.py` dòng 35–43).
3. Client gửi `Authorization: Bearer <TOKEN>`; `verify_token` kiểm tra chữ ký và hạn (`auth.py` dòng 46–67), không cần tra database.

Đường dẫn đúng là `/auth/token` với `student` / `demo123`; `/token` như trong `CODE_LAB.md` trả 404.

Khởi động app (tắt bản develop trước) và lưu token vào biến `TOKEN`:

```bash
cd 04-api-gateway/production
pip install -r requirements.txt
python app.py
# ở terminal khác:
TOKEN=$(curl -s -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username":"student","password":"demo123"}' \
  | python -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')
```

```text
$ curl -i -X POST http://localhost:8000/auth/token -H "Content-Type: application/json" -d '{"username":"student","password":"demo123"}'
HTTP/1.1 200 OK
{"access_token":"<TOKEN>","token_type":"bearer","expires_in_minutes":60,"hint":"Include in header: Authorization: Bearer <TOKEN>"}

$ curl -i -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{"question":"Explain JWT"}'
HTTP/1.1 401 Unauthorized
www-authenticate: Bearer
{"detail":"Authentication required. Include: Authorization: Bearer <token>"}

$ curl -i -X POST http://localhost:8000/ask -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"question":"Explain JWT"}'
HTTP/1.1 200 OK
x-content-type-options: nosniff
x-frame-options: DENY
{"question":"Explain JWT","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic.","usage":{"requests_remaining":9,"budget_remaining_usd":2.1e-05}}
```

| Trường hợp khác | Kết quả |
|---|---|
| Sai mật khẩu | 401 `Invalid credentials` |
| Token bịa (`abc.def.ghi`) | 403 `Invalid token.` |
| Token hết hạn | 401 `Token expired. Please login again.` |
| Câu hỏi rỗng hoặc 1001 ký tự | 422 |
| `student` gọi `/admin/stats` | 403 |
| Token role `admin` tự ký bằng secret mặc định, gọi `/admin/stats` (thử trên máy local) | **200** |

Dòng cuối cho thấy lỗ hổng: `JWT_SECRET` có giá trị mặc định nằm trong code (`auth.py` dòng 22). Ai đọc được code đều tự tạo được token admin nếu server không đặt biến này. Cần bắt buộc đặt `JWT_SECRET` và không để mặc định.

### Exercise 4.3: Rate limiting (`rate_limiter.py`)

- **Thuật toán:** sliding window 60 giây. Mỗi user có một `deque` chứa thời điểm các request; xoá mốc cũ rồi đếm (dòng 29–65). Ghi chú gọi là "Sliding Window Counter", nhưng do lưu từng timestamp nên đúng ra là *sliding window log*.
- **Giới hạn:** user 10 request/phút, admin 100 request/phút (dòng 86–87).
- **Admin:** không bỏ qua hẳn limit; `app.py` dòng 141 chọn limiter theo `role`, nên `teacher` được mức 100.

Vòng lặp (khởi động lại app trước đó để bộ đếm bằng 0):

```bash
for i in $(seq 1 20); do
  printf 'Request %2d: ' $i
  curl -s -o /dev/null -w '%{http_code}\n' -X POST http://localhost:8000/ask \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d "{\"question\":\"Test $i\"}"
done
```

```text
Request  1: 200
Request  2: 200
Request  3: 200
Request  4: 200
Request  5: 200
Request  6: 200
Request  7: 200
Request  8: 200
Request  9: 200
Request 10: 200
Request 11: 429
Request 12: 429
Request 13: 429
Request 14: 429
Request 15: 429
Request 16: 429
Request 17: 429
Request 18: 429
Request 19: 429
Request 20: 429
```

```text
$ curl -i -X POST http://localhost:8000/ask -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"question":"Test 21"}'
HTTP/1.1 429 Too Many Requests
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
x-ratelimit-reset: 1795596333
retry-after: 59
{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
```

- `teacher` gửi 20 request: cả 20 trả 200.
- Khởi động lại app, `student` (token cũ) gọi được ngay (200). Token vẫn dùng được vì JWT không cần lưu ở server, còn bộ đếm bị mất vì nằm trong RAM. Chạy nhiều instance thì mỗi instance đếm riêng, nên production cần lưu trong Redis.

### Exercise 4.4: Cost guard

**Bản mẫu (`cost_guard.py`):** ngân sách $1/ngày mỗi user và $10/ngày toàn hệ thống (dòng 128). Kiểm tra trước khi gọi LLM (`app.py` dòng 145), ghi chi phí theo token sau khi gọi (dòng 153). Thử với ngân sách $0.001: vượt mức user trả **402**, vượt mức toàn cục trả **503**.

Hạn chế: lưu trong RAM (restart là mất, mỗi instance tính riêng); kiểm tra trước và cộng sau nên request có thể vượt ngân sách; trường `budget_remaining_usd` của `/ask` thực ra là số **đã dùng** (`app.py` dòng 160).

**Cách làm theo đề ($10/tháng mỗi user, lưu trong Redis):**

```python
import os
from datetime import datetime, timezone

import redis

MONTHLY_BUDGET_USD = 10.0
KEY_TTL_SECONDS = 32 * 24 * 3600

# Kiểm tra và cộng tiền trong cùng một bước (Redis chạy script Lua nguyên khối)
RESERVE = """
local spent = tonumber(redis.call('GET', KEYS[1]) or '0')
if spent + tonumber(ARGV[1]) > tonumber(ARGV[2]) then
  return 0
end
redis.call('INCRBYFLOAT', KEYS[1], ARGV[1])
redis.call('EXPIRE', KEYS[1], ARGV[3])
return 1
"""

r = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))


def budget_key(user_id: str, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return f"budget:{user_id}:{now:%Y-%m}"


def check_budget(user_id: str, estimated_cost: float) -> bool:
    """True nếu còn ngân sách (đã giữ chỗ khoản chi), False nếu sẽ vượt."""
    if estimated_cost < 0:
        raise ValueError("estimated_cost must be >= 0")
    allowed = r.eval(RESERVE, 1, budget_key(user_id), estimated_cost,
                     MONTHLY_BUDGET_USD, KEY_TTL_SECONDS)
    return allowed == 1
```

- **Theo user và theo tháng:** key `budget:<user>:<YYYY-MM>`. Sang tháng mới là key mới, nên ngân sách tự reset.
- **TTL 32 ngày:** key cũ tự bị xoá.
- **Không bị race:** đọc, so sánh và cộng nằm trong một script Lua, Redis chạy nguyên khối. Nếu `GET` rồi `INCRBYFLOAT` thành hai lệnh riêng, nhiều request đồng thời có thể cùng vượt qua bước kiểm tra.
- **Nhiều instance:** mọi instance dùng chung một Redis; restart app không mất số đã chi.
- **Giới hạn còn lại:** trừ theo chi phí ước tính, chưa điều chỉnh theo chi phí thật sau khi gọi LLM. Redis lỗi thì hàm ném exception, request không được cho qua; app cần bắt lỗi để trả mã phù hợp.

Kết quả kiểm thử với Redis 7:

```text
6.0 USD            -> True
them 4.0 (tong 10) -> True
them 0.01          -> False
user khac 0.01     -> True
da chi u1          -> 10.0
TTL (giay)         -> 2764800
key thang sau      -> budget:u1:2026-12
200 request dong thoi, 0.5 USD/request -> cho qua 20 | tong chi 10.0
chi phi am         -> ValueError: estimated_cost must be >= 0
```

**Vì sao cần cả hai:** rate limit bảo vệ **tốc độ** (chặn gọi dồn dập), cost guard bảo vệ **tiền** (ít request nhưng rất dài vẫn có thể tốn nhiều).

## Part 5: Scaling & Reliability

### Exercise 5.1: Health checks (`05-scaling-reliability/develop/app.py`)

| Endpoint | Câu hỏi | Cách làm trong code | Khi lỗi thì |
|---|---|---|---|
| `GET /health` (liveness) | Tiến trình còn sống không? | Dòng 104–144: trả uptime, version, kiểm tra bộ nhớ bằng `psutil` | Nền tảng khởi động lại container |
| `GET /ready` (readiness) | Nhận request được chưa? | Dòng 147–168: trả 503 khi cờ `_is_ready` là `False` (đang khởi động hoặc đang tắt) | Load balancer ngừng gửi traffic, không restart |

```text
$ curl -i http://localhost:8000/health
HTTP/1.1 200 OK
{"status":"ok","uptime_seconds":0.9,"version":"1.0.0","environment":"development","timestamp":"2026-11-25T08:49:17.792769+00:00","checks":{"memory":{"status":"ok","used_percent":46.4}}}

$ curl -i http://localhost:8000/ready
HTTP/1.1 200 OK
{"ready":true,"in_flight_requests":1}
```

`in_flight_requests` là 1 vì chính request `/ready` cũng được middleware đếm (dòng 72–81).

Bản production kiểm tra thêm Redis (`production/app.py` dòng 187–215). Dừng Redis rồi gọi trực tiếp một agent:

```text
/health 200 {"status":"degraded", ... "redis_connected":false}
/ready  503 {"detail":"Redis not available"}
```

`/health` vẫn 200 vì tiến trình còn sống, restart agent không sửa được Redis. `/ready` trả 503 để không nhận traffic. Khi gọi qua Nginx, một lần chạy nhận 503, một lần khác nhận 502 (chưa xác định nguyên nhân). Bật lại Redis thì `/ready` trả 200.

### Exercise 5.2: Graceful shutdown

Cách làm trong `develop/app.py`:

1. Nhận SIGTERM, uvicorn ngừng nhận kết nối mới.
2. Chờ request đang xử lý xong, tối đa 30 giây (`timeout_graceful_shutdown=30`, dòng 198).
3. Chạy phần shutdown của `lifespan` (dòng 53–66): đặt `_is_ready = False`, chờ bộ đếm in-flight về 0.
4. Thoát. `handle_sigterm` (dòng 175–187) chỉ ghi log.

Thử nghiệm: gửi `POST /ask` (mock xử lý 3 giây), 0.5 giây sau gửi tín hiệu.

| Tín hiệu | Request đang chạy | Kết quả request | Exit code |
|---|---|---|---|
| SIGTERM | 1 | 200 sau 3.05 giây | 0 |
| SIGTERM | 2 | cả hai 200 sau 6.08 giây | 0 |
| SIGKILL | 1 | mất kết nối (`RemoteDisconnected`) sau 0.51 giây | -9 |

```text
INFO:     Shutting down
INFO:     127.0.0.1:55406 - "POST /ask?question=hello HTTP/1.1" 200 OK
INFO:     Waiting for application shutdown.
INFO 🔄 Graceful shutdown initiated...
INFO ✅ Shutdown complete
INFO:     Application shutdown complete.
INFO:     Finished server process [20014]
INFO Received signal 15 — uvicorn will handle graceful shutdown
```

Những điều quan sát được:

- SIGTERM cho phép làm xong việc dở; SIGKILL không bắt được nên request bị mất.
- Gọi `/ready` sau khi gửi tín hiệu không nhận được 503 mà bị lỗi kết nối. Dòng log "Waiting for ... in-flight requests" cũng không xuất hiện, vì uvicorn đã chờ xong request trước khi gọi phần shutdown của `lifespan`.
- `ask_agent` là `async def` nhưng gọi `time.sleep` (qua mock LLM), nên chặn event loop: 2 request chạy lần lượt (6 giây thay vì 3), và `/health` gọi lúc đang có request mất 2.71 giây. Nên dùng `def` hoặc lời gọi bất đồng bộ.

### Exercise 5.3: Stateless design (`production/app.py`)

**Anti-pattern:** lưu hội thoại trong biến của tiến trình, ví dụ `conversation_history = {}`. Mỗi instance có RAM riêng, nên request sau rơi vào instance khác sẽ không thấy lịch sử, và restart là mất.

**Cách đúng trong code:**

- `save_session` / `load_session` (dòng 59–73) ghi và đọc key `session:<id>` trong Redis, TTL 1 giờ.
- `append_to_history` (dòng 76–90) giữ tối đa 20 message.
- `POST /chat` (dòng 128–157) nhận `session_id`, nên instance nào cũng phục vụ tiếp được. Trường `served_by` cho biết instance nào trả lời.

Hạn chế tìm được khi thử:

- Không kết nối được Redis lúc khởi động thì app **âm thầm chuyển sang lưu trong RAM** (dòng 35–45). Chạy image không có Redis: `/health` trả 200 `"status":"ok","storage":"in-memory"` và `/ready` trả 200. Production nên báo chưa sẵn sàng trong trường hợp này.
- `append_to_history` đọc, sửa rồi ghi cả session, không nguyên tử. Gửi 8 request đồng thời vào cùng session (sau 1 request mở đầu), 3 lần thử được **17, 16, 18** message thay vì 18. Nên dùng `RPUSH` + `LTRIM` hoặc transaction.
- Trường `turn` lệch 1: request đầu tiên trả `"turn": 2` (dòng 154).

### Exercise 5.4: Load balancing

```bash
cd 05-scaling-reliability/production
touch .env.local
docker compose -p k5-day14-scaling up -d --build --scale agent=3
```

```text
NAME                       SERVICE   STATUS         PORTS
k5-day14-scaling-agent-1   agent     Up (healthy)   8000/tcp
k5-day14-scaling-agent-2   agent     Up (healthy)   8000/tcp
k5-day14-scaling-agent-3   agent     Up (healthy)   8000/tcp
k5-day14-scaling-nginx-1   nginx     Up             0.0.0.0:8080->80/tcp
k5-day14-scaling-redis-1   redis     Up (healthy)   6379/tcp
```

Chỉ Nginx mở cổng (8080). `server agent:8000` (`nginx.conf` dòng 7–11) được Docker DNS phân giải ra 3 địa chỉ. Gửi 12 request `POST /chat` liên tiếp:

```text
instance-47e844: 4    instance-859d33: 4    instance-bd465a: 4
```

Traffic được chia đều theo round-robin. Response có header `X-Served-By: 172.21.0.3:8000`. Endpoint là `POST /chat` ở cổng 8080, không phải `/ask` ở cổng 80 như trong `CODE_LAB.md`.

### Exercise 5.5: Test stateless

`python test_stateless.py`:

```text
Request 1: [instance-bd465a]
Request 2: [instance-859d33]
Request 3: [instance-47e844]
Request 4: [instance-bd465a]
Request 5: [instance-859d33]
Instances used: {'instance-47e844', 'instance-bd465a', 'instance-859d33'}
✅ All requests served despite different instances!
Total messages: 10
✅ Session history preserved across all instances via Redis!
```

**Giải thích:** 5 request được 3 instance khác nhau xử lý nhưng lịch sử vẫn đủ 10 message (5 hỏi, 5 đáp), vì state nằm trong Redis. Script không tự tắt instance nào, nên phần đó được thử riêng.

**Tắt một instance** (`docker kill k5-day14-scaling-agent-2`), rồi gửi 6 request cùng session:

| Cấu hình Nginx | Kết quả | Lịch sử |
|---|---|---|
| Nguyên bản | 4 request 200, **2 request không phản hồi sau 20 giây** | 4 → 12 message: lịch sử cũ còn nguyên, 4 request thành công được lưu |
| Thêm `proxy_connect_timeout 2s;` (thử trên bản sao, gửi 10 request) | 10/10 request 200, một request mất 2.13 giây | Đủ 20 message (mức tối đa) |

Stateless giúp **không mất dữ liệu** khi một instance chết, nhưng chưa đủ để **không gián đoạn**: Nginx vẫn gửi request tới địa chỉ đã chết và chờ kết nối quá lâu. Đặt timeout kết nối ngắn thì Nginx chuyển sang instance khác nhanh.

Dọn dẹp: `docker compose -p k5-day14-scaling down`.

## Part 6: Final Project (`06-lab-complete/`)

### Output `python check_production_ready.py` (chạy đầy đủ, có Docker)

```text
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 43/43 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
```

### Cách hoạt động

`POST /ask`: API key (401) → kiểm tra input (422) → rate limit (429) → budget (402) → gọi LLM → ghi chi phí.

| Thành phần | Cách làm |
|---|---|
| Cấu hình (`config.py`) | Đọc từ biến môi trường; `ENVIRONMENT=production` mà thiếu `AGENT_API_KEY` thì không khởi động |
| Auth (`auth.py`) | Header `X-API-Key`, so sánh bằng `secrets.compare_digest`; thiếu hoặc sai đều trả 401 |
| Rate limit (`rate_limiter.py`) | Sliding window 60 giây bằng sorted set trong Redis, chạy trong một script Lua; Redis chỉ lưu hash của key |
| Cost guard (`cost_guard.py`) | Cộng chi phí vào key `cost:<ngày UTC>`; đạt `DAILY_BUDGET_USD` thì trả 402 |
| Health / Ready | `/health` không phụ thuộc Redis; `/ready` trả 503 khi không ping được Redis |
| Xử lý lỗi (`main.py`) | 422 không lặp lại dữ liệu client gửi; Redis lỗi trả 503; lỗi khác trả 500, stack trace chỉ nằm trong log |
| Log | Mỗi dòng log của app là một JSON object |
| Shutdown | uvicorn xử lý SIGTERM, chờ request đang chạy (tối đa 8 giây), `lifespan` đóng kết nối Redis |
| Docker | Multi-stage, `python:3.11-slim`, user `app`, `HEALTHCHECK`, uvicorn là PID 1 |

### Thử thêm trên Docker Compose

| Trường hợp | Kết quả |
|---|---|
| Thiếu key, sai key, key có ký tự ngoài ASCII | 401 |
| Câu hỏi thiếu, rỗng, toàn khoảng trắng, sai kiểu, 2001 ký tự | 422 |
| JSON hỏng, `NaN`, body là mảng | 422 |
| Body không phải UTF-8 | 400 |
| `GET /ask`, đường dẫn không tồn tại | 405, 404 |
| 30 request đồng thời, giới hạn 10/phút | đúng 10 request 200, 20 request 429, có `Retry-After` |
| Dừng Redis | `/health` 200, `/ready` 503, `/ask` 503; bật lại thì `/ready` 200 |
| Log container | không có traceback, không chứa API key |
| `docker stop` | exit code 0 |

Image build bằng Compose: 193 MB theo `docker images`; script chấm đo 184 MB.

Hạn chế: cost guard kiểm tra trước rồi mới cộng chi phí, nên nhiều request đồng thời có thể vượt ngân sách một ít.

## AI log

| Hỏi gì | Nhận gì | Tôi tự sửa và kiểm tra thế nào |
|--------|---------|--------------------------------|
| Nhờ AI (Claude Code) hỗ trợ tìm hiểu CP1 | AI hỗ trợ giải thích yêu cầu và các bước làm | Tôi làm theo hướng dẫn để chạy lại bản production và đối chiếu code |
| Nhờ AI hỗ trợ CP1 | AI hỗ trợ kiểm thử hai app và soạn bản nháp Part 1 | Tôi tự chạy bản production: `/ask`, `/health`, `/ready` đều trả 200; đã đối chiếu `develop/app.py` với bảng anti-pattern |
| Nhờ AI hỗ trợ CP2 | AI hỗ trợ build, kiểm thử Docker và soạn bản nháp Part 2 | Tôi tự chạy Compose stack theo hướng dẫn của Claude Code: 4 service chạy (agent, redis, qdrant healthy), hai request qua Nginx đều trả 200, sau đó dọn stack |
| Nhờ AI hỗ trợ CP3 | AI hỗ trợ kiểm thử, viết hàm cost guard và soạn bản nháp Part 4 | Tôi tự chạy lại vòng lặp curl của Exercise 4.3 theo hướng dẫn của Claude Code: request 1–10 trả 200, request 11–20 trả 429 |
| Nhờ AI hỗ trợ CP4 | AI hỗ trợ kiểm thử và soạn bản nháp Part 5 | Tôi tự chạy stack 3 agent và `test_stateless.py` theo hướng dẫn của Claude Code: 5 request do 3 instance xử lý, lịch sử đủ 10 message, sau đó tắt stack |
| Nhờ AI hỗ trợ CP5 | AI hỗ trợ viết code trong `06-lab-complete/`, kiểm thử và soạn bản nháp Part 6 | Tôi tự chạy `python check_production_ready.py` (đầy đủ, có Docker): PASS 12/12, 43/43 checks, image 184 MB |
