"""测试替身：不加载真实向量模型，以及知识库的最小造数工具。"""

from datetime import datetime
from uuid import uuid4

from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.rag.embedding import EmbeddingError
from app.services.knowledge_service import content_hash


class FakeEmbedder:
    """按关键词生成固定向量，让检索结果可预测。

    向量不补常数项：不相关文本得到全零向量，余弦相似度为 0。
    早期版本给每维加了 0.01，导致两段毫不相干的文本余弦接近 1，
    会把无关文档排进检索结果。
    """

    dimension = 6
    KEYS = ("寄养", "疫苗", "换粮", "测试甲", "测试乙", "测试丙")

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [
            [1.0 if key in text else 0.0 for key in self.KEYS]
            for text in texts
        ]


class BrokenEmbedder:
    dimension = 6

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise EmbeddingError("测试环境模拟模型不可用")


def add_knowledge(
    db,
    *,
    title: str,
    content: str,
    category: str = "boarding",
    source: str = "测试知识库",
    doc_id: str | None = None,
    status: str = "published",
) -> KnowledgeChunk:
    """建一篇文档和它的第一片切片，返回切片。"""
    doc_id = doc_id or f"test-{uuid4().hex[:10]}"
    db.add(
        KnowledgeDocument(
            doc_id=doc_id,
            category=category,
            title=title,
            content=content,
            source=source,
            status=status,
            chunk_count=1,
            content_hash=content_hash(content),
            indexed_at=datetime.now(),
        )
    )
    chunk = KnowledgeChunk(
        doc_id=doc_id,
        chunk_index=0,
        title=title,
        content=content,
        meta={"category": category, "source": source},
    )
    db.add(chunk)
    db.commit()
    db.refresh(chunk)
    return chunk
