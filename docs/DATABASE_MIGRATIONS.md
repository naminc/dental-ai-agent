# Database migrations với Alembic

Alembic là cách duy nhất được hỗ trợ để thay đổi database schema. FastAPI và Gunicorn không tự tạo bảng hoặc tự chạy migration khi startup.

## Chuẩn bị

Kích hoạt đúng Python environment và bảo đảm `.env` chứa `DATABASE_URL`, `SECRET_KEY` cùng cấu hình engine hợp lệ:

```bash
cd /www/wwwroot/dental-ai
source .venv/bin/activate
alembic current
```

Alembic dùng chung `Base.metadata` trong `src.database.database`, các model trong `src.database.models` và `database_url` từ `src.core.settings`.

## Apply migration

Backup database trước khi apply trên production:

```bash
mysqldump -h 127.0.0.1 -u dental_ai -p dental_agent_db > /www/backup/dental_agent_db_before_migration.sql
alembic upgrade head
alembic current
```

Chạy lại `alembic upgrade head` là an toàn; Alembic chỉ chạy các revision chưa được apply.

## Database production đã có bảng từ `create_all()` cũ

Không chạy initial migration trực tiếp nếu database đã có đủ ba bảng `users`, `chat_sessions`, `messages`, vì migration sẽ cố tạo lại bảng.

Sau khi backup, đối chiếu schema hiện tại với `migrations/versions/0001_initial_schema.py`. Chỉ khi cấu trúc khớp, đánh dấu revision mà không chạy DDL:

```bash
alembic stamp 0001_initial
alembic current
```

`stamp` không tạo hay thay đổi bảng. Không dùng lệnh này cho database rỗng.

## Tạo migration mới

Thay đổi SQLAlchemy models trước, sau đó autogenerate revision:

```bash
alembic revision --autogenerate -m "describe schema change"
```

Luôn đọc file migration vừa sinh trước khi apply, đặc biệt kiểm tra:

- Tên bảng và cột.
- Nullable và server default.
- Foreign key và index.
- Các thao tác drop/rename ngoài ý muốn.
- Cả `upgrade()` và `downgrade()`.

Sau khi review:

```bash
alembic upgrade head
alembic current
```

## Rollback một revision

```bash
alembic downgrade -1
alembic current
```

Xem lịch sử và revision hiện tại:

```bash
alembic history --verbose
alembic current --verbose
alembic heads
```

Không rollback production nếu migration xóa hoặc biến đổi dữ liệu mà chưa có backup đã kiểm chứng.

## Kiểm tra migration trên database rỗng

Có thể dùng SQLite file tạm cho smoke test schema cơ bản:

```bash
APP_ENV=test \
DATABASE_URL=sqlite:///migration_test.db \
SECRET_KEY=test-only-secret \
EMBEDDING_ENGINE=local \
LLM_ENGINE=local \
alembic upgrade head

APP_ENV=test DATABASE_URL=sqlite:///migration_test.db SECRET_KEY=test-only-secret EMBEDDING_ENGINE=local LLM_ENGINE=local alembic upgrade head
APP_ENV=test DATABASE_URL=sqlite:///migration_test.db SECRET_KEY=test-only-secret EMBEDDING_ENGINE=local LLM_ENGINE=local alembic downgrade -1
```

SQLite smoke test không thay thế việc kiểm tra migration trên một MySQL staging database cùng version với production.
