# Benchmark & Observability Report — Day 14

> Copy file này thành `BENCHMARK_REPORT.md` trong repo của bạn và điền đầy đủ.
> Mọi con số phải lấy từ report JSON / CSV / screenshot thật, không ước lượng.

**Họ tên:** Nguyễn Vũ Thành Long
**Ngày chạy:** 2026-11-25 (mục 1–3)
**Môi trường:** MacBook Apple M1 Max (10 CPU, 64 GB RAM), macOS 26.6.2, Python 3.11.18. Mục 2–3: agent và công cụ đo chạy trực tiếp trên cùng máy, không dùng Docker.

---

## 1. SLO của agent

| SLI                          | SLO      | Lý do chọn ngưỡng này                                                                                                                     |
| ---------------------------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| p95 latency `/ask`           | < 500 ms | Khi tải vừa, p95 đo được khoảng 220.0 ms, nên 500 ms còn chỗ cho dao động nhưng vẫn bắt được trường hợp nhiều request bị chậm (~1,7 giây) |
| Error rate `/ask`            | < 2 %    | Mock LLM mặc định lỗi khoảng 1 %; ngưỡng 2 % cho phép dao động ngẫu nhiên và báo khi lỗi tăng gấp đôi                                     |
| Accuracy trên golden dataset | ≥ 85 %   | Trên 23 câu cho phép sai tối đa 3 câu; thấp hơn là chất lượng giảm rõ. Kèm điều kiện không có regression                                  |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

Mỗi mức chạy 300 request vào agent v2. Report: `reports/load_v2_*.json`.

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS    | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO        |
| ----------- | ------ | -------- | -------- | -------- | ---------- | ---------- |
| 1           | 3.75   | 193.4    | 516.2    | 1704.6   | 1.00%      | FAIL (p95) |
| 10          | 42.65  | 193.9    | 220.0    | 1703.7   | 1.67%      | PASS       |
| 50          | 107.95 | 195.0    | 236.3    | 1699.5   | 1.33%      | PASS       |
| 100         | 46.15  | 383.0    | 4236.6   | 4751.2   | 1.00%      | FAIL (p95) |

**Nhận xét:** RPS **không** tăng tuyến tính.

- Từ 1 lên 10, RPS tăng từ 3.75 lên 42.65: agent dùng `async`, nên trong lúc chờ LLM vẫn nhận request khác.
- Từ 10 lên 50 (gấp 5), RPS chỉ lên 107.95 (khoảng 2.5 lần). Với 300 request, đợt chạy quá ngắn nên vài request chậm 1,7 giây chi phối tổng thời gian. Chạy lại 2000 request ở mức 50 được 189.93 RPS.
- Ở mức 100, RPS giảm còn 46.15 và p95 lên 4236.6 ms.
- p95 vượt SLO ở mức 1 là do trong lần chạy đó tỉ lệ request chậm hơi quá 5 % (15/297), đẩy p95 rơi vào nhóm chậm (516.2 ms).

**Điểm nghẽn ở mức 100 nằm ở phía tạo tải.** So sánh p95 client đo với p95 server đo từ log (`reports/extra/server_side_latency.json`):

| Concurrency | p95 client (ms) | p95 server (ms) | Request > 1 giây (server) |
| ----------- | --------------- | --------------- | ------------------------- |
| 1           | 516.2           | 227.0           | 15/297                    |
| 10          | 220.0           | 217.1           | 8/295                     |
| 50          | 236.3           | 215.2           | 5/296                     |
| 100         | 4236.6          | 239.3           | 11/297                    |

| Thử đối chiếu (file trong `reports/extra/`)                               | RPS    | p95 (ms) | Error rate |
| ------------------------------------------------------------------------- | ------ | -------- | ---------- |
| 1 tiến trình, 100 đồng thời, 300 request (lặp lại)                        | 52.63  | 3543.5   | 0.33%      |
| 1 tiến trình, 100 đồng thời, 2000 request                                 | 58.56  | 4987.9   | 0.90%      |
| Như trên, tăng `max_keepalive_connections` lên 100 (bản sao script)       | 58.69  | 5062.4   | 1.00%      |
| 2 tiến trình chạy cùng lúc, mỗi tiến trình 50, 1000 request: tiến trình 1 | 167.68 | 226.0    | 0.40%      |
| 2 tiến trình chạy cùng lúc: tiến trình 2                                  | 165.26 | 226.9    | 0.90%      |

