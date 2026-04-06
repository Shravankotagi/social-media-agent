"""
alembic/versions/001_initial_schema.py — Initial database schema migration.
"""
from alembic import op
import sqlalchemy as sa

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("linkedin_url", sa.String(500)),
        sa.Column("twitter_url", sa.String(500)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "profile_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("report_json", sa.Text(2**24)),
        sa.Column("status", sa.Enum("pending", "complete", "failed"), default="pending"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "competitor_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("report_json", sa.Text(2**24)),
        sa.Column("status", sa.Enum("pending", "complete", "failed"), default="pending"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "content_calendars",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("title", sa.String(255)),
        sa.Column("start_date", sa.Date),
        sa.Column("end_date", sa.Date),
        sa.Column("calendar_json", sa.Text(2**24)),
        sa.Column("status", sa.Enum("draft", "under_review", "approved", "locked"), default="draft"),
        sa.Column("review_notes", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "calendar_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("calendar_id", sa.String(36), sa.ForeignKey("content_calendars.id", ondelete="CASCADE")),
        sa.Column("day_number", sa.Integer),
        sa.Column("scheduled_date", sa.Date),
        sa.Column("platform", sa.Enum("linkedin", "twitter", "both")),
        sa.Column("topic", sa.String(500)),
        sa.Column("format", sa.String(100)),
        sa.Column("posting_time", sa.Time),
        sa.Column("status", sa.Enum(
            "planned", "content_generated", "approved", "published", "failed"
        ), default="planned"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "posts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("entry_id", sa.String(36), sa.ForeignKey("calendar_entries.id", ondelete="CASCADE")),
        sa.Column("body_copy", sa.Text(2**24)),
        sa.Column("hashtags", sa.Text),
        sa.Column("visual_prompt", sa.Text(2**24)),
        sa.Column("visual_url", sa.String(500)),
        sa.Column("copy_status", sa.Enum("pending", "approved", "regenerate"), default="pending"),
        sa.Column("hashtag_status", sa.Enum("pending", "approved", "regenerate"), default="pending"),
        sa.Column("visual_status", sa.Enum("pending", "approved", "regenerate"), default="pending"),
        sa.Column("publish_status", sa.Enum("draft", "queued", "posted", "failed"), default="draft"),
        sa.Column("published_at", sa.DateTime),
        sa.Column("platform_post_id", sa.String(255)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "post_metrics",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("post_id", sa.String(36), sa.ForeignKey("posts.id", ondelete="CASCADE")),
        sa.Column("impressions", sa.Integer, default=0),
        sa.Column("reactions", sa.Integer, default=0),
        sa.Column("comments", sa.Integer, default=0),
        sa.Column("shares", sa.Integer, default=0),
        sa.Column("polled_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("stage", sa.String(100)),
        sa.Column("status", sa.Enum("running", "success", "failed"), default="running"),
        sa.Column("token_usage", sa.Integer, default=0),
        sa.Column("latency_ms", sa.Integer, default=0),
        sa.Column("error_message", sa.Text),
        sa.Column("started_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime),
    )

    op.create_table(
        "hitl_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("session_type", sa.Enum("calendar_review", "content_review")),
        sa.Column("reference_id", sa.String(36)),
        sa.Column("messages_json", sa.Text(2**24)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    for table in [
        "hitl_sessions", "pipeline_runs", "post_metrics",
        "posts", "calendar_entries", "content_calendars",
        "competitor_reports", "profile_reports", "users",
    ]:
        op.drop_table(table)
