# API Architecture — FastAPI, Dependency Injection & SSE Streaming

Tài liệu giải thích kiến trúc API backend, bao gồm cách tổ chức module, Dependency Injection pattern, và cơ chế Server-Sent Events cho streaming response.

**Tham chiếu mã nguồn:**
- `api/main.py` — FastAPI entry point
- `src/chat/router.py` — Chat endpoints
- `src/chat/dependencies.py` — Lazy-init DentalChatbot
- `src/auth/router.py` — Auth endpoints

---

## 1. Kiến trúc Module

```
api/
├── main.py              ← Entry point, CORS, include routers
├── lifespan.py          ← Startup/shutdown (kiểm tra DB, init chatbot, dispose pool)
└── exception_handlers.py ← Xử lý lỗi DB toàn cục (trả 503 thay vì crash)

src/
├── chat/
│   ├── router.py        ← Chat API endpoints
│   ├── schemas.py       ← Pydantic request/response models
│   └── dependencies.py  ← Lazy-init chatbot (DI provider)
├── auth/
│   ├── router.py        ← Auth API endpoints
│   ├── schemas.py       ← Pydantic models
│   └── utils.py         ← JWT, bcrypt, get_current_user
├── agent/
│   └── chatbot.py       ← RAG pipeline logic
├── retriever/
│   ├── search.py        ← Retriever compatibility facade
│   ├── index_store.py   ← Shared FAISS index + metadata loader
│   ├── vector_searcher.py ← Vector similarity search
│   ├── bm25_searcher.py ← Tokenization + keyword search
│   ├── query_expander.py ← Query variants from injected LLM client
│   ├── category_matcher.py ← Category pre-filter
│   ├── rrf_ranker.py    ← RRF merge + overview boost
│   ├── retrieval_service.py ← Pipeline orchestration
│   ├── ingest.py        ← FAISS index builder
│   └── engines.py       ← Compatibility embedding factory
├── providers/
│   ├── protocols.py     ← Chat, stream, embedding, expansion interfaces
│   ├── chat.py          ← OpenAI and Ollama-compatible chat adapters
│   ├── embedding.py     ← OpenAI and local embedding adapters
│   ├── factory.py       ← Process-cached provider construction
│   └── errors.py        ← Safe application-level provider errors
├── database/
│   ├── database.py      ← SQLAlchemy engine (connection pool) & session
│   └── models.py        ← ORM models
├── lib/
│   └── constants.py     ← All prompts & AI config
├── core/settings.py     ← Validated pydantic-settings configuration
└── config.py            ← Backward-compatible config aliases
```

### Nguyên tắc tổ chức

- **Domain-driven:** Mỗi domain (chat, auth) là 1 package riêng với router + schemas + dependencies
- **Separation of Concerns:** `main.py` chỉ setup app + CORS + include routers; `lifespan.py` quản lý startup/shutdown; `exception_handlers.py` xử lý lỗi toàn cục
- **Config tập trung:** Mọi biến môi trường qua `core/settings.py`, mọi prompt qua `constants.py`
- **Provider boundary:** Chatbot và retrieval chỉ phụ thuộc protocol; OpenAI SDK chỉ xuất hiện trong `providers/`

---

## 2. FastAPI Entry Point

```python
# api/main.py
from api.lifespan import lifespan
from api.exception_handlers import register_exception_handlers

app = FastAPI(title="Dental AI API", version="1.0.0", lifespan=lifespan)
register_exception_handlers(app)

app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, ...)

app.include_router(auth_router.router)   # /api/auth/*
app.include_router(chat_router.router)   # /api/chat/*
```

```python
# api/lifespan.py — Startup không gọi dependency ngoài; Shutdown: dispose pool
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    engine.dispose()  # Giải phóng toàn bộ connection pool
```

```python
# api/exception_handlers.py — Bắt lỗi DB toàn cục, trả 503 thay vì crash
def register_exception_handlers(app: FastAPI):
    @app.exception_handler(OperationalError)
    async def db_operational_error_handler(request, exc):
        return JSONResponse(status_code=503, content={"detail": "..."})
```

`main.py` chỉ làm các việc:
1. Khởi tạo FastAPI và đăng ký exception handlers.
2. Cấu hình CORS middleware.
3. Cung cấp `/health` và `/ready`.
4. Include 2 routers: `/api/auth/*` và `/api/chat/*`.

Database schema được quản lý riêng bằng Alembic; application startup không tạo bảng hoặc chạy migration. Chatbot/retriever được lazy-load khi endpoint chat cần dùng.

### Database Connection Pool (Production)

`src/database/database.py` cấu hình engine với connection pool ổn định cho production:

| Tham số | Giá trị | Tác dụng |
|---|---|---|
| `pool_pre_ping` | `True` | Kiểm tra connection còn sống trước khi dùng (fix lỗi `MySQL server has gone away`) |
| `pool_recycle` | `280` | Tái tạo connection trước timeout thường gặp của MySQL |
| `pool_size` | `5` | Số connection thường trực trên mỗi worker |
| `max_overflow` | `10` | Số connection tạm thêm trên mỗi worker (tổng max = 15) |
| `pool_timeout` | `30` | Chờ tối đa 30s để lấy connection từ pool |

