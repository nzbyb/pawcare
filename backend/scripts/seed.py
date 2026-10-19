"""生成可复现的演示数据。

用法（在 backend 目录）：
    .venv\\Scripts\\python.exe scripts\\seed.py

脚本按业务唯一键做 get_or_create，可重复执行，不会清空已有数据。
所有账号、宠物、健康记录均为合成数据。
"""

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# 直接运行脚本时，让 `app` 可被导入
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import models  # noqa: F401  # 注册全部模型
from app.database import Base, SessionLocal, engine
from app.models.boarding import (
    BoardingDailyReport,
    BoardingOrder,
    Kennel,
)
from app.models.pet import Pet, WeightRecord
from app.models.user import User
from app.schemas.health import HealthRecordCreate
from app.services import health_service
from app.utils.password import hash_password

TODAY = date.today()

ACCOUNTS = [
    {
        "username": "owner",
        "password": "Owner12345",
        "nickname": "林小满",
        "role": "pet_owner",
        "phone": "13800000001",
    },
    {
        "username": "owner2",
        "password": "Owner12345",
        "nickname": "陈屿",
        "role": "pet_owner",
        "phone": "13800000002",
    },
    {
        "username": "staff",
        "password": "Staff12345",
        "nickname": "周寄养",
        "role": "boarding_staff",
        "phone": "13800000003",
    },
    {
        "username": "admin",
        "password": "Admin12345",
        "nickname": "管理员",
        "role": "admin",
        "phone": "13800000004",
    },
]

KENNELS = [
    ("K-S-01", "small", 68, "安静角落，适合小型犬或猫"),
    ("K-S-02", "small", 68, "靠近前台，方便观察"),
    ("K-M-01", "medium", 88, "带室内监控，适合中型犬"),
    ("K-M-02", "medium", 88, "带室内监控，靠近活动区"),
    ("K-L-01", "large", 128, "大型犬专属，独立活动区"),
]


