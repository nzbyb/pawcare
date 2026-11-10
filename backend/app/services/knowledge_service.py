"""护理知识库的文档维护、切片生成与检索测试。

切片规则：按中文句末标点断句，再把句子装进目标长度的切片段落。
文档是编辑单位，切片是检索单位；改正文后整篇重建切片，向量置空，
由检索或「重建索引」按需重新生成，避免保存时被模型拖慢。
"""

import hashlib
import logging
import re
import time
from datetime import datetime

from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.models.audit import AuditLog
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.models.user import User
from app.rag.embedding import EmbeddingError, get_embedder
from app.rag.retriever import KNOWLEDGE_CATEGORIES, search

logger = logging.getLogger(__name__)

# 目标切片长度。现有护理知识每篇 120~180 字，正好一篇一片；
# 新增长文按句子打包，避免出现半句话的切片。
CHUNK_TARGET_CHARS = 300
CHUNK_MIN_CHARS = 80

_SENTENCE_END = "。！？；!?;"
DEFAULT_SOURCE = "PawCare 护理知识库"
STATUSES = ("published", "archived")


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _sentences(text: str) -> list[str]:
    """按句末标点和换行断句，标点保留在前一句末尾。"""
    result: list[str] = []
    buffer: list[str] = []
    for char in text:
        if char == "\n":
            if buffer:
                result.append("".join(buffer))
                buffer = []
            continue
        buffer.append(char)
        if char in _SENTENCE_END:
            result.append("".join(buffer))
            buffer = []
    if buffer:
        result.append("".join(buffer))
    return [item.strip() for item in result if item.strip()]


def _hard_split(sentence: str) -> list[str]:
    # 没有句末标点的长串（操作清单、表格粘贴）直接按目标长度硬切。
    if len(sentence) <= CHUNK_TARGET_CHARS:
        return [sentence]
    return [
        sentence[index:index + CHUNK_TARGET_CHARS]
        for index in range(0, len(sentence), CHUNK_TARGET_CHARS)
    ]


def split_content(content: str) -> list[str]:
    """把正文切成若干切片，保证不丢字、不出现空切片。"""
    text = (content or "").strip()
    if not text:
        return []

    chunks: list[str] = []
    current = ""
    for sentence in _sentences(text):
        for piece in _hard_split(sentence):
            if current and len(current) + len(piece) > CHUNK_TARGET_CHARS:
                chunks.append(current)
                current = ""
            current += piece
    if current:
        chunks.append(current)

    # 末尾过短时并回上一片；并完不能超过目标长度，避免切片大小失控。
    if (
        len(chunks) >= 2
        and len(chunks[-1]) < CHUNK_MIN_CHARS
        and len(chunks[-2]) + len(chunks[-1]) <= CHUNK_TARGET_CHARS
    ):
        chunks[-2] += chunks[-1]
        chunks.pop()
    return chunks


def rebuild_chunks(db: Session, document: KnowledgeDocument) -> int:
    """重建某篇文档的切片。只改内存，由调用方提交事务。"""
    db.query(KnowledgeChunk).filter(
        KnowledgeChunk.doc_id == document.doc_id
    ).delete(synchronize_session=False)

    pieces = split_content(document.content)
    for index, piece in enumerate(pieces):
        db.add(
            KnowledgeChunk(
                doc_id=document.doc_id,
                chunk_index=index,
                title=document.title,
                content=piece,
                meta={
                    "category": document.category,
                    "source": document.source,
                    "document_title": document.title,
                },
            )
        )

    document.chunk_count = len(pieces)
    document.content_hash = content_hash(document.content)
    document.indexed_at = datetime.now()
    db.flush()
    return len(pieces)


def embed_document(db: Session, document: KnowledgeDocument) -> dict:
    """为文档切片生成向量。模型不可用时返回失败原因，不回滚切片。"""
    chunks = (
        db.query(KnowledgeChunk)
        .filter(KnowledgeChunk.doc_id == document.doc_id)
        .order_by(KnowledgeChunk.chunk_index)
        .all()
    )
    if not chunks:
        return {"embedded": 0, "mode": "empty", "error": "文档还没有切片"}

    embedder = get_embedder()
    if embedder is None:
        return {"embedded": 0, "mode": "lexical", "error": "未启用向量模型"}

    try:
        vectors = embedder.embed([chunk.content for chunk in chunks])
    except EmbeddingError as exc:
        logger.warning("知识库重建索引失败：%s", exc)
        return {"embedded": 0, "mode": "lexical", "error": str(exc)}

    if len(vectors) != len(chunks):
        return {"embedded": 0, "mode": "lexical", "error": "向量数量与切片数量不一致"}

    for chunk, vector in zip(chunks, vectors):
        chunk.embedding = vector
    document.indexed_at = datetime.now()
    db.commit()
    return {"embedded": len(chunks), "mode": "hybrid", "error": None}


