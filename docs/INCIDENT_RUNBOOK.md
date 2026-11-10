# Production incident runbook

Runbook này dành cho backend FastAPI/Gunicorn trên aaPanel. Không đưa `.env`, token,
prompt, nội dung chat hoặc SQL parameters vào ticket/log hỗ trợ.

## 1. Triage và containment

1. Ghi thời điểm, commit đang chạy và phạm vi ảnh hưởng; ưu tiên bảo toàn dữ liệu.
2. Kiểm tra liveness/readiness trước khi restart:

```bash
date -Is
cd /www/wwwroot/dental-ai && git rev-parse HEAD
curl -i http://127.0.0.1:8001/health
curl -i http://127.0.0.1:8001/ready
ps -ef | grep '[g]unicorn.*api.main:app'
ss -lntp | grep ':8001'
free -h; df -h
```

3. Lưu phần log liên quan, không copy toàn bộ file nếu có thể chứa dữ liệu người dùng:

```bash
tail -n 300 /www/wwwlogs/python/dental-ai/gunicorn_error.log
tail -n 300 /www/wwwlogs/python/dental-ai/chat.log
journalctl -u nginx --since '-30 min' --no-pager
```

## 2. Chẩn đoán theo readiness

- `database=unavailable`: kiểm tra MySQL, disk, connection limit và tài khoản ứng dụng.
- `retriever=unavailable`: xác nhận engine, quyền đọc, checksum và cặp FAISS/metadata.
- `integrity=mismatch`: index và metadata khác phiên bản; thay cả cặp artifact, không thay một file.
- `chatbot=unavailable`: kiểm tra provider timeout/rate limit/auth; không in API key.

```bash
mysqladmin -h 127.0.0.1 -u dental_ai -p ping
mysql -h 127.0.0.1 -u dental_ai -p -e 'SELECT 1' dental_agent_db
sha256sum data/vector_db/$EMBEDDING_ENGINE/faiss.index data/vector_db/$EMBEDDING_ENGINE/metadata.json
nginx -t
```

## 3. Recovery và rollback

Restart một lần sau khi đã thu thập bằng chứng. Nếu lỗi xuất hiện ngay sau deploy, rollback
về commit tốt đã ghi trước đó và đồng bộ dependency theo lockfile. Không downgrade database
mù quáng; kiểm tra revision và migration downgrade trước.

```bash
cd /www/wwwroot/dental-ai
alembic current
git switch --detach REPLACE_WITH_KNOWN_GOOD_COMMIT
uv sync --frozen --no-dev
python -m compileall -q api src
```

Restart trong aaPanel, rồi kiểm tra `/health`, `/ready` và smoke test trong tài liệu deploy.
Chỉ restore MySQL khi code rollback không tương thích schema/data; trước restore phải backup
trạng thái hiện tại và kiểm tra file dump khác rỗng.

## 4. Sau sự cố

- Ghi timeline, nguyên nhân gốc, tác động, cách phát hiện và hành động phòng ngừa.
- Rotate secret nếu có khả năng bị lộ; không ghi giá trị secret vào postmortem.
- Xác nhận log rotation, backup, dependency scan và alert cho `/health`/`/ready`.
- Thực hiện restore drill định kỳ trên database test, không thử restore trực tiếp vào production.