Ngoài ra, event listener `checkout` kiểm tra connection bằng `SELECT 1` mỗi khi lấy ra khỏi pool (dự phòng cho `pool_pre_ping`). Nếu connection đã chết → tự tạo mới, không để backend crash.

---

## 3. Dependency Injection — Lazy Initialization

### Vấn đề

`DentalChatbot` khi khởi tạo sẽ:
- Load FAISS index (~50MB)
- Load sentence-transformers model (~420MB)
- Khởi tạo BM25 corpus (tokenize 762 tài liệu)

Nếu khởi tạo ngay khi server start → chậm startup. Nếu khởi tạo mỗi request → lãng phí tài nguyên.

### Giải pháp: Singleton + lazy initialization

```python
# src/chat/dependencies.py
_chatbot: DentalChatbot | None = None

def get_chatbot() -> DentalChatbot:
    """Singleton — chỉ khởi tạo DentalChatbot 1 lần duy nhất."""
    global _chatbot
    if _chatbot is None:
        t0 = time.perf_counter()
        _chatbot = DentalChatbot()
        print(f"[STARTUP] DentalChatbot khởi tạo xong trong {time.perf_counter() - t0:.2f}s")
    return _chatbot
```

- **Singleton:** Các request sau dùng chung instance, không tạo mới
- **DI-compatible:** Inject qua `Depends(get_chatbot)` trong FastAPI
- **Lazy-load:** request chat đầu tiên mới khởi tạo chatbot; lỗi provider/model trả 503 nhưng không làm chết web process

### Sử dụng trong Router

```python
@router.post("")
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    chatbot: DentalChatbot = Depends(get_chatbot),
):
    ...
```

FastAPI tự động gọi `get_chatbot()`, `get_db()`, `get_current_user()` trước khi handler chạy.

---

## 4. Server-Sent Events (SSE) — Streaming Response

### Tại sao cần SSE?

LLM sinh câu trả lời **từng token** (mỗi token ~0.05s). Nếu đợi toàn bộ xong mới trả → người dùng chờ 5-10 giây nhìn màn hình trắng. SSE cho phép **stream từng phần** → người dùng thấy chữ hiện dần như chatbot đang "gõ".

### Cơ chế hoạt động

```
Client                          Server
  │                               │
  │── POST /api/chat ────────────>│
  │                               │── Rewrite query (LLM call 1)
  │                               │── Extract category (LLM call 2)
  │                               │── Hybrid search
  │                               │── Start answer stream (LLM call 4)
  │                               │
  │<── data: {"token": "Để"} ─────│
  │<── data: {"token": " chăm"} ──│
  │<── data: {"token": " sóc"} ───│
  │         ...                   │
  │<── data: {"token": "..."} ────│
  │<── data: {"done": true, ──────│
  │     "sources": [...],         │
  │     "rewritten_query": "..."}│
  │                               │
```

### Triển khai

```python
async def stream():
    full_answer = ""
    sources = []

    for item in chatbot.answer_stream(user_question, chat_history):
        if isinstance(item, str):
            full_answer += item
            yield f"data: {json.dumps({'token': item})}\n\n"
            await asyncio.sleep(0.01)
        elif isinstance(item, dict):
            sources = item.get("sources", [])

    _save_message(db, session_id, user_id, "assistant", full_answer, sources)
    yield f"data: {json.dumps({'done': True, 'sources': sources})}\n\n"

return StreamingResponse(stream(), media_type="text/event-stream")
```

Đặc điểm:
- `media_type="text/event-stream"` — chuẩn SSE
- Format: `data: {JSON}\n\n` — mỗi event cách nhau bằng 2 newline
- `asyncio.sleep(0.01)` — nhường event loop, tránh block
- Message cuối: `{"done": true, "sources": [...]}` — báo hiệu kết thúc stream
- Database save xảy ra **sau khi stream xong** — không block streaming

### Xử lý lỗi

```python
except Exception as e:
    yield f"data: {json.dumps({'error': 'Lỗi trong quá trình tạo câu trả lời'})}\n\n"
```

Nếu LLM lỗi giữa chừng, client nhận event `error` và hiển thị thông báo thay vì treo.

---

## 5. Pydantic Schemas — Validation

```python
# src/chat/schemas.py
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    user_question: str
    session_id: str
    chat_history: list[ChatMessage] = []
```

Pydantic tự động:
- Validate kiểu dữ liệu (string, list, ...)
- Reject request thiếu field bắt buộc
- Cung cấp default value cho field optional
- Generate OpenAPI schema cho Swagger docs

---

## 6. Danh sách API Endpoints

### Chat (`/api/chat`)

| Method | Endpoint | Mô tả | Response |
|---|---|---|---|
| POST | `/` | Gửi câu hỏi, nhận SSE stream | `text/event-stream` |
| GET | `/sessions` | Danh sách phiên hội thoại | JSON array |
| GET | `/sessions/{id}/messages` | Lịch sử chat của 1 phiên | JSON array |
| DELETE | `/sessions/{id}` | Xóa 1 phiên | JSON message |
| DELETE | `/sessions` | Xóa toàn bộ lịch sử | JSON message |

Tất cả endpoints đều yêu cầu JWT token (`Depends(get_current_user)`).
