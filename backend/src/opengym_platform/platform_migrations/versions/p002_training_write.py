"""Owner-scoped canonical writes; derived metadata remains read-only."""

from alembic import op

revision = "p002_training_write"
down_revision = "p002_training"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "GRANT INSERT (owner_id, document), UPDATE (document) "
        "ON training.documents TO opengym_api_runtime"
    )


def downgrade():
    raise RuntimeError("PLATFORM_MIGRATION_FORWARD_ONLY")
