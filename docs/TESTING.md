# Backend test suite

Test suite dùng `pytest`, chạy hoàn toàn offline và không đọc hoặc ghi dữ liệu
production. Cấu hình, marker và coverage nằm trong `pyproject.toml`.

## Chạy test

Từ thư mục gốc project:

```bash
uv sync
uv run pytest
```

Lệnh `uv run pytest` chạy toàn bộ test và in coverage dạng `term-missing`.
Không có coverage threshold bắt buộc; báo cáo dùng để nhận diện vùng chưa được test.

Chạy từng nhóm:

```bash
uv run pytest -m unit
uv run pytest -m integration
uv run pytest tests/test_auth.py -q
```

Xuất báo cáo HTML khi cần:

```bash
uv run pytest --cov-report=html
```

Mở `htmlcov/index.html` để xem chi tiết.

## Phạm vi hiện tại

- Validation Settings cho OpenAI/local và biến bắt buộc.
- Import `api.main` trong subprocess bị chặn network/database.
- `/health` và các trạng thái `/ready`.
- Auth register/login và JWT hợp lệ, thiếu, sai, hết hạn.
- Retrieval ranking và category matching bằng retriever in-memory.
- Chat SSE streaming bằng fake LLM, gồm kiểm tra lưu message.
- Alembic upgrade, chạy lại upgrade và downgrade trên database rỗng.

## Cách ly dependency và dữ liệu

- Mỗi test dùng một file SQLite tạm riêng và xóa schema khi kết thúc.
- FastAPI dependency `get_db` và session của chat được override sang SQLite.
- Socket ra ngoài bị chặn tự động; test sẽ fail với thông báo rõ nếu code cố gọi
  MySQL, OpenAI, Ollama, Hugging Face hoặc dịch vụ khác.
- `HF_HUB_OFFLINE=1` và `TRANSFORMERS_OFFLINE=1` được bật trước khi import app.
- LLM, embedding và retriever ở boundary được thay bằng fake/in-memory object.
- Không nạp `.env` production, không dùng database URL production và không cần internet.

## Fixtures chính

- `db_session_factory`: session factory trỏ tới SQLite tạm theo từng test.
- `db_session`: session ngắn hạn cho unit test.
- `client`: `TestClient` đã override database dependency.
- `create_user`: tạo user test.
