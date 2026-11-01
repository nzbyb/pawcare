"""系统设置：门店信息等少量键值配置。

只允许 schema 里声明的键，取值以数据库为准、缺省回落到默认值；
管理端整体保存，前台（帮助与反馈页）只读公开字段。
"""

from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.models.audit import AuditLog
from app.models.system import SystemSetting
from app.models.user import User
from app.schemas.system import SettingUpdateItem

# key -> (默认值, 说明)。新增设置项要同步这里和 schemas.system.SettingKey。
DEFAULT_SETTINGS: dict[str, tuple[str, str]] = {
    "store_name": ("PawCare 宠物寄养中心", "门店名称，显示在帮助与反馈页"),
    "service_phone": ("400-000-0000", "客服电话（演示占位，可在系统设置中修改）"),
    "store_address": ("", "门店地址，留空时前台显示未设置"),
    "business_hours": ("每天 08:00 - 21:00", "营业时间"),
    "booking_notice": (
        "建议提前 7 天预约；入住当天请携带免疫记录，门店会核对疫苗与驱虫有效期。",
        "预约须知，显示在服务指南",
    ),
}

# 电话、营业时间这类短字段额外限长，避免把长文本塞进页脚。
SHORT_VALUE_KEYS = {"store_name": 60, "service_phone": 40, "business_hours": 60}


def list_settings(db: Session) -> list[dict]:
    rows = {row.key: row for row in db.query(SystemSetting).all()}
    items = []
    for key, (default, description) in DEFAULT_SETTINGS.items():
        row = rows.get(key)
        items.append(
            {
                "key": key,
                "value": row.value if row else default,
                "description": description,
                "update_time": row.update_time if row else None,
            }
        )
    return items


def public_settings(db: Session) -> dict[str, str]:
    """前台可读的设置项；未写入数据库时返回默认值。"""
    rows = dict(
        db.query(SystemSetting.key, SystemSetting.value)
        .filter(SystemSetting.key.in_(tuple(DEFAULT_SETTINGS)))
        .all()
    )
    return {
        key: rows.get(key, default) for key, (default, _) in DEFAULT_SETTINGS.items()
    }


def update_settings(
    db: Session, admin: User, items: list[SettingUpdateItem]
) -> list[dict]:
    rows = {row.key: row for row in db.query(SystemSetting).all()}
    changed: dict[str, dict[str, str]] = {}

    for item in items:
        key = item.key
        if key not in DEFAULT_SETTINGS:
            raise BusinessException(message=f"不支持的设置项：{key}")
        value = item.value.strip()
        limit = SHORT_VALUE_KEYS.get(key)
        if limit and len(value) > limit:
            raise BusinessException(message=f"{DEFAULT_SETTINGS[key][1]}不能超过 {limit} 个字")

        row = rows.get(key)
        before = row.value if row else DEFAULT_SETTINGS[key][0]
        if value == before:
            continue

        if row is None:
            db.add(
                SystemSetting(
                    key=key,
                    value=value,
                    description=DEFAULT_SETTINGS[key][1],
                    updated_by=admin.id,
                )
            )
        else:
            row.value = value
            row.updated_by = admin.id
        changed[key] = {"before": before, "after": value}

    if not changed:
        return list_settings(db)

    db.add(
        AuditLog(
            actor_id=admin.id,
            action="setting.update",
            target_type="system_setting",
            before_data={key: value["before"] for key, value in changed.items()},
            after_data={key: value["after"] for key, value in changed.items()},
        )
    )
    db.commit()
    return list_settings(db)
