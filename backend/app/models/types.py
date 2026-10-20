import json

from sqlalchemy import JSON
from sqlalchemy.types import Text, TypeDecorator

# MySQL / SQLite 通用：MySQL 会落到 JSON 列，SQLite 存 TEXT 并自动序列化。
JsonType = JSON()


class EmbeddingType(TypeDecorator):
    """512 维向量列。

    以 JSON 文本存库（MySQL 为 TEXT），检索时在应用层计算余弦相似度。
    知识库切片规模在千级以内，SQL 端无需向量类型。
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return json.dumps([float(item) for item in value], ensure_ascii=False)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, str):
            return json.loads(value)
        return value
