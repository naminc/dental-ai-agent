# Production-readiness audit

Ngày audit: 2026-11-08. Phạm vi: backend FastAPI, frontend Next.js, cấu hình
Gunicorn/Nginx, artifact, dependency và tài liệu vận hành.

## Critical

- **Đã sửa — bypass 2FA bằng temp token.** `get_current_user()` trước đây chấp nhận
  mọi JWT có `sub`, kể cả token `purpose=2fa_verify`. Access token mới có
  `purpose=access`; token cũ không có claim này vẫn dùng được để tránh buộc toàn bộ
  người dùng đăng nhập lại. Có regression test riêng.

## High

- **Đã sửa — CORS wildcard kết hợp credentials.** Origin giờ lấy từ
  `CORS_ORIGINS`, wildcard bị validator từ chối và production bắt buộc có ít nhất
  một origin rõ ràng.
- **Đã sửa — production chấp nhận secret yếu.** `SECRET_KEY` production phải có
  tối thiểu 32 ký tự; secret vẫn dùng `SecretStr` và không được log.
- **Đã sửa — lỗi database bị trả/log nguyên văn.** API và log không còn đưa exception
  chứa SQL parameters ra response; log chỉ ghi loại exception.
- **Đã sửa — dependency frontend có advisory High.** Bỏ direct dependency `zod`
  không được dùng và áp dụng các bản vá non-breaking trong lockfile. Scan production
  hiện không còn Critical/High.

## Medium

- **Đã sửa — thiếu security headers.** API thêm `nosniff`, frame deny, referrer,
  permissions và opener policy bằng pure ASGI middleware để không buffer SSE. HSTS
  được cấu hình tại Nginx HTTPS.
- **Đã sửa — readiness chỉ kiểm tra file tồn tại.** `/ready` giờ đọc được FAISS và
  metadata, đồng thời kiểm tra `index.ntotal == len(metadata)`. Nó không load model
  embedding và không gọi provider.
- **Đã sửa — Gunicorn log có thể tăng vô hạn.** App log giữ 30 bản; tài liệu deploy
  có logrotate cho access/error log.
- **Đã sửa — graceful timeout ngắn hơn thời gian SSE.** Gunicorn đọc
  `GUNICORN_GRACEFUL_TIMEOUT`, mặc định 300 giây, đồng bộ với proxy/provider timeout.
- **Đã sửa — cache build bị track.** Xóa `tsconfig.tsbuildinfo`, ignore toàn bộ
  `*.tsbuildinfo` và dùng `git archive` để tạo artifact sạch.
- **Đã sửa — Requests advisory có bản vá.** Nâng `requests` 2.32.5 lên 2.33.0,
  cập nhật `uv.lock` và `requirements.txt`.
- **Chưa sửa — policy mật khẩu không đồng nhất.** Register chưa có minimum length,
  đổi mật khẩu chỉ yêu cầu 6 ký tự. Siết rule sẽ thay đổi contract/UX và có thể từ
  chối payload trước đây hợp lệ, nên chỉ ghi nhận trong audit này.
- **Residual — `python-jose`/`ecdsa`.** `pip-audit` báo 3 finding trong 2 package,
  chưa có fix version. Ứng dụng giới hạn decode vào đúng algorithm cấu hình và mặc
  định HS256, nên các đường tấn công public-key/ecdsa không nằm trên luồng hiện tại.
  Cần theo dõi để thay thư viện khi có lộ trình migration.

## Low

- **Residual — 2 advisory Moderate của PostCSS selector parser.** Chỉ nằm trong
  toolchain Tailwind/Typography khi build; `npm audit` chỉ đề xuất downgrade breaking.
  Không force vì có nguy cơ phá CSS/UI.
- **Residual — development toolchain có 11 advisory.** Scan đầy đủ báo 1 High
  (`zod` transitive qua ESLint config) và 10 Moderate trong ESLint/TypeScript/build
  tooling. Các package này không nằm trong production install/runtime; direct runtime
  `zod` đã được bỏ. Tiếp tục theo dõi bản vá non-breaking, không dùng `--force`.
- **Residual — test client deprecation warning.** Starlette cảnh báo TestClient sẽ
  chuyển sang `httpx2`; không ảnh hưởng runtime production.

## Các mục đã kiểm tra, không thấy lỗi cần sửa

- bcrypt password hashing; JWT có expiration và algorithm allowlist.
- SQLAlchemy pool có pre-ping, recycle, timeout, connect timeout; một worker mặc định.
- OpenAI/Ollama client có timeout/retry tập trung và được cache theo process.
- Startup không gọi database/provider/model; shutdown dispose pool.
- Gunicorn có `max_requests` và jitter để giới hạn tăng memory lâu dài.
- Nginx SSE tắt buffering/cache và có read/send timeout 300 giây.
- Frontend production bắt buộc URL tuyệt đối và từ chối loopback.
- `.env`, `.venv`, `.next`, log, cache và zip không được track trong artifact.
- Alembic, MySQL backup/rollback, smoke test và incident workflow đã có tài liệu.

## Verification đã chạy

```text
pytest: 45 passed
python compileall: passed
uv lock --check: passed
frontend eslint: passed
frontend tsc --noEmit: passed
frontend next build: passed
pip-audit: 3 residual findings / 2 packages, no available fix
npm audit --omit=dev: 2 moderate, 0 high, 0 critical
npm audit (including dev): 10 moderate, 1 high, 0 critical
tracked artifact scan: passed
```

Checklist và command deploy thực tế nằm trong `docs/DEPLOY_AAPANEL.md`; quy trình
xử lý sự cố nằm trong `docs/INCIDENT_RUNBOOK.md`.
