# Quản lý Python dependencies bằng uv

`pyproject.toml` khai báo dependency trực tiếp và `uv.lock` khóa toàn bộ dependency transitively cho Python 3.11. Không chỉnh tay `requirements.txt`; file này là compatibility export cho aaPanel/pip.

## Cài uv

```bash
python -m pip install uv
uv --version
```

## Tạo environment phát triển

```bash
uv sync --frozen
uv run pytest
uv run uvicorn api.main:app --reload --port 8000
```

`uv sync` tạo `.venv`. `--frozen` yêu cầu `uv.lock` khớp `pyproject.toml` và không tự cập nhật lockfile.

## Environment production

Cloud/OpenAI embedding, không cài test tools hoặc local model stack:

```bash
uv sync --frozen --no-dev
```

Nếu production dùng `EMBEDDING_ENGINE=local`:

```bash
uv sync --frozen --no-dev --extra local-embedding
```

Gunicorn:

```bash
uv run --frozen --no-dev gunicorn -c gunicorn_conf.py api.main:app
```

## Data pipeline và crawler

`requests`, `beautifulsoup4` và `ddgs` được khai báo trong group `pipeline` vì chỉ các script trong `tools/` import trực tiếp chúng:

```bash
uv sync --frozen --group pipeline
```

`requests` hiện vẫn xuất hiện trong production export vì `underthesea` cũng phụ thuộc transitively vào nó. Việc đặt `requests` trong group `pipeline` ghi nhận direct ownership của crawler; không ép uv cài hai bản.

Nếu ingest bằng local embedding:

```bash
uv sync --frozen --group pipeline --extra local-embedding
uv run python -m src.retriever.ingest --engine local
```

## Export requirements cho aaPanel/pip

```bash
# Production cloud
uv export --locked --no-dev --no-hashes \
  --format requirements-txt --output-file requirements.txt

# Runtime có local embedding
uv export --locked --no-dev --no-hashes \
  --extra local-embedding \
  --format requirements-txt --output-file requirements-local.txt

# Crawler/data pipeline
uv export --locked --no-dev --no-hashes \
  --group pipeline \
  --format requirements-txt --output-file requirements-pipeline.txt
```

CI nên chạy `uv lock --check` để phát hiện `pyproject.toml` và `uv.lock` không đồng bộ.

## Phân loại package nặng

| Package | Phạm vi | Lý do |
|---|---|---|
| `faiss-cpu` | Runtime bắt buộc | Retriever luôn search FAISS index, kể cả embedding query dùng OpenAI. |
| `numpy` | Runtime bắt buộc | Vector query và FAISS input dùng trực tiếp. |
| `underthesea` | Runtime bắt buộc | BM25 dùng `word_tokenize` cho mọi engine; phần Transformers của Underthesea là optional. |
| `sentence-transformers` | Extra `local-embedding` | Chỉ được import khi `LocalEngine` load model. |
| `torch` | Extra `local-embedding`, transitive và được pin | Cloud/OpenAI runtime không dùng trực tiếp. |
| `transformers` | Extra `local-embedding`, transitive và được pin | Local SentenceTransformer cần; cloud runtime không cần. |

Local stack được giữ theo environment đã chạy ổn: `sentence-transformers==5.3.0`, `torch==2.10.0`, `transformers==5.3.0`.

## Thêm hoặc cập nhật dependency

```bash
uv add package-name
uv add --group dev package-name
uv add --group pipeline package-name
uv add --optional local-embedding package-name
```

Sau thay đổi:

```bash
uv lock
uv sync
uv run pytest
```

Commit `pyproject.toml`, `uv.lock` và compatibility export cần thiết cùng nhau.
