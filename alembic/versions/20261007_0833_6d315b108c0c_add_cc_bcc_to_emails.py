"""add cc_bcc to emails

Revision ID: 6d315b108c0c
Revises: 9bd05ff0fa81
Create Date: 2026-10-07 08:33:10.112145+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '6d315b108c0c'
down_revision: Union[str, Sequence[str], None] = '9bd05ff0fa81'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('emails', sa.Column('cc_emails', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('emails', sa.Column('bcc_emails', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('emails', 'bcc_emails')
    op.drop_column('emails', 'cc_emails')