def get_or_create_user(db, data: dict) -> User:
    user = db.query(User).filter(User.username == data["username"]).first()
    if user:
        return user
    user = User(
        username=data["username"],
        password_hash=hash_password(data["password"]),
        nickname=data["nickname"],
        role=data["role"],
        phone=data["phone"],
        status=1,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_or_create_kennel(db, code, size, price, note) -> Kennel:
    kennel = db.query(Kennel).filter(Kennel.code == code).first()
    if kennel:
        return kennel
    kennel = Kennel(
        code=code, size=size, status="available", daily_price=price, note=note
    )
    db.add(kennel)
    db.commit()
    db.refresh(kennel)
    return kennel


def get_or_create_pet(db, owner: User, data: dict) -> Pet:
    pet = (
        db.query(Pet)
        .filter(
            Pet.owner_id == owner.id,
            Pet.name == data["name"],
            Pet.status != "deleted",
        )
        .first()
    )
    if pet:
        return pet
    pet = Pet(owner_id=owner.id, status="active", **data)
    db.add(pet)
    db.commit()
    db.refresh(pet)
    return pet


def seed_weights(db, pet: Pet, values: list[float]) -> None:
    if db.query(WeightRecord).filter(WeightRecord.pet_id == pet.id).first():
        return
    for index, weight in enumerate(values):
        db.add(
            WeightRecord(
                pet_id=pet.id,
                record_date=TODAY - timedelta(days=(len(values) - index - 1) * 30),
                weight_kg=weight,
                note="演示数据",
            )
        )
    db.commit()


def seed_health(db, owner: User, pet: Pet, records: list[dict]) -> None:
    if health_service.list_records(db, owner, pet.id):
        return
    for item in records:
        health_service.create_record(
            db, owner, pet.id, HealthRecordCreate(**item)
        )


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        users = {item["username"]: get_or_create_user(db, item) for item in ACCOUNTS}
        owner = users["owner"]
        owner2 = users["owner2"]

        kennels = {
            code: get_or_create_kennel(db, code, size, price, note)
            for code, size, price, note in KENNELS
        }

        doudou = get_or_create_pet(
            db,
            owner,
            {
                "name": "豆豆",
                "species": "dog",
                "breed": "柯基",
                "birthday": date(2022, 5, 12),
                "gender": "male",
                "neutered": True,
                "allergies": "鸡肉",
                "notes": "怕生，遇到陌生人会叫；喜欢被摸下巴。",
            },
        )
        niangao = get_or_create_pet(
            db,
            owner,
            {
                "name": "年糕",
                "species": "cat",
                "breed": "英国短毛猫",
                "birthday": date(2021, 11, 3),
                "gender": "female",
                "neutered": True,
                "allergies": None,
                "notes": "胆小，需要安静环境；换粮容易软便。",
            },
        )
        cola = get_or_create_pet(
            db,
            owner2,
            {
                "name": "可乐",
                "species": "dog",
                "breed": "柴犬",
                "birthday": date(2020, 8, 21),
                "gender": "male",
                "neutered": True,
                "allergies": None,
                "notes": "精力旺盛，需要每天遛两次。",
            },
        )

        seed_weights(db, doudou, [12.1, 12.3, 12.4, 12.5, 12.6, 12.8])
        seed_weights(db, niangao, [4.1, 4.2, 4.2, 4.3, 4.4, 4.5])
        seed_weights(db, cola, [10.8, 10.9, 11.0, 11.1])

        seed_health(
            db,
            owner,
            doudou,
            [
                {
                    "record_type": "vaccine",
                    "title": "狂犬疫苗",
                    "record_date": TODAY - timedelta(days=330),
                    "next_due_date": TODAY + timedelta(days=35),
                    "note": "年度加强针",
                },
                {
                    "record_type": "deworm",
                    "title": "体内驱虫",
                    "record_date": TODAY - timedelta(days=20),
                    "next_due_date": TODAY + timedelta(days=10),
                    "note": "拜宠清",
                },
                {
                    "record_type": "visit",
                    "title": "年度体检",
                    "record_date": TODAY - timedelta(days=60),
                    "note": "血常规与生化指标正常，建议控制体重。",
                },
            ],
        )
        seed_health(
            db,
            owner,
            niangao,
            [
                {
                    "record_type": "vaccine",
                    "title": "猫三联",
                    "record_date": TODAY - timedelta(days=300),
                    "next_due_date": TODAY + timedelta(days=65),
                },
                {
                    "record_type": "deworm",
                    "title": "体外驱虫",
                    "record_date": TODAY - timedelta(days=15),
                    "next_due_date": TODAY + timedelta(days=15),
                    "note": "大宠爱",
                },
            ],
        )

        if not (
            db.query(BoardingOrder)
            .filter(BoardingOrder.note == "seed-demo")
            .first()
        ):
            completed = BoardingOrder(
                pet_id=doudou.id,
                owner_id=owner.id,
                kennel_id=kennels["K-M-01"].id,
                start_date=TODAY - timedelta(days=24),
                end_date=TODAY - timedelta(days=20),
                status="completed",
                daily_price=88,
                deposit=105.6,
                total_amount=352,
                note="seed-demo",
                confirmed_at=datetime.now() - timedelta(days=26),
                checked_in_at=datetime.now() - timedelta(days=24),
                checked_out_at=datetime.now() - timedelta(days=20),
                created_by=owner.id,
            )
            pending = BoardingOrder(
                pet_id=niangao.id,
                owner_id=owner.id,
                kennel_id=kennels["K-S-02"].id,
                start_date=TODAY + timedelta(days=7),
                end_date=TODAY + timedelta(days=10),
                status="pending",
                daily_price=68,
                deposit=61.2,
                total_amount=204,
                note="seed-demo",
                created_by=owner.id,
            )
            confirmed = BoardingOrder(
                pet_id=cola.id,
                owner_id=owner2.id,
                kennel_id=kennels["K-L-01"].id,
                start_date=TODAY + timedelta(days=2),
                end_date=TODAY + timedelta(days=5),
                status="confirmed",
                daily_price=128,
                deposit=115.2,
                total_amount=384,
                note="seed-demo",
                confirmed_at=datetime.now() - timedelta(days=1),
                created_by=users["staff"].id,
            )
            db.add_all([completed, pending, confirmed])
            db.flush()
            db.add_all(
                [
                    BoardingDailyReport(
                        order_id=completed.id,
                        report_date=TODAY - timedelta(days=23),
                        appetite="good",
                        stool="normal",
                        spirit="good",
                        note="适应得很快，下午在活动区玩了半小时。",
                        photos=[],
                        created_by=users["staff"].id,
                    ),
                    BoardingDailyReport(
                        order_id=completed.id,
                        report_date=TODAY - timedelta(days=22),
                        appetite="normal",
                        stool="normal",
                        spirit="good",
                        note="今天有点想家，多陪它玩了一会儿。",
                        photos=[],
                        created_by=users["staff"].id,
                    ),
                ]
            )
            db.commit()

        print("演示数据准备完成。")
        print("  宠物主：owner / Owner12345")
        print("  宠物主：owner2 / Owner12345")
        print("  寄养员：staff / Staff12345")
        print("  管理员：admin / Admin12345")
        print(f"  笼舍 {len(kennels)} 间，宠物 3 只，订单 3 笔（可重复执行）")
    finally:
        db.close()


if __name__ == "__main__":
    main()
