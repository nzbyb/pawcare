from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Pet(Base):
    __tablename__ = "pets"
    __table_args__ = {"comment": "宠物档案"}

    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False, comment="宠物名")
    species: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="dog / cat / other"
    )
    breed: Mapped[str | None] = mapped_column(String(50), comment="品种")
    birthday: Mapped[date | None] = mapped_column(Date, comment="生日")
    gender: Mapped[str | None] = mapped_column(
        String(10), comment="male / female / unknown"
    )
    neutered: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, comment="是否绝育"
    )
    allergies: Mapped[str | None] = mapped_column(Text, comment="过敏史")
    notes: Mapped[str | None] = mapped_column(Text, comment="备注（不可信数据）")
    photo_url: Mapped[str | None] = mapped_column(String(255), comment="照片")
    status: Mapped[str] = mapped_column(
        String(20), default="active", nullable=False, comment="active / deleted"
    )


class WeightRecord(Base):
    __tablename__ = "weight_records"
    __table_args__ = {"comment": "体重记录"}

    pet_id: Mapped[int] = mapped_column(
        ForeignKey("pets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    record_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    weight_kg: Mapped[float] = mapped_column(
        Numeric(5, 2, asdecimal=False), nullable=False, comment="体重 kg"
    )
    note: Mapped[str | None] = mapped_column(Text)


class Attachment(Base):
    __tablename__ = "attachments"
    __table_args__ = {"comment": "附件（多态关联）"}

    owner_type: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True, comment="pet / health_record / report"
    )
    owner_id: Mapped[int] = mapped_column(nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(100))
    size_bytes: Mapped[int | None] = mapped_column()
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
