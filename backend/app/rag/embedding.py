"""文本向量模型封装。

使用 fastembed 的 BAAI/bge-small-zh-v1.5（512 维，中文效果稳定、CPU 可跑）。
模型按需加载：服务启动、单元测试和纯词法检索都不会触发模型下载。
"""

import logging
import threading
from pathlib import Path
from typing import Protocol

from app.config import BASE_DIR, settings

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 512


class EmbeddingError(RuntimeError):
    """模型不可用或向量化失败，调用方应退回词法检索。"""


class Embedder(Protocol):
    dimension: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class FastEmbedEmbedder:
    def __init__(self, model_name: str, cache_dir: Path) -> None:
        self.model_name = model_name
        self.cache_dir = cache_dir
        self.dimension = EMBEDDING_DIM
        self._model = None
        self._load_error: str | None = None
        self._lock = threading.Lock()

    def _load_model(self):
        if self._model is not None:
            return self._model
        if self._load_error is not None:
            raise EmbeddingError(self._load_error)

        with self._lock:
            if self._model is not None:
                return self._model
            if self._load_error is not None:
                raise EmbeddingError(self._load_error)
            try:
                from fastembed import TextEmbedding

                self.cache_dir.mkdir(parents=True, exist_ok=True)
                self._model = TextEmbedding(
                    model_name=self.model_name,
                    cache_dir=str(self.cache_dir),
                )
            except Exception as exc:
                # 记住失败原因，避免每次请求都重复下载/重试。
                self._load_error = f"向量模型加载失败：{exc}"
                logger.warning(self._load_error)
                raise EmbeddingError(self._load_error) from exc
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._load_model()
        try:
            vectors = list(model.embed(texts))
        except Exception as exc:
            raise EmbeddingError(f"文本向量化失败：{exc}") from exc

        result: list[list[float]] = []
        for vector in vectors:
            values = vector.tolist() if hasattr(vector, "tolist") else list(vector)
            if len(values) != self.dimension:
                raise EmbeddingError(
                    f"向量维度不符：期望 {self.dimension}，实际 {len(values)}"
                )
            result.append([float(item) for item in values])
        return result


_embedder: FastEmbedEmbedder | None = None
_embedder_lock = threading.Lock()


def _cache_dir() -> Path:
    path = Path(settings.RAG_CACHE_DIR)
    return path if path.is_absolute() else BASE_DIR / path


def get_embedder() -> Embedder | None:
    """返回进程内复用的向量模型；关闭 RAG 时返回 None。"""
    if not settings.RAG_ENABLED:
        return None

    global _embedder
    if _embedder is None:
        with _embedder_lock:
            if _embedder is None:
                _embedder = FastEmbedEmbedder(
                    settings.RAG_EMBEDDING_MODEL,
                    _cache_dir(),
                )
    return _embedder
