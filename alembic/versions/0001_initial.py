"""initial tables

Revision ID: 0001_initial
Revises: 
Create Date: 2025-10-22
"""
from alembic import op
import sqlalchemy as sa
import os

# revision identifiers, used by Alembic.
revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__),'..','..'))
    schema_path = os.path.join(base_dir,'app','db','postgres_schema.sql')
    with open(schema_path,'r') as f:
        op.execute(f.read())


def downgrade():
    for tbl in ['tasks','employees','branches','designations']:
        try:
            op.drop_table(tbl)
        except Exception:
            pass