Cùng tổng 100 request đồng thời, chia cho 2 tiến trình thì tổng RPS khoảng 333 và p95 vẫn thấp. Vì vậy con số ở mức 100 chủ yếu phản ánh giới hạn của một tiến trình `load_test.py`, không phải của agent. Chưa profile để biết chính xác phần nào trong client gây chậm. Latency server đo trong middleware cũng không gồm thời gian chờ trước khi request vào ứng dụng.

### 2.2 Tail latency

Mỗi mức: 300 request, concurrency 20.

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
| ---------------- | -------- | -------- | -------- |
| 0                | 190.8    | 219.4    | 230.6    |
| 0.03 (mặc định)  | 237.1    | 221.9    | 1703.4   |
| 0.1              | 349.3    | 1690.7   | 1714.6   |

**Nhận xét:** Chỉ số nào nhạy nhất với request chậm? Vì sao SLO không nên đặt theo average?

- **p99 nhạy nhất:** từ 0 lên 0.03, avg chỉ tăng 46.3 ms, p95 gần như không đổi (+2.5 ms), còn p99 tăng 1472.8 ms.
- Khi tỉ lệ chậm là 0.1 (hơn 5 %), p95 cũng nhảy lên (+1471.3 ms) trong khi avg chỉ tăng 158.5 ms.
- **Average che giấu nhóm người dùng bị chậm:** ở mức 0.1, avg 349.3 ms vẫn dưới 500 ms dù khoảng 1/10 request chờ gần 1,7 giây. SLO theo p95 hoặc p99 mới phản ánh trải nghiệm này.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số                | Agent v1          | Agent v2                     | Agent v2 (sau khi sửa KB)     |
| --------------------- | ----------------- | ---------------------------- | ----------------------------- |
| Accuracy              | 4.3% (1/23)       | 91.3% (21/23)                | 100.0% (23/23)                |
| Avg tokens / câu      | 57.7              | 109.1                        | 113.9                         |
| Tổng cost (USD)       | 0.000413          | 0.000762                     | 0.000792                      |
| Cost / câu đúng (USD) | 0.00041295        | 0.00003627                   | 0.00003445                    |
| Quality gate          | FAIL (ngưỡng 80%) | PASS (ngưỡng 80%, so với v1) | PASS (ngưỡng 100%, so với v2) |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID          | Keyword bị thiếu            | Bạn đã sửa gì                                                                                  |
| ----------- | --------------------------- | ---------------------------------------------------------------------------------------------- |
| security-02 | token, hết hạn, chữ ký      | Thêm tài liệu về JWT (token, thời điểm hết hạn, chữ ký số) với từ khoá `jwt`                   |
| scaling-03  | cpu, memory, custom metrics | Thêm tài liệu về HPA (CPU, memory, custom metrics) với từ khoá `hpa`, `kubernetes`, `autoscal` |

Sửa trong `develop/utils/mock_llm.py` (`KNOWLEDGE_BASE`), chép sang bản `production/`. Không sửa `golden_dataset.jsonl`. Sau khi sửa: 23/23 và không có regression.

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**

- **Chất lượng:** v2 đạt 91.3% (21/23) so với 4.3% (1/23) của v1.
- **Chi phí:** v2 dùng khoảng 1.9 lần token mỗi câu và tổng cost cao hơn 1.8 lần, nhưng **cost trên mỗi câu đúng rẻ hơn khoảng 11.4 lần**. So theo "cost / câu" thì v1 trông rẻ hơn dù phần lớn câu trả lời sai.
- **Latency:** p50 trong eval là 174.8 ms (v1) và 196.3 ms (v2), khớp với bước retrieval khoảng 20 ms. p95 của eval không dùng để kết luận vì chỉ có 23 mẫu, một request chậm đã làm p95 nhảy.