def needs_reindex(document: KnowledgeDocument) -> bool:
    if not document.chunk_count:
        return True
    return document.content_hash != content_hash(document.content)


def _validate_category(category: str) -> str:
    if category not in KNOWLEDGE_CATEGORIES:
        raise BusinessException(message="知识分类不在允许范围内")
    return category


def _validate_status(status: str) -> str:
    if status not in STATUSES:
        raise BusinessException(message="文档状态不合法")
    return status


def _generate_doc_id(db: Session) -> str:
    for _ in range(20):
        candidate = "kb-" + datetime.now().strftime("%Y%m%d") + "-" + hashlib.md5(
            str(time.time_ns()).encode()
        ).hexdigest()[:6]
        if not db.query(KnowledgeDocument.id).filter(
            KnowledgeDocument.doc_id == candidate
        ).first():
            return candidate
    raise BusinessException(message="文档编号生成失败，请重试", code=500)


def get_document(db: Session, doc_id: str) -> KnowledgeDocument:
    document = (
        db.query(KnowledgeDocument)
        .filter(KnowledgeDocument.doc_id == doc_id)
        .first()
    )
    if document is None:
        raise BusinessException(message="知识文档不存在", code=404)
    return document


def _embedding_stats(db: Session, doc_ids: list[str]) -> dict[str, tuple[int, int]]:
    """返回 doc_id -> (切片数, 未生成向量的切片数)。"""
    if not doc_ids:
        return {}
    rows = (
        db.query(
            KnowledgeChunk.doc_id,
            func.count(KnowledgeChunk.id),
            func.sum(case((KnowledgeChunk.embedding.is_(None), 1), else_=0)),
        )
        .filter(KnowledgeChunk.doc_id.in_(doc_ids))
        .group_by(KnowledgeChunk.doc_id)
        .all()
    )
    return {
        doc_id: (int(total), int(missing or 0))
        for doc_id, total, missing in rows
    }


def _serialize(
    document: KnowledgeDocument,
    *,
    with_content: bool = False,
    stats: tuple[int, int] | None = None,
) -> dict:
    chunks, missing = stats or (document.chunk_count, 0)
    data = {
        "doc_id": document.doc_id,
        "category": document.category,
        "title": document.title,
        "source": document.source,
        "status": document.status,
        "chunk_count": chunks,
        "missing_embedding": missing,
        "needs_reindex": needs_reindex(document),
        "indexed_at": document.indexed_at,
        "update_time": document.update_time,
    }
    if with_content:
        data["content"] = document.content
    return data


