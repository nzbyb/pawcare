from typing import Literal

from pydantic import BaseModel, Field

# 文档编号只用于稳定引用，要求小写字母、数字和短横线，便于记忆和排查。
DOC_ID_PATTERN = r"^[a-z0-9][a-z0-9-]{1,99}$"


class KnowledgeDocumentCreate(BaseModel):
    doc_id: str | None = Field(default=None, pattern=DOC_ID_PATTERN)
    category: str = Field(min_length=2, max_length=30)
    title: str = Field(min_length=2, max_length=200)
    content: str = Field(min_length=10, max_length=20000)
    source: str | None = Field(default=None, max_length=200)
    status: Literal["published", "archived"] = "published"


class KnowledgeDocumentUpdate(BaseModel):
    category: str = Field(min_length=2, max_length=30)
    title: str = Field(min_length=2, max_length=200)
    content: str = Field(min_length=10, max_length=20000)
    source: str | None = Field(default=None, max_length=200)


class KnowledgeStatusUpdate(BaseModel):
    status: Literal["published", "archived"]


class KnowledgeHitTestQuery(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    top_k: int = Field(default=5, ge=1, le=10)
    category: str | None = Field(default=None, max_length=30)
