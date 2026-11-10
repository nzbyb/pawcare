from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.types import EmbeddingType, JsonType


class KnowledgeDocument(Base):
    """知识库文档。

    文档是维护单位（可编辑、可归档），切片是检索单位（由正文自动生成）。
    改正文后切片会被重建，向量置空，由检索或「重建索引」按需重新生成。
    """

    __tablename__ = "knowledge_documents"
    __table_args__ = {"comment": "护理知识库文档"}

    doc_id: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True, comment="稳定文档标识"
    )
    category: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True, comment="boarding / vaccine 等分类"
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="完整正文")
    source: Mapped[str] = mapped_column(
        String(200), nullable=False, default="PawCare 护理知识库"
    )
    status: Mapped[str] = mapped_column(
        String(20), default="published", nullable=False, index=True,
        comment="published / archived",
    )
    chunk_count: Mapped[int] = mapped_column(default=0, nullable=False)
    # 上一次生成切片时的正文摘要，用来判断正文改过但没重建索引。
    content_hash: Mapped[str | None] = mapped_column(String(64))
    indexed_at: Mapped[datetime | None] = mapped_column(
        DateTime, comment="最近一次生成切片的时间"
    )
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("doc_id", "chunk_index", name="uq_knowledge_doc_chunk"),
        {"comment": "护理知识库切片"},
    )

    # 切片以 doc_id 归属文档；文档删除时切片级联删除（MySQL 生效，
    # SQLite 需开启 foreign_keys，测试与本地都以服务层显式删除兜底）。
    doc_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("knowledge_documents.doc_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(EmbeddingType)
    meta: Mapped[dict | None] = mapped_column(JsonType)
