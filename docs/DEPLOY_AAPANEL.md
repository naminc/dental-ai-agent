# Deploy Dental AI backend trên aaPanel

Backend chạy tại `/www/wwwroot/dental-ai`, chỉ lắng nghe nội bộ ở `127.0.0.1:8001` và nhận traffic công khai qua Nginx. ASGI application là `api.main:app`, process chạy bằng user `www` và bắt đầu với một worker.

## 1. Chuẩn bị source và thư mục

```bash
mkdir -p /www/wwwroot/dental-ai
mkdir -p /www/wwwlogs/python/dental-ai
chown -R www:www /www/wwwroot/dental-ai
chown -R www:www /www/wwwlogs/python/dental-ai
```

Đưa source vào `/www/wwwroot/dental-ai`. Không upload `.venv`, `.env`, `.next`, `node_modules`, log hoặc cache từ máy phát triển.

```bash
cd /www/wwwroot/dental-ai
test -f api/main.py
test -f gunicorn_conf.py
git status --short
```

FAISS artifacts đang bị Git ignore nên phải upload riêng hoặc chạy pipeline ingest. Kiểm tra theo embedding engine đang dùng:

```bash
test -f data/vector_db/openai/faiss.index
test -f data/vector_db/openai/metadata.json
```

Nếu dùng `EMBEDDING_ENGINE=local`, thay `openai` bằng `local` trong hai đường dẫn trên.

## 2. Tạo Python environment

Có thể tạo environment tại **Website → Python Project → Environment Management**, chọn Python 3.11, rồi mở Terminal của environment đó.

Nếu tạo bằng command line:

```bash
cd /www/wwwroot/dental-ai
python3.11 -m venv .venv
source .venv/bin/activate
python --version
python -m pip install --upgrade pip setuptools wheel
```

Mọi lệnh Python tiếp theo phải chạy trong cùng environment mà aaPanel dùng để start project.

## 3. Cài dependencies

Ưu tiên cài đúng lockfile bằng uv:

```bash
cd /www/wwwroot/dental-ai
python3.11 -m pip install uv
uv sync --frozen --no-dev
uv run --frozen --no-dev python -c "import fastapi, gunicorn, uvicorn, pymysql, faiss; print('dependencies OK')"
uv run --frozen --no-dev python -c "import api.main; print('application import OK')"
```

Nếu aaPanel chỉ hỗ trợ pip, `requirements.txt` là production export đã khóa version:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Với local embedding, dùng `uv sync --frozen --no-dev --extra local-embedding`. Chi tiết tại `docs/DEPENDENCY_MANAGEMENT.md`.

Import application không cần kết nối MySQL, OpenAI hoặc Hugging Face.

## 4. Tạo MySQL database và user

```bash
mysql -u root -p
```

Thay placeholder bằng mật khẩu riêng:

```sql
CREATE DATABASE dental_agent_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE USER 'dental_ai'@'127.0.0.1'
  IDENTIFIED BY 'REPLACE_WITH_A_STRONG_PASSWORD';

GRANT ALL PRIVILEGES ON dental_agent_db.*
  TO 'dental_ai'@'127.0.0.1';

FLUSH PRIVILEGES;
```

```bash
mysql -h 127.0.0.1 -u dental_ai -p -e "SELECT 1;" dental_agent_db
```

Với database mới hoàn toàn, sau khi tạo `.env`, apply toàn bộ schema bằng Alembic:

```bash
cd /www/wwwroot/dental-ai
source .venv/bin/activate
alembic upgrade head
alembic current
```

Không chạy migration trong Gunicorn startup. Nếu production đã có bảng do cơ chế `create_all()` cũ, đọc `docs/DATABASE_MIGRATIONS.md` và chỉ dùng `alembic stamp 0001_initial` sau khi xác nhận schema khớp.

## 5. Cấu hình `.env`

```bash
cd /www/wwwroot/dental-ai
cp .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"
```

Cập nhật `.env` bằng giá trị thật của máy chủ:

```dotenv
APP_ENV=production
CORS_ORIGINS=["https://app.example.com"]

EMBEDDING_ENGINE=openai
LLM_ENGINE=openai
OPENAI_API_KEY=REPLACE_WITH_OPENAI_API_KEY
OPENAI_BASE_URL=
OPENAI_CHAT_MODEL=gpt-4.1-mini
PROVIDER_TIMEOUT_SECONDS=60
PROVIDER_MAX_RETRIES=2

DATABASE_URL=mysql+pymysql://dental_ai:REPLACE_WITH_URL_ENCODED_PASSWORD@127.0.0.1:3306/dental_agent_db
SECRET_KEY=REPLACE_WITH_GENERATED_SECRET
ACCESS_TOKEN_EXPIRE_MINUTES=1440

MULTI_QUERY_EXPANSION=true
TOP_K=10
LOG_FILE=/www/wwwlogs/python/dental-ai/chat.log
```

