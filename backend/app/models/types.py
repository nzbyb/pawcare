from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import Text, TypeDecorator

try:
    from pgvector.sqlalchemy import Vector
except Exception:  # pragma: no cover - 没装 pgvector 时仍可跑 SQLite 测试
    Vector = None

# PostgreSQL 用 JSONB，SQLite 自动退回 JSON。
JsonType = JSON().with_variant(JSONB, "postgresql")


class EmbeddingType(TypeDecorator):
    """512 维向量列。

    PostgreSQL 上映射到 pgvector 的 vector(512)；
    SQLite 上退回 TEXT，方便本地测试不依赖 pgvector。
    """

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql" and Vector is not None:
            return dialect.type_descriptor(Vector(512))
        return dialect.type_descriptor(Text())
