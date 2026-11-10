"""add knowledge documents

Revision ID: a8d3f1c6b7e2
Revises: c7e2a4d9b1f6

知识库原本只有切片表，内容只能靠脚本灌入。这里补上文档表：
文档是维护单位，切片通过 doc_id 归属文档（外键级联删除）。
迁移时按现有切片的 doc_id 反推文档，正文取各切片正文拼接。
"""
import hashlib
import json
from datetime import datetime

from alembic import op
import sqlalchemy as sa

revision = "a8d3f1c6b7e2"
down_revision = "c7e2a4d9b1f6"
branch_labels = None
depends_on = None

DEFAULT_SOURCE = "PawCare 护理知识库"
DEFAULT_CATEGORY = "boarding"


def _load_meta(value):
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _backfill_documents(conn) -> None:
    rows = conn.execute(
        sa.text(
            "SELECT doc_id, chunk_index, title, content, meta "
            "FROM knowledge_chunks ORDER BY doc_id, chunk_index"
        )
    ).mappings()

    grouped: dict[str, dict] = {}
    for row in rows:
        item = grouped.setdefault(
            row["doc_id"],
            {"title": row["title"], "parts": [], "meta": _load_meta(row["meta"])},
        )
        item["parts"].append(row["content"] or "")

    if not grouped:
        return

    now = datetime.now()
    records = []
    for doc_id, item in grouped.items():
        meta = item["meta"]
        content = "".join(item["parts"])
        records.append(
            {
                "doc_id": doc_id,
                "category": meta.get("category") or DEFAULT_CATEGORY,
                "title": (item["title"] or doc_id)[:200],
                "content": content,
                "source": (meta.get("source") or DEFAULT_SOURCE)[:200],
                "status": "published",
                "chunk_count": len(item["parts"]),
                "content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                "indexed_at": now,
                "created_by": None,
                "updated_by": None,
                "create_time": now,
                "update_time": now,
            }
        )

    table = sa.table(
        "knowledge_documents",
        sa.column("doc_id", sa.String),
        sa.column("category", sa.String),
        sa.column("title", sa.String),
        sa.column("content", sa.Text),
        sa.column("source", sa.String),
        sa.column("status", sa.String),
        sa.column("chunk_count", sa.Integer),
        sa.column("content_hash", sa.String),
        sa.column("indexed_at", sa.DateTime),
        sa.column("created_by", sa.Integer),
        sa.column("updated_by", sa.Integer),
        sa.column("create_time", sa.DateTime),
        sa.column("update_time", sa.DateTime),
    )
    op.bulk_insert(table, records)


def upgrade():
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("create_time", sa.DateTime(), nullable=False),
        sa.Column("update_time", sa.DateTime(), nullable=False),
        sa.Column("doc_id", sa.String(100), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="published"),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("indexed_at", sa.DateTime()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        comment="护理知识库文档",
    )
    op.create_index(
        "ix_knowledge_documents_doc_id", "knowledge_documents", ["doc_id"], unique=True
    )
    op.create_index("ix_knowledge_documents_category", "knowledge_documents", ["category"])
    op.create_index("ix_knowledge_documents_status", "knowledge_documents", ["status"])

    _backfill_documents(op.get_bind())

    # 现网只有切片表，加外键需要重建表结构；batch 模式让 SQLite 也能执行。
    with op.batch_alter_table("knowledge_chunks") as batch_op:
        batch_op.create_foreign_key(
            "fk_knowledge_chunks_doc_id",
            "knowledge_documents",
            ["doc_id"],
            ["doc_id"],
            ondelete="CASCADE",
        )


def downgrade():
    with op.batch_alter_table("knowledge_chunks") as batch_op:
        batch_op.drop_constraint("fk_knowledge_chunks_doc_id", type_="foreignkey")
    op.drop_index("ix_knowledge_documents_status", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_category", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_doc_id", table_name="knowledge_documents")
    op.drop_table("knowledge_documents")
