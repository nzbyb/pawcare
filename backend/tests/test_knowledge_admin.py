"""知识库维护接口：文档增删改、状态、重建索引与命中测试。"""

from uuid import uuid4

from app.rag import retriever
from app.services import knowledge_service
from tests.fakes import FakeEmbedder


def payload(**overrides):
    data = {
        "category": "vaccine",
        "title": "疫苗观察要点",
        "content": "接种后留院观察三十分钟，注意精神与食欲变化。出现异常及时联系兽医。",
        "source": "测试知识库",
    }
    data.update(overrides)
    return data


def create(client, headers, **overrides):
    doc_id = overrides.pop("doc_id", f"kb-{uuid4().hex[:10]}")
    body = client.post(
        "/api/admin/knowledge",
        headers=headers,
        json=payload(doc_id=doc_id, **overrides),
    ).json()
    assert body["code"] == 200, body
    return doc_id, body["data"]


def test_admin_knowledge_crud_flow(client, admin_headers):
    doc_id, created = create(client, admin_headers)
    assert created["chunk_count"] >= 1

    listing = client.get(
        "/api/admin/knowledge",
        headers=admin_headers,
        params={"keyword": doc_id},
    ).json()
    assert listing["code"] == 200, listing
    item = next(row for row in listing["data"]["items"] if row["doc_id"] == doc_id)
    assert item["title"] == "疫苗观察要点"
    assert item["missing_embedding"] == created["chunk_count"]
    assert item["needs_reindex"] is False

    detail = client.get(
        f"/api/admin/knowledge/{doc_id}", headers=admin_headers
    ).json()["data"]
    assert detail["content"].startswith("接种后留院观察")
    assert len(detail["chunks"]) == created["chunk_count"]

    long_content = "".join(
        f"第{index}段：观察精神、食欲、体温和排便情况。" for index in range(20)
    )
    updated = client.put(
        f"/api/admin/knowledge/{doc_id}",
        headers=admin_headers,
        json=payload(title="疫苗观察要点（补充）", content=long_content),
    ).json()
    assert updated["code"] == 200, updated
    assert updated["data"]["chunk_count"] > 1

    archived = client.put(
        f"/api/admin/knowledge/{doc_id}/status",
        headers=admin_headers,
        json={"status": "archived"},
    ).json()
    assert archived["data"]["status"] == "archived"

    deleted = client.delete(
        f"/api/admin/knowledge/{doc_id}", headers=admin_headers
    ).json()
    assert deleted["code"] == 200

    missing = client.get(
        f"/api/admin/knowledge/{doc_id}", headers=admin_headers
    ).json()
    assert missing["code"] == 404


def test_create_rejects_unknown_category(client, admin_headers):
    body = client.post(
        "/api/admin/knowledge",
        headers=admin_headers,
        json=payload(doc_id=f"kb-{uuid4().hex[:10]}", category="unknown"),
    ).json()
    assert body["code"] == 400


def test_create_rejects_duplicate_doc_id(client, admin_headers):
    doc_id, _ = create(client, admin_headers)
    duplicated = client.post(
        "/api/admin/knowledge",
        headers=admin_headers,
        json=payload(doc_id=doc_id),
    ).json()
    assert duplicated["code"] == 400


def test_delete_requires_archived(client, admin_headers):
    doc_id, _ = create(client, admin_headers)
    body = client.delete(
        f"/api/admin/knowledge/{doc_id}", headers=admin_headers
    ).json()
    assert body["code"] == 400

    client.put(
        f"/api/admin/knowledge/{doc_id}/status",
        headers=admin_headers,
        json={"status": "archived"},
    )
    assert (
        client.delete(
            f"/api/admin/knowledge/{doc_id}", headers=admin_headers
        ).json()["code"]
        == 200
    )


def test_reindex_generates_embeddings(client, admin_headers, db, monkeypatch):
    monkeypatch.setattr(knowledge_service, "get_embedder", lambda: FakeEmbedder())
    doc_id, _ = create(client, admin_headers)

    body = client.post(
        f"/api/admin/knowledge/{doc_id}/reindex", headers=admin_headers
    ).json()
    assert body["code"] == 200, body
    assert body["data"]["mode"] == "hybrid"
    assert body["data"]["embedded"] == body["data"]["chunk_count"]

    detail = client.get(
        f"/api/admin/knowledge/{doc_id}", headers=admin_headers
    ).json()["data"]
    assert detail["missing_embedding"] == 0
    assert all(chunk["has_embedding"] for chunk in detail["chunks"])


def test_reindex_reports_lexical_fallback(client, admin_headers, monkeypatch):
    monkeypatch.setattr(knowledge_service, "get_embedder", lambda: None)
    doc_id, _ = create(client, admin_headers)

    body = client.post(
        f"/api/admin/knowledge/{doc_id}/reindex", headers=admin_headers
    ).json()
    assert body["code"] == 200
    assert body["data"]["mode"] == "lexical"
    assert body["data"]["error"]


def test_hit_test_returns_scores(client, admin_headers, monkeypatch):
    monkeypatch.setattr(retriever, "get_embedder", lambda: FakeEmbedder())
    marker = f"命中测试{uuid4().hex[:6]}"
    # 用独立分类隔离其他用例留下的文档，避免假向量把排序搅乱。
    doc_id, _ = create(
        client,
        admin_headers,
        category="cat",
        title=marker,
        content=f"{marker}：疫苗后观察三十分钟。",
    )

    body = client.post(
        "/api/admin/knowledge/test",
        headers=admin_headers,
        json={"query": marker, "top_k": 3, "category": "cat"},
    ).json()
    assert body["code"] == 200, body
    data = body["data"]
    assert data["mode"] == "hybrid"
    assert data["results"]
    top = data["results"][0]
    assert top["doc_id"] == doc_id
    assert 0 <= top["score"] <= 1
    assert top["lexical_score"] > 0
    assert "vector_score" in top
    assert isinstance(top["passed"], bool)


def test_archived_document_is_not_retrieved(client, admin_headers, db, monkeypatch):
    monkeypatch.setattr(retriever, "get_embedder", lambda: FakeEmbedder())
    marker = f"归档不回搜{uuid4().hex[:6]}"
    doc_id, _ = create(
        client,
        admin_headers,
        category="senior",
        title=marker,
        content=f"{marker}：内容只在归档前可检索。",
    )

    before = knowledge_service.hit_test(db, query=marker, top_k=5, category="senior")
    assert any(item["doc_id"] == doc_id for item in before["results"])

    client.put(
        f"/api/admin/knowledge/{doc_id}/status",
        headers=admin_headers,
        json={"status": "archived"},
    )
    after = knowledge_service.hit_test(db, query=marker, top_k=5, category="senior")
    assert all(item["doc_id"] != doc_id for item in after["results"])


def test_non_admin_cannot_maintain_knowledge(client, owner_headers):
    assert (
        client.get("/api/admin/knowledge", headers=owner_headers).json()["code"] == 403
    )
    assert (
        client.post(
            "/api/admin/knowledge",
            headers=owner_headers,
            json=payload(doc_id="kb-owner-denied"),
        ).json()["code"]
        == 403
    )
    assert (
        client.post(
            "/api/admin/knowledge/test",
            headers=owner_headers,
            json={"query": "疫苗"},
        ).json()["code"]
        == 403
    )
