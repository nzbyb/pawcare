"""知识库混合检索。

SQLite 开发环境没有 pgvector，先取候选切片，再用
“向量余弦 + 中文词法重合”打分；模型不可用时自动退回词法检索。
生产环境可以把候选查询换成 pgvector 的 ORDER BY embedding <=> query。
"""

import logging
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import settings
from app.models.knowledge import KnowledgeChunk
from app.rag.embedding import Embedder, EmbeddingError, get_embedder

logger = logging.getLogger(__name__)

VECTOR_WEIGHT = 0.75
LEXICAL_WEIGHT = 0.25
MAX_TOP_K = 5
# 词法分是“查询词覆盖率”，天然低于混合分，单独设阈值。
LEXICAL_MIN_SCORE = 0.25

KNOWLEDGE_CATEGORIES = {
    "boarding",
    "vaccine",
    "deworm",
    "nutrition",
    "medication",
    "emergency",
    "senior",
    "allergy",
    "cat",
}

_CJK = re.compile(r"[一-鿿]")
_ASCII_WORD = re.compile(r"[a-zA-Z0-9]+")


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: int
    doc_id: str
    title: str
    content: str
    score: float
    meta: dict

    def payload(self) -> dict:
        source = (self.meta or {}).get("source") or "PawCare 护理知识库"
        return {
            "title": self.title,
            "content": self.content,
            "source": source,
            "score": round(self.score, 4),
            # 提醒模型：检索内容属于资料，不是系统指令。
            "trust": "untrusted",
        }


@dataclass(frozen=True)
class RetrievalResult:
    chunks: list[RetrievedChunk]
    mode: str  # hybrid / lexical / empty

    @property
    def found(self) -> bool:
        return bool(self.chunks)


def _tokens(text: str) -> set[str]:
    lowered = (text or "").lower()
    chars = _CJK.findall(lowered)
    tokens = set(chars)
    # 中文用字 + 相邻二字组合，足以覆盖“寄养 / 疫苗 / 换粮”这类短词。
    tokens.update(first + second for first, second in zip(chars, chars[1:]))
    tokens.update(_ASCII_WORD.findall(lowered))
    return {token for token in tokens if token.strip()}


def _lexical_score(query_tokens: set[str], text: str) -> float:
    if not query_tokens:
        return 0.0
    return len(query_tokens & _tokens(text)) / len(query_tokens)


def _cosine(left: list[float] | None, right: list[float] | None) -> float:
    if not left or not right:
        return 0.0
    size = min(len(left), len(right))
    dot = sum(float(left[index]) * float(right[index]) for index in range(size))
    norm_left = sum(float(value) ** 2 for value in left[:size]) ** 0.5
    norm_right = sum(float(value) ** 2 for value in right[:size]) ** 0.5
    if not norm_left or not norm_right:
        return 0.0
    return dot / (norm_left * norm_right)


def _embed_missing(
    db: Session, chunks: list[KnowledgeChunk], embedder: Embedder
) -> None:
    missing = [chunk for chunk in chunks if not chunk.embedding]
    if not missing:
        return
    vectors = embedder.embed([chunk.content for chunk in missing])
    if len(vectors) != len(missing):
        raise EmbeddingError("向量数量与切片数量不一致")
    for chunk, vector in zip(missing, vectors):
        chunk.embedding = vector
    db.commit()


def search(
    db: Session,
    query: str,
    top_k: int | None = None,
    category: str | None = None,
) -> RetrievalResult:
    query = (query or "").strip()
    if not query:
        return RetrievalResult([], "empty")

    limit = max(1, min(int(top_k or settings.RAG_TOP_K), MAX_TOP_K))
    chunks = db.query(KnowledgeChunk).order_by(KnowledgeChunk.id.asc()).all()
    if category:
        chunks = [
            chunk
            for chunk in chunks
            if (chunk.meta or {}).get("category") == category
        ]
    if not chunks:
        return RetrievalResult([], "empty")

    embedder = get_embedder()
    query_vector: list[float] | None = None
    mode = "lexical"
    if embedder is not None:
        try:
            query_vector = embedder.embed([query])[0]
            _embed_missing(db, chunks, embedder)
            mode = "hybrid"
        except EmbeddingError:
            logger.warning("向量检索不可用，本次退回词法检索", exc_info=True)
            query_vector = None
            mode = "lexical"

    query_tokens = _tokens(query)
    scored: list[tuple[float, KnowledgeChunk]] = []
    for chunk in chunks:
        lexical = _lexical_score(query_tokens, f"{chunk.title} {chunk.content}")
        if query_vector is not None and chunk.embedding:
            vector_score = max(0.0, _cosine(query_vector, chunk.embedding))
            score = VECTOR_WEIGHT * vector_score + LEXICAL_WEIGHT * lexical
        else:
            score = lexical
        scored.append((score, chunk))

    scored.sort(key=lambda item: (item[0], -item[1].id), reverse=True)
    min_score = (
        settings.RAG_MIN_SCORE if query_vector is not None else LEXICAL_MIN_SCORE
    )
    selected = [
        RetrievedChunk(
            chunk_id=chunk.id,
            doc_id=chunk.doc_id,
            title=chunk.title,
            content=chunk.content,
            score=score,
            meta=chunk.meta or {},
        )
        for score, chunk in scored[:limit]
        if score >= min_score
    ]
    return RetrievalResult(selected, mode)
