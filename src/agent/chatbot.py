import logging
import time
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

from src.core.settings import get_settings
from src.providers.protocols import ChatProvider
from src.retriever.query_expander import QueryExpander
from src.retriever.search import Retriever
from src.lib.constants import (
    AI_TEMPERATURE,
    AI_SYSTEM_INSTRUCTIONS,
    AI_USER_PROMPT_TEMPLATE,
    REWRITE_SYSTEM_PROMPT,
    REWRITE_USER_TEMPLATE,
    EXTRACT_CATEGORY_SYSTEM_PROMPT,
    EXTRACT_CATEGORY_USER_TEMPLATE,
)

settings = get_settings()


class DentalChatbot:
    """
    Dental RAG Chatbot với Multi-LLM Engine.
    Hỗ trợ 2 engine cho Text Generation / Query Rewrite:
      - "openai": API OpenAI (gpt-4.1-mini) — cần OPENAI_API_KEY
      - "local":  Ollama localhost (qwen2.5:1.5b) — cần Ollama đang chạy

    """

    # Khởi tạo Chatbot
    def __init__(
        self,
        chat_provider: ChatProvider,
        llm_engine: str = settings.llm_engine.value,
        embedding_engine: str = settings.embedding_engine.value,
        retriever: Retriever | None = None,
    ) -> None:
        self.llm_engine: str = llm_engine
        self.chat_provider = chat_provider
        self.retriever = retriever or Retriever(
            engine=embedding_engine,
            llm_engine=llm_engine,
            query_expander=QueryExpander(self.chat_provider),
        )

    # Format lịch sử hội thoại cho prompt
    def format_history_for_prompt(self, chat_history):
        if not chat_history:
            return "Chưa có lịch sử hội thoại."

        lines = []
        for item in chat_history[-8:]:
            role = "Người dùng" if item["role"] == "user" else "Trợ lý"
            lines.append(f"{role}: {item['content']}")
        return "\n".join(lines)

    # Format lịch sử hội thoại cho rewrite query
    def format_history_for_rewrite(self, chat_history):
        if not chat_history:
            return "Chưa có lịch sử hội thoại."

        lines = []
        for item in chat_history[-6:]:
            if item["role"] == "user":
                lines.append(f"Người dùng: {item['content']}")
            else:
                first_line = item["content"].split("\n")[0][:120]
                lines.append(f"Trợ lý (tóm tắt): {first_line}...")
        return "\n".join(lines)

    def rewrite_query(self, user_question: str, chat_history=None) -> str:
        history_text = self.format_history_for_rewrite(chat_history or [])
        prompt = REWRITE_USER_TEMPLATE.format(
            history=history_text,
            question=user_question,
        )

        return self.chat_provider.complete(
            messages=[
                {"role": "system", "content": REWRITE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=AI_TEMPERATURE["STRICT"],
            max_tokens=100,
        )

    # Extract category từ query
    def extract_category(self, query: str) -> list[str] | None:
        # Lấy danh sách bệnh lý có sẵn
        diseases = self.retriever.get_available_diseases()
        if not diseases:
            return None

        # Tạo prompt cho extract_category
        prompt = EXTRACT_CATEGORY_USER_TEMPLATE.format(
            diseases=", ".join(diseases),
            query=query,
        )

        try:
            result = self.chat_provider.complete(
                messages=[
                    {"role": "system", "content": EXTRACT_CATEGORY_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=AI_TEMPERATURE["STRICT"],
                max_tokens=50,
            )

            if result.upper() in ("NONE", "KHÔNG XÁC ĐỊNH", "KHÔNG RÕ", ""):
                return None

            categories = [kw.strip() for kw in result.split("|") if kw.strip()]
            return categories if categories else None

        except Exception:
            return None

    # Xây dựng ngữ cảnh
    def build_context(self, results):
        if not results:
            return "Không tìm thấy ngữ cảnh liên quan."
        contexts = []
        for item in results:
            parts = [
                f"Tiêu đề: {item.get('title', '')}",
                f"Mục: {item.get('section', '')}",
            ]
            if summary := item.get("summary", "").strip():
                parts.append(f"Tóm tắt: {summary}")
            parts.append(f"Nội dung: {item.get('content', '')}")
            parts.append(f"Nguồn: {item.get('source', '')}")
            contexts.append("\n".join(parts))
        return "\n\n---\n\n".join(contexts)

    # Pipeline trả lời
    def answer_stream(self, user_question: str, chat_history=None):
        is_cloud = self.llm_engine == "openai"
        mode_label = "CLOUD" if is_cloud else "LOCAL"
        t_pipeline = time.perf_counter()
        chat_history = chat_history or []

        logger.info("[TIME-LOG] Pipeline mode: %s (LLM_ENGINE=%s)", mode_label, self.llm_engine)

        # [1] Rewrite -> [2] Extract Category + Multi-Query Expansion -> [3] Retrieval -> [4] LLM

        # [1] Rewrite query
        t0 = time.perf_counter()
        rewritten_question = self.rewrite_query(user_question, chat_history)
        t_rewrite = time.perf_counter() - t0
        logger.info("[TIME-LOG] Rewrite Query mất: %.2fs", t_rewrite)

        # [2] Extract Category + Multi-Query Expansion
        t_parallel_start = time.perf_counter()

        def _safe_extract():
            t0 = time.perf_counter()
            try:
                result = self.extract_category(rewritten_question)
            except Exception:
                result = None
            elapsed = time.perf_counter() - t0
            logger.info("[TIME-LOG] Extract Category mất: %.2fs", elapsed)
            return result

        if settings.multi_query_expansion:
            def _safe_expand():
                t0 = time.perf_counter()
                try:
                    result = self.retriever.expand_queries(rewritten_question)
                except Exception:
                    result = [rewritten_question]
                elapsed = time.perf_counter() - t0
                logger.info("[TIME-LOG] Multi-Query Expansion mất: %.2fs (%d queries)", elapsed, len(result))
                return result

            with ThreadPoolExecutor(max_workers=2) as executor:
                future_extract = executor.submit(_safe_extract)
                future_expand = executor.submit(_safe_expand)
                categories = future_extract.result()
                expanded_queries = future_expand.result()
        else:
            categories = _safe_extract()
            expanded_queries = [rewritten_question]
            logger.info("[TIME-LOG] Multi-Query Expansion: OFF (MULTI_QUERY_EXPANSION=false)")

        t_parallel = time.perf_counter() - t_parallel_start
        logger.info("[TIME-LOG] Extract + Expand mất: %.2fs", t_parallel)

        # [3] Retrieval (FAISS + BM25 + RRF)
        t0 = time.perf_counter()
        retrieved_docs = self.retriever.search(
            rewritten_question,
            categories=categories,
            expanded_queries=expanded_queries,
        )
        t_retrieval = time.perf_counter() - t0
        logger.info("[TIME-LOG] Retrieval tổng mất: %.2fs", t_retrieval)

        context = self.build_context(retrieved_docs)
        history_text = self.format_history_for_prompt(chat_history)

        user_prompt = AI_USER_PROMPT_TEMPLATE.format(
            history=history_text,
            context=context,
            question=user_question
        )

        # [4] LLM Generation
        t_llm_start = time.perf_counter()
        t_first_token = None

        response = self.chat_provider.stream(
            messages=[
                {"role": "system", "content": AI_SYSTEM_INSTRUCTIONS},
                {"role": "user", "content": user_prompt}
            ],
            temperature=AI_TEMPERATURE["NORMAL"],
        )

        for content in response:
            if t_first_token is None:
                t_first_token = time.perf_counter() - t_llm_start
                logger.info("[TIME-LOG] LLM Time-to-First-Token: %.2fs", t_first_token)
            yield content

        t_llm_total = time.perf_counter() - t_llm_start
        logger.info("[TIME-LOG] LLM Generation tổng: %.2fs", t_llm_total)

        disclaimer = "\n\n*Thông tin chỉ mang tính tham khảo, không thay thế tư vấn trực tiếp từ bác sĩ nha khoa.*"
        yield disclaimer

        yield {
            "sources": retrieved_docs,
            "rewritten_query": rewritten_question
        }

        t_total = time.perf_counter() - t_pipeline
        logger.info(
            "[TIME-LOG] TỔNG KẾT PIPELINE (%s) | "
            "Rewrite: %.2fs | Extract+Expand: %.2fs | Retrieval: %.2fs | "
            "LLM-First-Token: %.2fs | LLM-Total: %.2fs | TỔNG: %.2fs",
            mode_label, t_rewrite, t_parallel, t_retrieval,
            t_first_token or 0, t_llm_total, t_total,
        )
