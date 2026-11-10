"""切片规则：不丢字、不出现空片、长文按句子打包。"""

from uuid import uuid4

from app.models.user import User
from app.services import knowledge_service
from app.utils.password import hash_password


def test_short_document_stays_one_chunk():
    content = "寄养前准备疫苗本和牵引绳。入住当天先确认喂食习惯。"
    chunks = knowledge_service.split_content(content)

    assert len(chunks) == 1
    assert chunks[0] == content


def test_split_preserves_every_character():
    content = "".join(
        f"第{index}条：护理记录要写清楚时间、症状和处理措施。" for index in range(40)
    )
    chunks = knowledge_service.split_content(content)

    assert len(chunks) > 1
    assert "".join(chunks) == content
    assert all(chunk.strip() for chunk in chunks)
    assert all(len(chunk) <= knowledge_service.CHUNK_TARGET_CHARS for chunk in chunks)


def test_unpunctuated_text_is_hard_split():
    content = "甲" * 1500
    chunks = knowledge_service.split_content(content)

    assert len(chunks) >= 2
    assert "".join(chunks) == content
    assert all(len(chunk) <= knowledge_service.CHUNK_TARGET_CHARS for chunk in chunks)


def test_blank_content_has_no_chunks():
    assert knowledge_service.split_content("   \n  ") == []


def test_rebuild_is_idempotent(db):
    document = knowledge_service.create_document(
        db,
        _actor(db),
        {
            "category": "boarding",
            "title": "幂等测试",
            "content": "第一句内容。第二句内容。第三句内容。",
            "source": "测试知识库",
        },
    )
    first = knowledge_service.document_detail(db, document.doc_id)

    knowledge_service.reindex(db, _actor(db), document.doc_id)
    second = knowledge_service.document_detail(db, document.doc_id)

    assert first["chunk_count"] == second["chunk_count"] == len(second["chunks"])
    assert [chunk["content"] for chunk in first["chunks"]] == [
        chunk["content"] for chunk in second["chunks"]
    ]


def _actor(db):
    user = User(
        username="kb_actor_" + uuid4().hex[:8],
        password_hash=hash_password("Passw0rd!"),
        nickname="知识库测试",
        role="admin",
        status=1,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
