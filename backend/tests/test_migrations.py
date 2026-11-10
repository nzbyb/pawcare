import os
import sqlite3
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _alembic(tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    db_path = tmp_path / "migration.db"
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    env["JWT_SECRET_KEY"] = "migration_test_secret_" + "x" * 40
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _tables(db_path: Path) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        return {
            row[0]
            for row in conn.execute(
                "select name from sqlite_master where type='table'"
            )
        }


def test_migrations_upgrade_and_downgrade(tmp_path: Path) -> None:
    db_path = tmp_path / "migration.db"

    upgraded = _alembic(tmp_path, "upgrade", "head")
    assert upgraded.returncode == 0, upgraded.stderr
    assert {
        "alembic_version",
        "users",
        "pets",
        "boarding_orders",
        "knowledge_chunks",
    } <= _tables(db_path)

    # 迁移必须可重复执行（容器每次启动都会跑一遍）。
    again = _alembic(tmp_path, "upgrade", "head")
    assert again.returncode == 0, again.stderr

    downgraded = _alembic(tmp_path, "downgrade", "base")
    assert downgraded.returncode == 0, downgraded.stderr
    remaining = _tables(db_path)
    assert "users" not in remaining
    assert "boarding_orders" not in remaining


def test_upgrade_backfills_knowledge_documents(tmp_path: Path) -> None:
    """旧库只有切片表时，升级要把切片反推成文档，不能丢内容。"""
    db_path = tmp_path / "migration.db"

    before = _alembic(tmp_path, "upgrade", "c7e2a4d9b1f6")
    assert before.returncode == 0, before.stderr

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO knowledge_chunks "
            "(create_time, update_time, doc_id, chunk_index, title, content, embedding, meta) "
            "VALUES (datetime('now'), datetime('now'), ?, 0, ?, ?, NULL, ?)",
            (
                "legacy-doc",
                "旧版寄养指南",
                "寄养前准备疫苗本。入住当天确认喂食习惯。",
                '{"category": "boarding", "source": "旧知识库"}',
            ),
        )
        conn.commit()

    upgraded = _alembic(tmp_path, "upgrade", "head")
    assert upgraded.returncode == 0, upgraded.stderr

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT category, title, content, source, status, chunk_count "
            "FROM knowledge_documents WHERE doc_id = 'legacy-doc'"
        ).fetchone()

    assert row is not None
    category, title, content, source, status, chunk_count = row
    assert category == "boarding"
    assert title == "旧版寄养指南"
    assert content == "寄养前准备疫苗本。入住当天确认喂食习惯。"
    assert source == "旧知识库"
    assert status == "published"
    assert chunk_count == 1


def test_upgrade_backfills_abnormal_cases(tmp_path: Path) -> None:
    """旧库的异常日报要补成处置单：今天的待处置，历史的标为已补录。"""
    from datetime import date, timedelta

    db_path = tmp_path / "migration.db"
    before = _alembic(tmp_path, "upgrade", "a8d3f1c6b7e2")
    assert before.returncode == 0, before.stderr

    old_day = (date.today() - timedelta(days=30)).isoformat()
    rows = ((old_day, "poor", "diarrhea"), (date.today().isoformat(), "normal", "soft"))
    with sqlite3.connect(db_path) as conn:
        for report_date, appetite, stool in rows:
            conn.execute(
                "INSERT INTO boarding_daily_reports "
                "(create_time, update_time, order_id, report_date, appetite, stool, spirit, note, photos) "
                "VALUES (datetime('now'), datetime('now'), 1, ?, ?, ?, 'good', '旧日报', NULL)",
                (report_date, appetite, stool),
            )
        conn.commit()

    upgraded = _alembic(tmp_path, "upgrade", "head")
    assert upgraded.returncode == 0, upgraded.stderr

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT r.report_date, c.severity, c.status, c.action_taken, c.reasons "
            "FROM boarding_abnormal_cases c "
            "JOIN boarding_daily_reports r ON r.id = c.report_id "
            "ORDER BY r.report_date"
        ).fetchall()

    assert len(rows) == 2
    old_date, old_severity, old_status, old_action, old_reasons = rows[0]
    assert old_date == old_day
    # 腹泻 + 食欲较差 → 紧急
    assert old_severity == "critical"
    assert old_status == "resolved"
    assert old_action == "历史日报补录：未记录处置过程"
    assert "stool_diarrhea" in old_reasons

    _, today_severity, today_status, today_action, today_reasons = rows[1]
    assert today_severity == "warning"
    assert today_status == "open"
    assert today_action is None
    assert "stool_soft" in today_reasons
