"""add boarding abnormal cases

Revision ID: e9b7c3d1a4f2
Revises: a8d3f1c6b7e2

日报异常此前只在「今日任务」里标红，看过就没了。这里增加处置单表，
把「发现—认领—处置—告知」落成可追踪的业务对象：一条日报最多一张单。

回填写法：今天的异常日报补成待处置，更早的补成已完成并注明「历史日报补录」，
避免升级后突然冒出一批积压待办。
"""
import json
from datetime import date, datetime

from alembic import op
import sqlalchemy as sa

revision = "e9b7c3d1a4f2"
down_revision = "a8d3f1c6b7e2"
branch_labels = None
depends_on = None

CRITICAL_REASONS = ("stool_diarrhea", "spirit_low")
HISTORY_NOTE = "历史日报补录：未记录处置过程"


def _reasons(appetite, stool, spirit):
    reasons = []
    if appetite == "poor":
        reasons.append("appetite_poor")
    if stool == "soft":
        reasons.append("stool_soft")
    elif stool == "diarrhea":
        reasons.append("stool_diarrhea")
    if spirit == "low":
        reasons.append("spirit_low")
    return reasons


def _as_datetime(value, fallback):
    """SQLite 把 datetime 读成字符串，MySQL 读成 datetime，两种都要能落库。"""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return fallback
    return fallback


def _backfill_cases(conn) -> None:
    rows = conn.execute(
        sa.text(
            "SELECT id, order_id, report_date, appetite, stool, spirit, create_time "
            "FROM boarding_daily_reports "
            "WHERE appetite = 'poor' OR stool IN ('soft', 'diarrhea') OR spirit = 'low' "
            "ORDER BY id"
        )
    ).mappings()

    today = date.today()
    now = datetime.now()
    records = []
    for row in rows:
        reasons = _reasons(row["appetite"], row["stool"], row["spirit"])
        if not reasons:
            continue
        severity = (
            "critical"
            if any(reason in CRITICAL_REASONS for reason in reasons) or len(reasons) >= 2
            else "warning"
        )
        report_date = row["report_date"]
        if isinstance(report_date, str):
            try:
                report_date = date.fromisoformat(report_date[:10])
            except ValueError:
                report_date = today
        pending = report_date >= today
        created_at = _as_datetime(row["create_time"], now)
        records.append(
            {
                "order_id": row["order_id"],
                "report_id": row["id"],
                "severity": severity,
                "reasons": json.dumps(reasons, ensure_ascii=False),
                "status": "open" if pending else "resolved",
                "action_taken": None if pending else HISTORY_NOTE,
                "resolved_at": None if pending else created_at,
                "vet_contacted": False,
                "owner_notified": False,
                "create_time": created_at,
                "update_time": created_at,
            }
        )

    if records:
        op.bulk_insert(
            sa.table(
                "boarding_abnormal_cases",
                sa.column("order_id", sa.Integer),
                sa.column("report_id", sa.Integer),
                sa.column("severity", sa.String),
                sa.column("reasons", sa.JSON),
                sa.column("status", sa.String),
                sa.column("action_taken", sa.Text),
                sa.column("resolved_at", sa.DateTime),
                sa.column("vet_contacted", sa.Boolean),
                sa.column("owner_notified", sa.Boolean),
                sa.column("create_time", sa.DateTime),
                sa.column("update_time", sa.DateTime),
            ),
            records,
        )


def upgrade():
    op.create_table(
        "boarding_abnormal_cases",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "order_id",
            sa.Integer(),
            sa.ForeignKey("boarding_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "report_id",
            sa.Integer(),
            sa.ForeignKey("boarding_daily_reports.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("severity", sa.String(length=20), nullable=False, server_default="warning"),
        sa.Column("reasons", sa.JSON()),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column(
            "handler_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("claimed_at", sa.DateTime()),
        sa.Column("resolved_at", sa.DateTime()),
        sa.Column("action_taken", sa.Text()),
        sa.Column("vet_contacted", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("owner_notified", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column(
            "resolved_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("create_time", sa.DateTime()),
        sa.Column("update_time", sa.DateTime()),
        comment="异常日报处置单",
    )
    op.create_index(
        "ix_boarding_abnormal_cases_order_id", "boarding_abnormal_cases", ["order_id"]
    )
    op.create_index(
        "ix_boarding_abnormal_cases_report_id",
        "boarding_abnormal_cases",
        ["report_id"],
        unique=True,
    )
    op.create_index(
        "ix_boarding_abnormal_cases_severity", "boarding_abnormal_cases", ["severity"]
    )
    op.create_index(
        "ix_boarding_abnormal_cases_status", "boarding_abnormal_cases", ["status"]
    )
    op.create_index(
        "ix_boarding_abnormal_cases_handler_id",
        "boarding_abnormal_cases",
        ["handler_id"],
    )
    op.create_index(
        "ix_abnormal_cases_status_time",
        "boarding_abnormal_cases",
        ["status", "create_time"],
    )

    _backfill_cases(op.get_bind())


def downgrade():
    op.drop_index(
        "ix_abnormal_cases_status_time", table_name="boarding_abnormal_cases"
    )
    op.drop_index(
        "ix_boarding_abnormal_cases_handler_id", table_name="boarding_abnormal_cases"
    )
    op.drop_index(
        "ix_boarding_abnormal_cases_status", table_name="boarding_abnormal_cases"
    )
    op.drop_index(
        "ix_boarding_abnormal_cases_severity", table_name="boarding_abnormal_cases"
    )
    op.drop_index(
        "ix_boarding_abnormal_cases_report_id", table_name="boarding_abnormal_cases"
    )
    op.drop_index(
        "ix_boarding_abnormal_cases_order_id", table_name="boarding_abnormal_cases"
    )
    op.drop_table("boarding_abnormal_cases")
