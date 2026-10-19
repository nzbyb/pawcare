"""护理知识库检索（RAG）。

本地开发用 fastembed + SQLite 余弦相似度；
生产环境保留同一套检索接口，后续可切换到 PostgreSQL + pgvector。
"""

from app.rag.retriever import RetrievalResult, RetrievedChunk, search

__all__ = ["RetrievalResult", "RetrievedChunk", "search"]