def list_documents(
    db: Session,
    *,
    keyword: str | None = None,
    category: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    page = max(1, int(page))
    page_size = max(1, min(50, int(page_size)))

    query = db.query(KnowledgeDocument)
    if keyword and keyword.strip():
        like = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                KnowledgeDocument.title.like(like),
                KnowledgeDocument.content.like(like),
                KnowledgeDocument.doc_id.like(like),
            )
        )
    if category:
        query = query.filter(KnowledgeDocument.category == category)
    if status:
        query = query.filter(KnowledgeDocument.status == status)

    total = query.count()
    rows = (
        query.order_by(KnowledgeDocument.update_time.desc(), KnowledgeDocument.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    stats = _embedding_stats(db, [row.doc_id for row in rows])
    return {
        "items": [_serialize(row, stats=stats.get(row.doc_id)) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def document_detail(db: Session, doc_id: str) -> dict:
    document = get_document(db, doc_id)
    chunks = (
        db.query(KnowledgeChunk)
        .filter(KnowledgeChunk.doc_id == doc_id)
        .order_by(KnowledgeChunk.chunk_index)
        .all()
    )
    data = _serialize(
        document,
        with_content=True,
        stats=(len(chunks), sum(1 for chunk in chunks if not chunk.embedding)),
    )
    data["chunks"] = [
        {
            "id": chunk.id,
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "has_embedding": bool(chunk.embedding),
        }
        for chunk in chunks
    ]
    return data


def create_document(db: Session, actor: User, data: dict) -> KnowledgeDocument:
    _validate_category(data["category"])
    doc_id = (data.get("doc_id") or "").strip() or _generate_doc_id(db)
    if db.query(KnowledgeDocument.id).filter(
        KnowledgeDocument.doc_id == doc_id
    ).first():
        raise BusinessException(message="文档编号已存在")
    if db.query(KnowledgeChunk.id).filter(KnowledgeChunk.doc_id == doc_id).first():
        raise BusinessException(message="文档编号已被已有切片占用")

    document = KnowledgeDocument(
        doc_id=doc_id,
        category=data["category"],
        title=data["title"].strip(),
        content=data["content"].strip(),
        source=(data.get("source") or DEFAULT_SOURCE).strip(),
        status=data.get("status") or "published",
        created_by=actor.id,
        updated_by=actor.id,
    )
    _validate_status(document.status)
    db.add(document)
    rebuild_chunks(db, document)
    db.add(
        AuditLog(
            actor_id=actor.id,
            action="knowledge.create",
            target_type="knowledge_document",
            target_id=document.id,
            after_data={
                "doc_id": document.doc_id,
                "title": document.title,
                "category": document.category,
            },
        )
    )
    db.commit()
    db.refresh(document)
    return document


def update_document(
    db: Session, actor: User, doc_id: str, data: dict
) -> KnowledgeDocument:
    document = get_document(db, doc_id)
    _validate_category(data["category"])
    before = {
        "title": document.title,
        "category": document.category,
        "status": document.status,
    }

    title = data["title"].strip()
    content = data["content"].strip()
    content_changed = content != document.content
    title_changed = title != document.title

    document.category = data["category"]
    document.title = title
    document.content = content
    document.source = (data.get("source") or DEFAULT_SOURCE).strip()
    document.updated_by = actor.id

    if content_changed:
        # 正文变了就整篇重建切片，向量一并置空。
        rebuild_chunks(db, document)
    elif title_changed:
        db.query(KnowledgeChunk).filter(
            KnowledgeChunk.doc_id == doc_id
        ).update({KnowledgeChunk.title: title}, synchronize_session=False)

    db.add(
        AuditLog(
            actor_id=actor.id,
            action="knowledge.update",
            target_type="knowledge_document",
            target_id=document.id,
            before_data=before,
            after_data={
                "title": document.title,
                "category": document.category,
                "content_changed": content_changed,
            },
        )
    )
    db.commit()
    db.refresh(document)
    return document


def set_status(db: Session, actor: User, doc_id: str, status: str) -> KnowledgeDocument:
    _validate_status(status)
    document = get_document(db, doc_id)
    if document.status == status:
        return document
    before = {"status": document.status}
    document.status = status
    document.updated_by = actor.id
    db.add(
        AuditLog(
            actor_id=actor.id,
            action="knowledge.status",
            target_type="knowledge_document",
            target_id=document.id,
            before_data=before,
            after_data={"status": status},
        )
    )
    db.commit()
    db.refresh(document)
    return document


def delete_document(db: Session, actor: User, doc_id: str) -> None:
    document = get_document(db, doc_id)
    if document.status != "archived":
        raise BusinessException(message="请先归档再删除，避免检索内容突然消失")
    db.query(KnowledgeChunk).filter(
        KnowledgeChunk.doc_id == doc_id
    ).delete(synchronize_session=False)
    db.add(
        AuditLog(
            actor_id=actor.id,
            action="knowledge.delete",
            target_type="knowledge_document",
            target_id=document.id,
            before_data={"doc_id": document.doc_id, "title": document.title},
        )
    )
    db.delete(document)
    db.commit()


def reindex(db: Session, actor: User, doc_id: str) -> dict:
    document = get_document(db, doc_id)
    rebuild_chunks(db, document)
    db.commit()
    result = embed_document(db, document)
    db.add(
        AuditLog(
            actor_id=actor.id,
            action="knowledge.reindex",
            target_type="knowledge_document",
            target_id=document.id,
            after_data={
                "chunks": document.chunk_count,
                "embedded": result["embedded"],
                "mode": result["mode"],
            },
        )
    )
    db.commit()
    return {
        "doc_id": document.doc_id,
        "chunk_count": document.chunk_count,
        **result,
    }


def hit_test(
    db: Session,
    *,
    query: str,
    top_k: int = 5,
    category: str | None = None,
) -> dict:
    """管理员检索命中测试：返回 top-k 切片及分数，不套用线上阈值。"""
    query = (query or "").strip()
    if not query:
        raise BusinessException(message="请输入测试问题")
    if category:
        _validate_category(category)

    started = time.perf_counter()
    result = search(db, query, top_k=top_k, category=category, apply_threshold=False)
    elapsed_ms = round((time.perf_counter() - started) * 1000)

    threshold = result.min_score
    return {
        "query": query,
        "mode": result.mode,
        "min_score": round(threshold, 4),
        "elapsed_ms": elapsed_ms,
        "results": [
            {
                "chunk_id": chunk.chunk_id,
                "doc_id": chunk.doc_id,
                "title": chunk.title,
                "content": chunk.content,
                "score": round(chunk.score, 4),
                "vector_score": round(chunk.vector_score, 4),
                "lexical_score": round(chunk.lexical_score, 4),
                "passed": chunk.score >= threshold,
                "source": (chunk.meta or {}).get("source"),
            }
            for chunk in result.chunks
        ],
    }


def counts(db: Session) -> dict:
    return {
        "documents": db.query(func.count(KnowledgeDocument.id)).scalar() or 0,
        "chunks": db.query(func.count(KnowledgeChunk.id)).scalar() or 0,
        "archived": db.query(func.count(KnowledgeDocument.id))
        .filter(KnowledgeDocument.status == "archived")
        .scalar()
        or 0,
    }