Nếu mật khẩu database chứa `@`, `:`, `/`, `#`, `%` hoặc ký tự đặc biệt khác, URL-encode phần mật khẩu trước khi đưa vào `DATABASE_URL`.

```bash
chown www:www /www/wwwroot/dental-ai/.env
chmod 600 /www/wwwroot/dental-ai/.env
```

Không commit hoặc gửi nội dung `.env` vào log hỗ trợ.

## 6. Biến môi trường Gunicorn

`gunicorn_conf.py` đọc các biến process sau:

| Biến | Default | Ý nghĩa |
|---|---:|---|
| `APP_DIR` | `/www/wwwroot/dental-ai` | Working directory |
| `HOST` | `127.0.0.1` | Interface nội bộ |
| `PORT` | `8001` | Internal port |
| `WEB_CONCURRENCY` | `1` | Số worker |
| `GUNICORN_TIMEOUT` | `300` | Worker timeout, giây |
| `GUNICORN_GRACEFUL_TIMEOUT` | `300` | Thời gian hoàn tất request/SSE khi restart, giây |
| `LOG_DIR` | `/www/wwwlogs/python/dental-ai` | Thư mục log Gunicorn |

Khai báo các giá trị override trong Environment Variables của aaPanel hoặc môi trường process. `.env` của FastAPI chỉ được đọc sau khi Gunicorn đã load config, nên không dựa vào `.env` để đổi bind port.

Kiểm tra override mà không start application:

```bash
cd /www/wwwroot/dental-ai
PORT=9001 WEB_CONCURRENCY=2 python -c "import runpy; c=runpy.run_path('gunicorn_conf.py'); print(c['bind'], c['workers'])"
```

Kết quả mong đợi: `127.0.0.1:9001 2`.

## 7. Cấu hình project trong aaPanel

Để chắc chắn aaPanel dùng file config trong repository, chọn **Command Startup**:

```bash
/www/wwwroot/dental-ai/.venv/bin/gunicorn -c /www/wwwroot/dental-ai/gunicorn_conf.py api.main:app
```

Thiết lập project:

- Project name: `dental-ai`
- Project path: `/www/wwwroot/dental-ai`
- Python environment: environment Python 3.11 vừa tạo
- Startup user: `www`
- Startup command: lệnh Gunicorn phía trên
- Environment variables: có thể dùng default hoặc khai báo sáu biến ở phần trên

Nếu dùng form Gunicorn thay cho Command Startup, phải bảo đảm aaPanel thực sự truyền `-c /www/wwwroot/dental-ai/gunicorn_conf.py`.

Test trước khi bật service:

```bash
cd /www/wwwroot/dental-ai
source .venv/bin/activate
gunicorn -c gunicorn_conf.py api.main:app
```

Terminal khác:

```bash
curl --fail --show-error http://127.0.0.1:8001/health
curl --include http://127.0.0.1:8001/ready
```

Dừng tiến trình test bằng `Ctrl+C`, sau đó start project trong aaPanel.

## 8. Reverse proxy Nginx

Gắn domain và SSL trong aaPanel, sau đó thêm cấu hình proxy:

```nginx
location / {
    proxy_pass http://127.0.0.1:8001;
    proxy_http_version 1.1;

    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
}
```

Trong `server` HTTPS, bật HSTS sau khi SSL hoạt động đúng trên domain:

```nginx
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
```

```bash
nginx -t
systemctl reload nginx
```

Không mở port 8001 ra Internet; firewall chỉ cần cho phép 80/443. Task này không thay đổi port hoặc URL của frontend.

## 9. Health và readiness

Health chỉ xác nhận web process đang hoạt động:

```bash
curl --fail --show-error http://127.0.0.1:8001/health
```

Kết quả: `{"status":"ok"}`.

Readiness kiểm tra MySQL, retrieval artifacts và cấu hình chatbot mà không gọi OpenAI:

```bash
curl --include http://127.0.0.1:8001/ready
```

- HTTP 200: backend sẵn sàng nhận traffic.
- HTTP 503: đọc `checks.database`, `checks.retriever` và `checks.chatbot` trong response.

Qua domain:

```bash
curl --fail --show-error https://api.example.com/health
curl --include https://api.example.com/ready
```

## 10. Xem log khi service crash

```bash
tail -n 200 /www/wwwlogs/python/dental-ai/gunicorn_error.log
tail -n 200 /www/wwwlogs/python/dental-ai/gunicorn_access.log
tail -n 200 /www/wwwlogs/python/dental-ai/chat.log
```

```bash
tail -F /www/wwwlogs/python/dental-ai/gunicorn_error.log \
        /www/wwwlogs/python/dental-ai/chat.log
```

Application log tự rotate mỗi ngày và giữ 30 bản. Tạo `/etc/logrotate.d/dental-ai-gunicorn`
để hai log Gunicorn không tăng vô hạn:

```text
/www/wwwlogs/python/dental-ai/gunicorn_access.log /www/wwwlogs/python/dental-ai/gunicorn_error.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
}
```

```bash
logrotate --debug /etc/logrotate.d/dental-ai-gunicorn
```

