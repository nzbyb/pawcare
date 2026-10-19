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