### Quality gate trong CI

`run_eval.py` trả **exit code 1** khi accuracy dưới `--min-accuracy` hoặc có regression so với `--baseline`. Trong CI, lệnh trả exit code khác 0 làm job thất bại; đặt job này làm _required status check_ của nhánh `main` thì pull request không merge được.

| Chạy thử trên máy                                                      | Exit code |
| ---------------------------------------------------------------------- | --------- |
| v2 đã sửa, `--min-accuracy 1.0`, so với `eval_v2.json`                 | 0         |
| v1, `--min-accuracy 0.85`, so với `eval_v2_fixed.json` (22 regression) | 1         |

Job GitHub Actions (đặt tại `.github/workflows/eval.yml`):

```yaml
name: quality-gate
on: [pull_request]
jobs:
  eval:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: 06-lab-complete/benchmark-observability/develop
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt
      - name: Start agent and run eval
        run: |
          AGENT_VERSION=v2 PORT=8000 MOCK_ERROR_RATE=0 python app.py &
          curl --silent --retry 30 --retry-delay 1 --retry-all-errors --output /dev/null http://localhost:8000/health
          python eval/run_eval.py --url http://localhost:8000 --min-accuracy 0.85 \
            --baseline reports/eval_v2_fixed.json
```

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [ ] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals)
- [ ] Một trace chậm trong Jaeger (thấy span nào chiếm thời gian)
- [ ] Một trace lỗi trong Jaeger (có event `exception`)
- [ ] Trang Alerts của Prometheus với ít nhất 1 alert đang **firing**

### 4.2 Thí nghiệm "phá hệ thống"

| #   | Thay đổi                   | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
| --- | -------------------------- | ---------------- | ----------------------------- | -------------------------- |
| A   | `MOCK_ERROR_RATE=0.2`      |                  |                               |                            |
| B   | `MOCK_SLOW_RATE=0.3`       |                  |                               |                            |
| C   | `LLM_MODEL=mock-llm-large` |                  |                               |                            |
| D   | `docker pause` 1 instance  |                  |                               |                            |
| E   | `AGENT_VERSION=v1`         |                  |                               |                            |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

...

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất bạn tìm được:

- `trace_id`: ...
- Tổng thời gian: ... ms
- Span chiếm nhiều thời gian nhất: ... (... ms, ...%)
- Dòng log tương ứng (grep theo `trace_id`):

```json

```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
| ----------- | --- | -------- | -------- | -------- | -------- |
| 1           |     |          |          |          |          |
| 3           |     |          |          |          |          |

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?

...

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. ...
  2. ...
  3. ...
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?

...

---

## Phụ lục: Exercise 7.1 (metrics của agent)

Lấy từ `GET /metrics` sau 1 request `/ask` và 4 request tới URL không tồn tại:

| Loại      | Ví dụ                                                                                | Đặc điểm                                   |
| --------- | ------------------------------------------------------------------------------------ | ------------------------------------------ |
| Counter   | `http_requests_total{method="POST",route="/ask",status="200"} 1.0`                   | Chỉ tăng, dùng với `rate()`                |
| Gauge     | `agent_in_flight_requests 0.0`                                                       | Lên xuống                                  |
| Histogram | `agent_question_length_chars_bucket{le="50.0"} 1.0`, `..._sum 40.0`, `..._count 1.0` | Chia giá trị vào bucket để tính percentile |

**Vì sao dùng `route.path`:** 4 URL lạ (`/wp-admin`, `/.env`, `/a1b2c3`, `/xyz123`) được gộp thành một series `http_requests_total{method="GET",route="unmatched",status="404"} 4.0`. Nếu dùng `request.url.path`, mỗi URL bot quét tạo một series mới, số series tăng không giới hạn và Prometheus tốn RAM.

**Metric mới:** `agent_question_length_chars` là Histogram, ghi trong `ask()` ở `develop/app.py`. Không đưa độ dài vào label vì có quá nhiều giá trị khác nhau.
