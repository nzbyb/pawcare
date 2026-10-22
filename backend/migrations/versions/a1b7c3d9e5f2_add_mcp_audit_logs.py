"""add mcp audit logs

Revision ID: a1b7c3d9e5f2
Revises: c4e8b1f6a2d9
Create Date: 2026-10-22 20:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b7c3d9e5f2'
down_revision: Union[str, None] = 'c4e8b1f6a2d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'mcp_audit_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='主键ID'),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('transport', sa.String(length=16), nullable=False, comment='http / stdio'),
        sa.Column('tool_name', sa.String(length=64), nullable=False),
        sa.Column('arguments', sa.JSON(), nullable=True, comment='参数摘要，超长截断'),
        sa.Column('status', sa.String(length=16), nullable=False, comment='ok / error / denied / timeout'),
        sa.Column('error_code', sa.String(length=16), nullable=True),
        sa.Column('elapsed_ms', sa.Integer(), nullable=True),
        sa.Column('ip', sa.String(length=64), nullable=True),
        sa.Column('trace_id', sa.String(length=64), nullable=True),
        sa.Column('create_time', sa.DateTime(), nullable=False, comment='创建时间'),
        sa.Column('update_time', sa.DateTime(), nullable=False, comment='更新时间'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        comment='MCP 工具调用审计',
    )
    op.create_index(
        op.f('ix_mcp_audit_logs_user_id'), 'mcp_audit_logs', ['user_id'], unique=False
    )
    op.create_index(
        op.f('ix_mcp_audit_logs_tool_name'), 'mcp_audit_logs', ['tool_name'], unique=False
    )
    op.create_index(
        op.f('ix_mcp_audit_logs_status'), 'mcp_audit_logs', ['status'], unique=False
    )
    op.create_index(
        op.f('ix_mcp_audit_logs_trace_id'), 'mcp_audit_logs', ['trace_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_mcp_audit_logs_trace_id'), table_name='mcp_audit_logs')
    op.drop_index(op.f('ix_mcp_audit_logs_status'), table_name='mcp_audit_logs')
    op.drop_index(op.f('ix_mcp_audit_logs_tool_name'), table_name='mcp_audit_logs')
    op.drop_index(op.f('ix_mcp_audit_logs_user_id'), table_name='mcp_audit_logs')
    op.drop_table('mcp_audit_logs')
