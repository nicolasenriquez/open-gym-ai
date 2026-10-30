"""Owner-scoped forgetting; no new privileged or global access."""

from alembic import op

revision = "p003_coach_lifecycle"
down_revision = "p003_coach_http"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "GRANT INSERT (owner_id,sharing,forget_generation), UPDATE (sharing,forget_generation) ON coach.profile_state TO opengym_api_runtime"
    )
    op.execute("GRANT DELETE ON coach.daily_usage TO opengym_api_runtime")


def downgrade():
    raise RuntimeError("PLATFORM_MIGRATION_FORWARD_ONLY")