Kiểm tra process và port:

```bash
ps -ef | grep '[g]unicorn.*api.main:app'
ss -lntp | grep ':8001'
```

Lỗi thường gặp:

- `can't chdir`: `APP_DIR` sai hoặc source chưa ở đúng đường dẫn.
- `Address already in use`: port 8001 đang bị process khác chiếm.
- `Permission denied`: user `www` không đọc source/`.env` hoặc không ghi được `LOG_DIR`.
- `/health` 200 nhưng `/ready` 503: thường do MySQL hoặc FAISS artifacts.
- Chat trả 503: xem `chat.log`; request sau sẽ thử lazy initialization lại.

## 11. Restart và deploy bản mới

Trước khi deploy:

```bash
cd /www/wwwroot/dental-ai
git status --short
git rev-parse HEAD
mkdir -p /www/backup
mysqldump -h 127.0.0.1 -u dental_ai -p dental_agent_db > /www/backup/dental_agent_db_before_deploy.sql
test -s /www/backup/dental_agent_db_before_deploy.sql
sha256sum /www/backup/dental_agent_db_before_deploy.sql
```

Ghi lại commit hiện tại để rollback. Không deploy đè lên working tree có thay đổi chưa commit.

```bash
cd /www/wwwroot/dental-ai
git pull --ff-only
uv sync --frozen --no-dev
uv run --frozen --no-dev alembic upgrade head
uv run --frozen --no-dev alembic current
uv run --frozen --no-dev python -m compileall -q api src
uv run --frozen --no-dev python -c "import api.main; print('application import OK')"
```

Restart tại **aaPanel → Website → Python Project → dental-ai → Restart**, sau đó:

```bash
curl --fail --show-error http://127.0.0.1:8001/health
curl --include http://127.0.0.1:8001/ready
```

## 12. Rollback

Thay placeholder bằng commit tốt đã ghi lại trước deploy:

```bash
cd /www/wwwroot/dental-ai
git status --short
git switch --detach REPLACE_WITH_KNOWN_GOOD_COMMIT
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m compileall -q api src
python -c "import api.main; print('rollback import OK')"
```

Restart project trong aaPanel và kiểm tra `/health`, `/ready`.

Chỉ restore database nếu deployment đã thay đổi schema hoặc dữ liệu và rollback code không đủ:

```bash
mysql -h 127.0.0.1 -u dental_ai -p dental_agent_db < /www/backup/dental_agent_db_before_deploy.sql
```

Restore database ghi đè dữ liệu hiện tại. Phải giữ thêm một backup của trạng thái hiện tại và xác nhận đúng file trước khi restore.

## 13. Artifact, security scan và smoke test

Tạo artifact từ file đã commit để không kéo theo `.env`, `.venv`, `.next`, log,
cache hoặc zip cũ:

```bash
git archive --format=tar.gz --output=/tmp/dental-ai-$(git rev-parse --short HEAD).tar.gz HEAD
tar -tzf /tmp/dental-ai-*.tar.gz | grep -E '(^|/)(\.env$|\.venv/|\.next/|logs?/|__pycache__/|\.pytest_cache/)|\.zip$' && exit 1 || true
```

FAISS bị Git ignore nên provision riêng. Ghi checksum của cả hai file và xác nhận
`/ready` trả `integrity: valid` sau deploy.

```bash
sha256sum data/vector_db/$EMBEDDING_ENGINE/faiss.index data/vector_db/$EMBEDDING_ENGINE/metadata.json
uvx pip-audit -r requirements.txt
cd frontend/nextjs-app && npm audit --omit=dev
```

Smoke test không tạo dữ liệu production:

```bash
curl --fail --show-error https://api.example.com/health
curl --fail --show-error https://api.example.com/ready
curl --include https://api.example.com/api/auth/me   # mong đợi 403 nếu thiếu Bearer token
curl --fail --show-error --request OPTIONS https://api.example.com/health \
  --header 'Origin: https://app.example.com' \
  --header 'Access-Control-Request-Method: GET'
curl --silent --show-error https://app.example.com | grep -q '<html'
```

Checklist trước khi chuyển traffic:

- `.env` permission `600`, `SECRET_KEY` tối thiểu 32 ký tự và không dùng lại secret dev.
- `CORS_ORIGINS` chỉ chứa domain frontend HTTPS thật; frontend build dùng đúng `NEXT_PUBLIC_API_URL`.
- Backup MySQL khác rỗng, checksum đã ghi lại và quy trình restore đã được kiểm tra định kỳ.
- `alembic current` ở revision mong đợi; FAISS index/metadata cùng phiên bản và `/ready` trả 200.
- Backend tests, frontend lint/typecheck/build và dependency audit đã chạy.
- Nginx config pass `nginx -t`, SSE buffering tắt, port 8001 không public.
- Health/readiness/smoke test qua cả loopback và domain HTTPS đều pass.

Khi có sự cố, dùng runbook tại `docs/INCIDENT_RUNBOOK.md`.
