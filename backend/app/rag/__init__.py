"""护理知识库检索（RAG）。

向量以 JSON 文本存库（MySQL / SQLite 通用），
检索在应用层计算余弦相似度并与中文词法覆盖率混合排序。
"""

from app.rag.retriever import RetrievalResult, RetrievedChunk, search

__all__ = ["RetrievalResult", "RetrievedChunk", "search"]
