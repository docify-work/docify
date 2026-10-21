"""security hardening columns

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-21 17:34:41.313974
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0002'
down_revision: str | None = '0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('email_tokens', sa.Column('password_hash', sa.String(length=255), nullable=True))
    op.add_column('oauth_states', sa.Column('browser_hmac', sa.LargeBinary(), nullable=True))
    op.add_column('workspace_installations', sa.Column('allowed_repo_ids', sa.ARRAY(sa.BigInteger()), server_default=sa.text("'{}'"), nullable=False))


def downgrade() -> None:
    op.drop_column('workspace_installations', 'allowed_repo_ids')
    op.drop_column('oauth_states', 'browser_hmac')
    op.drop_column('email_tokens', 'password_hash')
