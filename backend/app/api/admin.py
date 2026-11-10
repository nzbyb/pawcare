from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.common.response import Response
from app.database import get_db
from app.dependencies.auth import get_current_admin
from app.models.user import User
from app.rag.retriever import KNOWLEDGE_CATEGORIES
from app.schemas.admin import UserStatusUpdate
from app.schemas.content import AnnouncementCreate, AnnouncementUpdate, FeedbackReply
from app.schemas.knowledge import (
    KnowledgeDocumentCreate,
    KnowledgeDocumentUpdate,
    KnowledgeHitTestQuery,
    KnowledgeStatusUpdate,
)
from app.schemas.system import SettingUpdateRequest
from app.services import (
    admin_service,
    content_service,
    export_service,
    knowledge_service,
    setting_service,
)

router = APIRouter(prefix="/admin", tags=["管理端"])


@router.get("/overview", response_model=Response)
def get_overview(
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return Response.success(data=admin_service.overview(db))


@router.get("/statistics", response_model=Response)
def get_statistics(
    days: int = Query(default=30),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return Response.success(data=admin_service.statistics(db, days))


@router.get("/knowledge", response_model=Response)
def list_knowledge(
    keyword: str | None = Query(default=None, max_length=50),
    category: str | None = Query(default=None, max_length=30),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return Response.success(
        data=knowledge_service.list_documents(
            db,
            keyword=keyword,
            category=category,
            status=status,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/knowledge/categories", response_model=Response)
def knowledge_categories(current_user: User = Depends(get_current_admin)):
    return Response.success(data=sorted(KNOWLEDGE_CATEGORIES))


@router.post("/knowledge/test", response_model=Response)
def knowledge_hit_test(
    data: KnowledgeHitTestQuery,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return Response.success(data=knowledge_service.hit_test(db, **data.model_dump()))


@router.post("/knowledge", response_model=Response)
def create_knowledge(
    data: KnowledgeDocumentCreate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    document = knowledge_service.create_document(db, current_user, data.model_dump())
    return Response.success(
        message="知识文档已创建",
        data={
            "doc_id": document.doc_id,
            "chunk_count": document.chunk_count,
            "needs_embedding": True,
        },
    )


@router.get("/knowledge/{doc_id}", response_model=Response)
def knowledge_detail(
    doc_id: str,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return Response.success(data=knowledge_service.document_detail(db, doc_id))


@router.put("/knowledge/{doc_id}", response_model=Response)
def update_knowledge(
    doc_id: str,
    data: KnowledgeDocumentUpdate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    document = knowledge_service.update_document(
        db, current_user, doc_id, data.model_dump()
    )
    return Response.success(
        message="知识文档已更新",
        data={"doc_id": document.doc_id, "chunk_count": document.chunk_count},
    )


@router.put("/knowledge/{doc_id}/status", response_model=Response)
def update_knowledge_status(
    doc_id: str,
    data: KnowledgeStatusUpdate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    document = knowledge_service.set_status(db, current_user, doc_id, data.status)
    return Response.success(
        message="文档状态已更新", data={"doc_id": document.doc_id, "status": document.status}
    )


@router.post("/knowledge/{doc_id}/reindex", response_model=Response)
def reindex_knowledge(
    doc_id: str,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    result = knowledge_service.reindex(db, current_user, doc_id)
    message = "重建完成"
    if result["mode"] != "hybrid":
        message = f"切片已重建，向量未生成：{result['error']}"
    return Response.success(message=message, data=result)


@router.delete("/knowledge/{doc_id}", response_model=Response)
def delete_knowledge(
    doc_id: str,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    knowledge_service.delete_document(db, current_user, doc_id)
    return Response.success(message="知识文档已删除")


@router.get("/users", response_model=Response)
def list_users(
    keyword: str | None = Query(default=None, max_length=50),
    role: str | None = Query(default=None),
    status: int | None = Query(default=None, ge=0, le=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return Response.success(
        data=admin_service.list_users(
            db,
            keyword=keyword,
            role=role,
            status=status,
            page=page,
            page_size=page_size,
        )
    )


@router.put("/users/{user_id}/status", response_model=Response)
def update_user_status(
    user_id: int,
    data: UserStatusUpdate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user = admin_service.set_user_status(db, current_user, user_id, data.status)
    return Response.success(
        message="账号已启用" if data.status == 1 else "账号已停用",
        data={
            "id": user.id,
            "username": user.username,
            "status": user.status,
        },
    )


@router.get("/statistics/export")
def export_statistics(
    days: int = Query(default=30),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    filename, content = export_service.statistics_workbook(db, days)
    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/announcements", response_model=Response)
def list_announcements(
    keyword: str | None = Query(default=None, max_length=50),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return Response.success(
        data=content_service.list_for_admin(
            db, keyword=keyword, status=status, page=page, page_size=page_size
        )
    )


@router.post("/announcements", response_model=Response)
def create_announcement(
    data: AnnouncementCreate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    row = content_service.create_announcement(db, current_user, data)
    return Response.success(message="公告已保存", data={"id": row.id})


@router.put("/announcements/{announcement_id}", response_model=Response)
def update_announcement(
    announcement_id: int,
    data: AnnouncementUpdate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    row = content_service.update_announcement(db, current_user, announcement_id, data)
    return Response.success(message="公告已更新", data={"id": row.id})


@router.delete("/announcements/{announcement_id}", response_model=Response)
def delete_announcement(
    announcement_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    content_service.delete_announcement(db, current_user, announcement_id)
    return Response.success(message="公告已删除")


@router.get("/announcements/{announcement_id}/reads", response_model=Response)
def announcement_reads(
    announcement_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return Response.success(data=content_service.read_stats(db, announcement_id))


@router.get("/feedbacks", response_model=Response)
def list_feedback(
    status: str | None = Query(default=None),
    keyword: str | None = Query(default=None, max_length=50),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return Response.success(
        data=content_service.list_feedback(
            db, status=status, keyword=keyword, page=page, page_size=page_size
        )
    )


@router.put("/feedbacks/{feedback_id}", response_model=Response)
def reply_feedback(
    feedback_id: int,
    data: FeedbackReply,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    row = content_service.reply_feedback(db, current_user, feedback_id, data)
    return Response.success(message="反馈已更新", data={"id": row.id, "status": row.status})


@router.get("/kennels/occupancy", response_model=Response)
def get_kennel_occupancy(
    day: date | None = Query(default=None),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return Response.success(data=admin_service.kennel_occupancy(db, day))


@router.get("/mcp-audit", response_model=Response)
def list_mcp_audit(
    user_id: int | None = Query(default=None, ge=1),
    tool: str | None = Query(default=None, max_length=64),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return Response.success(
        data=admin_service.list_mcp_audit(
            db,
            user_id=user_id,
            tool=tool,
            status=status,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/audit-logs", response_model=Response)
def list_audit_logs(
    action: str | None = Query(default=None, max_length=50),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return Response.success(
        data=admin_service.list_audit_logs(
            db, action=action, page=page, page_size=page_size
        )
    )


@router.get("/settings", response_model=Response)
def list_settings(
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return Response.success(data=setting_service.list_settings(db))


@router.put("/settings", response_model=Response)
def update_settings(
    data: SettingUpdateRequest,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return Response.success(
        message="设置已保存",
        data=setting_service.update_settings(db, current_user, data.items),
    )


@router.get("/login-logs", response_model=Response)
def list_login_logs(
    keyword: str | None = Query(default=None, max_length=50),
    success: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return Response.success(
        data=admin_service.list_login_logs(
            db,
            keyword=keyword,
            success=success,
            page=page,
            page_size=page_size,
        )
    )
