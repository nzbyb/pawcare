"""图片上传。

只接受常见位图格式，扩展名由文件头推断，不信任客户端传的 Content-Type
和文件名。文件按用途分目录保存，返回站内相对地址，前端直接用于 <img>。
"""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.common.exceptions import BusinessException
from app.common.response import Response
from app.config import MAX_FILE_SIZE, UPLOAD_PATH
from app.dependencies.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/uploads", tags=["文件上传"])


def _sniff_type(head: bytes) -> tuple[str, str] | None:
    """根据文件头判断图片类型，返回 (类型名, 扩展名)。"""
    if head.startswith(b"\xff\xd8\xff"):
        return "jpeg", ".jpg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png", ".png"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "gif", ".gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp", ".webp"
    return None


@router.post("", response_model=Response)
def upload_image(
    file: UploadFile = File(...),
    purpose: Literal["pet", "report"] = Form("pet"),
    current_user: User = Depends(get_current_user),
):
    content = file.file.read(MAX_FILE_SIZE + 1)
    if not content:
        raise BusinessException(message="请选择要上传的图片")
    if len(content) > MAX_FILE_SIZE:
        raise BusinessException(message=f"图片不能超过 {MAX_FILE_SIZE // (1024 * 1024)}MB")

    detected = _sniff_type(content[:16])
    if detected is None:
        raise BusinessException(message="仅支持 JPG / PNG / GIF / WEBP 图片")

    _, suffix = detected
    folder = UPLOAD_PATH / purpose
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{suffix}"
    (folder / filename).write_bytes(content)

    return Response.success(
        message="上传成功",
        data={
            "url": f"/uploads/{purpose}/{filename}",
            "size": len(content),
        },
    )
