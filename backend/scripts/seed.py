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
from app.models.knowledge import KnowledgeChunk
from app.models.payment import PaymentOrder
from app.models.pet import Pet, WeightRecord
from app.models.user import User
from app.rag.retriever import KNOWLEDGE_CATEGORIES
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

# 合成护理知识库：演示 RAG 检索、引用与拒答。
# 内容是通用护理常识，不构成兽医诊断；embedding 在首次检索时按需生成。
KNOWLEDGE_DOCS = [
    {
        "doc_id": "boarding-prep",
        "category": "boarding",
        "title": "寄养前准备清单",
        "content": (
            "寄养前建议准备：疫苗本和近期驱虫记录；平时吃的粮，按天数分装并多带两天余量；"
            "常用的碗、牵引绳、航空箱或窝垫；正在服用的药物和剂量说明；"
            "写明过敏史、慢性病和紧急联系人。提前三到五天告诉宠物寄养安排，"
            "避免临出门才换环境。入住当天不要把全部零食一次交给寄养员，先确认喂食习惯。"
        ),
        "source": "PawCare 护理知识库 · 寄养指南",
    },
    {
        "doc_id": "boarding-stress",
        "category": "boarding",
        "title": "寄养应激与适应期",
        "content": (
            "猫和狗到陌生环境后可能出现躲藏、少食、软便或夜间叫唤，通常三到五天缓解。"
            "寄养时保留原来的粮和气味熟悉的垫子，前几天减少围观和强行抱抱；"
            "猫优先选择安静、可攀爬的独立空间。若超过两天完全不吃、持续呕吐、"
            "呼吸急促或精神明显沉郁，应联系兽医，不要只当作普通应激。"
        ),
        "source": "PawCare 护理知识库 · 寄养指南",
    },
    {
        "doc_id": "vaccine-dog",
        "category": "vaccine",
        "title": "犬类疫苗与加强针",
        "content": (
            "幼犬通常按兽医方案接种多联疫苗，成年犬一般每年评估一次加强免疫；"
            "狂犬疫苗按当地法规和疫苗说明书定期接种。寄养、美容或去犬舍前，"
            "多数机构会要求狂犬和多联疫苗在有效期内。接种后一周内避免剧烈运动和洗澡，"
            "若出现面部肿胀、持续呕吐或呼吸困难，应立即就医。疫苗时间以疫苗本和兽医记录为准。"
        ),
        "source": "PawCare 护理知识库 · 免疫指南",
    },
    {
        "doc_id": "vaccine-cat",
        "category": "vaccine",
        "title": "猫三联与狂犬疫苗",
        "content": (
            "猫三联覆盖猫瘟、猫鼻支和猫杯状病毒，幼猫需按程序完成基础免疫，"
            "成年猫根据风险和兽医建议加强。狂犬疫苗按当地规定接种。"
            "室内猫也需要基础免疫，因为病毒可能通过鞋底、寄养或外出就医带入。"
            "接种前应确认猫咪当天精神、食欲和体温正常；接种后观察半小时再离开医院。"
        ),
        "source": "PawCare 护理知识库 · 免疫指南",
    },
    {
        "doc_id": "deworm",
        "category": "deworm",
        "title": "体内外驱虫频率",
        "content": (
            "驱虫频率取决于年龄、生活方式和地区：经常外出、接触草地或其他动物的犬猫，"
            "通常需要更规律的体外驱虫；幼宠按兽医方案缩短间隔。"
            "体内驱虫药和体外滴剂不要自行叠加使用，避免成分重复。"
            "驱虫后记录日期和产品名，若出现流口水、呕吐或精神差，联系兽医并带上药品包装。"
        ),
        "source": "PawCare 护理知识库 · 驱虫指南",
    },
    {
        "doc_id": "cat-food-switch",
        "category": "nutrition",
        "title": "猫咪换粮与软便",
        "content": (
            "换粮建议用七到十天逐步过渡：旧粮占多数，每天小幅提高新粮比例。"
            "突然换粮容易引起软便、呕吐或拒食。换粮期间保持饮水充足，"
            "不要同时更换多个品牌或叠加大量零食。若软便超过两天、出现血便、"
            "频繁呕吐或完全不吃，应停止换粮并咨询兽医。"
        ),
        "source": "PawCare 护理知识库 · 营养指南",
    },
    {
        "doc_id": "dog-weight",
        "category": "nutrition",
        "title": "犬只体重管理",
        "content": (
            "判断体重不能只看数字，还要结合品种、体况评分和年龄。"
            "减重应控制每日总热量，零食不超过全天热量的十分之一，并保持规律散步；"
            "不要用断食方式让犬只快速减重。每周固定时间称重，下降速度以每周百分之一到二为宜。"
            "若体重短期明显下降或增加，先排查饮食变化、寄生虫和内分泌问题。"
        ),
        "source": "PawCare 护理知识库 · 营养指南",
    },
    {
        "doc_id": "medication",
        "category": "medication",
        "title": "在家喂药的安全做法",
        "content": (
            "喂药前确认药名、剂量、时间和给药途径，不要凭外观判断药品。"
            "除非兽医明确允许，不要把人用药给宠物，也不要把药混进整盆粮里导致吃不完。"
            "可以用少量湿粮包裹药片，但需确认与药物没有配伍禁忌。"
            "漏服时不要自行加倍补服；记录漏服时间并联系兽医。"
        ),
        "source": "PawCare 护理知识库 · 用药安全",
    },
    {
        "doc_id": "emergency",
        "category": "emergency",
        "title": "需要立即就医的危险信号",
        "content": (
            "呼吸困难、持续抽搐、大量出血、误食异物或有毒物、无法排尿、"
            "持续呕吐腹泻导致脱水、体温明显异常，都属于需要尽快联系兽医的情况。"
            "不要为了观察而拖延，也不要在网上自行催吐，某些腐蚀性物质催吐会造成二次伤害。"
            "就医时带上可能的毒物包装、药物清单和近期疫苗记录。"
        ),
        "source": "PawCare 护理知识库 · 急症指南",
    },
    {
        "doc_id": "senior-pet",
        "category": "senior",
        "title": "老年宠物照护",
        "content": (
            "犬猫进入老年后，建议提高体检频率，关注体重、牙齿、关节、肾脏和心脏指标。"
            "家中可增加防滑垫、低边猫砂盆和容易到达的休息点。"
            "老年宠物对环境和作息变化更敏感，寄养前应提供近期体检报告和用药计划。"
            "出现饮水量明显增加、夜尿、行动迟缓或认知变化时，应预约兽医评估。"
        ),
        "source": "PawCare 护理知识库 · 老年照护",
    },
    {
        "doc_id": "allergy",
        "category": "allergy",
        "title": "食物过敏与皮肤瘙痒",
        "content": (
            "食物过敏可能表现为瘙痒、耳道发红、反复软便或呕吐。"
            "排查通常需要在兽医指导下进行八周左右的单一蛋白或水解蛋白饮食试验，"
            "期间避免所有零食和人食。仅凭一次血检不能直接确诊。"
            "若出现面部肿胀、荨麻疹或呼吸急促，应立即就医。"
        ),
        "source": "PawCare 护理知识库 · 皮肤与过敏",
    },
    {
        "doc_id": "heatstroke",
        "category": "emergency",
        "title": "犬猫中暑的现场处理",
        "content": (
            "高温天气不要把宠物留在车内。出现剧烈喘气、流口水、步态不稳或体温升高时，"
            "先移到阴凉通风处，用常温水打湿腹部和脚垫并保持空气流动，"
            "不要用冰水浸泡或强行灌水。尽快联系兽医，途中避免包裹过厚。"
            "短鼻犬、肥胖犬和老年宠物中暑风险更高。"
        ),
        "source": "PawCare 护理知识库 · 急症指南",
    },
    {
        "doc_id": "cat-carrier",
        "category": "cat",
        "title": "猫咪出行与航空箱适应",
        "content": (
            "航空箱平时就放在家里，垫上熟悉的毛巾，让猫自由进出，不要只在去医院时出现。"
            "出行前几小时避免大量进食；箱门关好后用透气罩布减少视觉刺激。"
            "车内保持平稳和通风，不要打开箱门安抚。到达后先让猫在安静房间适应，"
            "再提供水、猫砂和原来的食物。"
        ),
        "source": "PawCare 护理知识库 · 猫咪照护",
    },
    {
        "doc_id": "multi-pet",
        "category": "boarding",
        "title": "多宠家庭寄养注意事项",
        "content": (
            "多宠家庭寄养时，应在预约备注中写明每只宠物的喂食顺序、是否护食、"
            "能否同笼以及彼此的相处情况。即使平时关系好，也建议分笼或分时段活动，"
            "降低陌生环境下的冲突风险。药物和特殊饮食要分别标注宠物名字，"
            "避免寄养员混淆。"
        ),
        "source": "PawCare 护理知识库 · 寄养指南",
    },
]

