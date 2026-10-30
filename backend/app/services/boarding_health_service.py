"""可追溯的寄养前资料核对；规则结果不代表医学诊断或入住许可。"""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.models.health import HealthRecord
from app.models.user import User
from app.services import pet_service


def check_health(db: Session, user: User, pet_id: int, start_date: date, end_date: date) -> dict:
    pet = pet_service.get_pet(db, user, pet_id)
    if end_date <= start_date or (end_date - start_date).days > 60:
        raise BusinessException(message="请选择 1 至 60 晚的寄养日期")
    today = date.today()
    records = (
        db.query(HealthRecord)
        .filter(
            HealthRecord.pet_id == pet.id,
            HealthRecord.deleted_at.is_(None),
            HealthRecord.record_date <= today,
        )
        .order_by(HealthRecord.record_date.desc(), HealthRecord.id.desc())
        .all()
    )
    items = []

    def add(code, title, level, detail, record=None):
        items.append({
            "code": code, "title": title, "level": level, "detail": detail,
            "source_record_id": record.id if record else None,
            "record_date": record.record_date.isoformat() if record else None,
            "next_due_date": record.next_due_date.isoformat() if record and record.next_due_date else None,
        })

    for kind, label in (("vaccine", "疫苗"), ("deworm", "驱虫")):
        # 同名项目的后续记录覆盖旧记录，不用一条新疫苗掩盖其他项目。
        latest = {}
        for record in records:
            if record.record_type == kind:
                latest.setdefault(record.title.strip(), record)
        if not latest:
            add(f"{kind}_missing", f"缺少{label}记录", "warning", f"请补充{label}记录，或携带证明交由寄养员核对。")
        for record in latest.values():
            due = record.next_due_date
            if due is None:
                add(f"{kind}_unknown", record.title, "warning", "未填写下次到期日，请核对有效期。", record)
            elif due <= start_date:
                add(f"{kind}_due", record.title, "warning", "入住前或入住当天已到期，请提前核对并安排处理。", record)
            elif due < end_date:
                add(f"{kind}_during", record.title, "warning", "将在寄养期间到期，请提前与寄养员确认安排。", record)
            else:
                add(f"{kind}_ok", record.title, "ok", "记录中的下次到期日覆盖本次寄养期间。", record)

    if pet.allergies and pet.allergies.strip():
        add("allergies", "过敏信息交接", "warning", f"已记录：{pet.allergies}。请确认食物和用品的避敏安排。")
    else:
        add("allergies_unknown", "过敏信息核对", "info", "档案未填写过敏信息，请在交接时确认；未填写不代表无过敏。")
    symptoms = [r for r in records if r.record_type == "symptom" and r.record_date >= today - timedelta(days=7)]
    for record in symptoms:
        add("recent_symptom", f"近期症状：{record.title}", "warning", "近 7 天有症状记录，请在入住前核实是否恢复，必要时咨询兽医。", record)

    warnings = sum(item["level"] == "warning" for item in items)
    return {
        "pet_id": pet.id, "pet_name": pet.name,
        "start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "checked_on": today.isoformat(),
        "status": "attention" if warnings else "ready", "warning_count": warnings,
        "items": items,
        "summary": f"有 {warnings} 项需要提前核对" if warnings else "未发现已记录的到期风险，入住时仍需核对原始资料",
        "notice": "依据已录入资料生成，不替代兽医诊断，也不代表已获准入住。",
    }
