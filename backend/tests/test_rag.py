from uuid import uuid4

from sqlalchemy.dialects import postgresql

from app.models.knowledge import KnowledgeChunk
from app.rag import retriever
from tests.fakes import BrokenEmbedder, FakeEmbedder


def add_chunk(
    db,
    *,
    title: str,
    content: str,
    category: str = "boarding",
    source: str = "测试知识库",
) -> KnowledgeChunk:
    chunk = KnowledgeChunk(
        doc_id=f"test-{uuid4().hex[:10]}",
        chunk_index=0,
        title=title,
        content=content,
        meta={"category": category, "source": source},
    )
    db.add(chunk)
    db.commit()
    db.refresh(chunk)
    return chunk


def test_hybrid_search_persists_embedding(db, monkeypatch):
    chunk = add_chunk(
        db,
        title="寄养准备测试",
        content="测试甲：寄养前准备疫苗本和牵引绳。",
        category="boarding",
    )
    monkeypatch.setattr(retriever, "get_embedder", lambda: FakeEmbedder())

    result = retriever.search(db, "寄养前要带什么 测试甲", top_k=3)

    assert result.mode == "hybrid"
    assert result.chunks
    matched = [item for item in result.chunks if item.doc_id == chunk.doc_id]
    assert matched
    assert matched[0].score >= 0.45
    assert matched[0].payload()["trust"] == "untrusted"

    db.expire_all()
    loaded = db.get(KnowledgeChunk, chunk.id)
    assert isinstance(loaded.embedding, list)
    assert len(loaded.embedding) == FakeEmbedder.dimension


def test_search_filters_category(db, monkeypatch):
    boarding = add_chunk(
        db,
        title="寄养分类",
        content="测试乙：寄养准备清单。",
        category="boarding",
    )
    nutrition = add_chunk(
        db,
        title="营养分类",
        content="测试乙：换粮过渡。",
        category="nutrition",
    )
    monkeypatch.setattr(retriever, "get_embedder", lambda: FakeEmbedder())

    result = retriever.search(db, "测试乙", top_k=5, category="boarding")

    assert result.chunks
    ids = {item.chunk_id for item in result.chunks}
    assert boarding.id in ids
    assert nutrition.id not in ids
    assert all(item.meta.get("category") == "boarding" for item in result.chunks)


def test_search_falls_back_to_lexical(db, monkeypatch):
    chunk = add_chunk(
        db,
        title="寄养准备要带什么",
        content="寄养前准备疫苗本、常用粮和牵引绳。",
        category="boarding",
    )
    monkeypatch.setattr(retriever, "get_embedder", lambda: BrokenEmbedder())

    result = retriever.search(db, "寄养准备要带什么", top_k=3)

    assert result.mode == "lexical"
    assert result.chunks
    assert chunk.doc_id in {item.doc_id for item in result.chunks}


def test_search_returns_empty_for_unrelated_query(db, monkeypatch):
    add_chunk(
        db,
        title="寄养准备",
        content="测试丙：寄养需要带疫苗本。",
        category="boarding",
    )
    monkeypatch.setattr(retriever, "get_embedder", lambda: FakeEmbedder())

    result = retriever.search(db, "量子力学 股票行情", top_k=3)

    assert result.mode == "hybrid"
    assert result.chunks == []


def test_search_empty_query(db):
    result = retriever.search(db, "   ")

    assert result.mode == "empty"
    assert result.chunks == []


def test_pgvector_statement_uses_cosine_distance_and_jsonb_filter():
    stmt = retriever._pgvector_statement([0.1] * 512, "vaccine", 12)
    sql = str(stmt.compile(dialect=postgresql.dialect()))

    assert "<=>" in sql
    assert "CAST(" in sql and "VECTOR(512)" in sql.upper()
    assert "->>" in sql
    assert "LIMIT" in sql