assert all(
    item["category"] in KNOWLEDGE_CATEGORIES for item in KNOWLEDGE_DOCS
), "知识库分类不在白名单内"


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


def seed_knowledge(db) -> int:
    created = 0
    for item in KNOWLEDGE_DOCS:
        exists = (
            db.query(KnowledgeChunk)
            .filter(
                KnowledgeChunk.doc_id == item["doc_id"],
                KnowledgeChunk.chunk_index == 0,
            )
            .first()
        )
        if exists:
            continue
        db.add(
            KnowledgeChunk(
                doc_id=item["doc_id"],
                chunk_index=0,
                title=item["title"],
                content=item["content"],
                meta={
                    "category": item["category"],
                    "source": item["source"],
                },
            )
        )
        created += 1
    if created:
        db.commit()
    return created


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        knowledge_count = seed_knowledge(db)
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
                    "next_due_date": TODAY + timedelta(days=3),
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
                deposit=0,
                total_amount=352,
                payment_status="paid",
                paid_amount=352,
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
                deposit=0,
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
                deposit=0,
                total_amount=384,
                note="seed-demo",
                confirmed_at=datetime.now() - timedelta(days=1),
                created_by=users["staff"].id,
            )
            db.add_all([completed, pending, confirmed])
            db.flush()
            db.add(
                PaymentOrder(
                    payment_no="PAY-DEMO-COMPLETED",
                    order_id=completed.id,
                    owner_id=owner.id,
                    channel="mock",
                    amount=352,
                    status="paid",
                    qr_token="seed-demo-token-completed",
                    qr_content="http://localhost:5173/pay/PAY-DEMO-COMPLETED",
                    expires_at=datetime.now() - timedelta(days=20),
                    paid_at=datetime.now() - timedelta(days=24),
                    transaction_id="MOCK-PAY-DEMO-COMPLETED",
                    notify_payload={"channel": "mock", "amount": 352},
                )
            )
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
        print(
            f"  护理知识库 {len(KNOWLEDGE_DOCS)} 篇"
            f"（本次新增 {knowledge_count} 篇，向量首次检索时生成）"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
