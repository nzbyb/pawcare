from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.types import JsonType


class HealthRecord(Base):
    __tablename__ = "health_records"
    __table_args__ = {"comment": "健康档案"}

    pet_id: Mapped[int] = mapped_column(
        ForeignKey("pets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    record_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
        comment="vaccine / deworm / medication / visit / symptom",
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    record_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    next_due_date: Mapped[date | None] = mapped_column(
        Date, index=True, comment="下次到期日，用于生成提醒"
    )
    note: Mapped[str | None] = mapped_column(Text, comment="备注（不可信数据）")
    extra: Mapped[dict | None] = mapped_column(JsonType, comment="扩展字段")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, comment="软删除时间")
