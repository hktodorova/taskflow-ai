"""Initial TaskFlow AI schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(40), nullable=False),
        sa.Column("email", sa.String(160), nullable=False),
        sa.Column("full_name", sa.String(120), nullable=True),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("password_hash", sa.String(128), nullable=False),
        sa.Column("api_token", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("username"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("api_token"),
    )
    op.create_index(op.f("ix_users_id"), "users", ["id"])
    op.create_index(op.f("ix_users_username"), "users", ["username"])
    op.create_index(op.f("ix_users_email"), "users", ["email"])
    op.create_index(op.f("ix_users_role"), "users", ["role"])

    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_teams_id"), "teams", ["id"])
    op.create_index(op.f("ix_teams_name"), "teams", ["name"])

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_projects_id"), "projects", ["id"])
    op.create_index(op.f("ix_projects_name"), "projects", ["name"])
    op.create_index(op.f("ix_projects_team_id"), "projects", ["team_id"])

    op.create_table(
        "team_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.UniqueConstraint("team_id", "user_id", name="uq_team_members_team_user"),
    )
    op.create_index(op.f("ix_team_members_team_id"), "team_members", ["team_id"])
    op.create_index(op.f("ix_team_members_user_id"), "team_members", ["user_id"])

    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("priority", sa.String(10), nullable=False),
        sa.Column("status", sa.String(15), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("estimated_minutes", sa.Integer(), nullable=False),
        sa.Column("actual_minutes", sa.Integer(), nullable=False),
        sa.Column("tags", sa.String(250), nullable=False),
        sa.Column("ai_notes", sa.Text(), nullable=True),
        sa.Column("blocked_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    for col in ["id", "title", "priority", "status", "due_date", "project_id", "owner_id"]:
        op.create_index(op.f(f"ix_tasks_{col}"), "tasks", [col])

    op.create_table("subtasks", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id"), nullable=False), sa.Column("title", sa.String(120), nullable=False), sa.Column("done", sa.Boolean(), nullable=False))
    op.create_index(op.f("ix_subtasks_id"), "subtasks", ["id"])
    op.create_index(op.f("ix_subtasks_task_id"), "subtasks", ["task_id"])

    op.create_table("comments", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id"), nullable=False), sa.Column("author", sa.String(80), nullable=False), sa.Column("body", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=True))
    op.create_index(op.f("ix_comments_id"), "comments", ["id"])
    op.create_index(op.f("ix_comments_task_id"), "comments", ["task_id"])

    op.create_table("task_dependencies", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id"), nullable=False), sa.Column("depends_on_task_id", sa.Integer(), sa.ForeignKey("tasks.id"), nullable=False))
    op.create_index(op.f("ix_task_dependencies_task_id"), "task_dependencies", ["task_id"])
    op.create_index(op.f("ix_task_dependencies_depends_on_task_id"), "task_dependencies", ["depends_on_task_id"])

    op.create_table("email_notifications", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("recipient", sa.String(160), nullable=False), sa.Column("subject", sa.String(160), nullable=False), sa.Column("body", sa.Text(), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=True), sa.Column("sent_at", sa.DateTime(), nullable=True))
    op.create_index(op.f("ix_email_notifications_id"), "email_notifications", ["id"])
    op.create_index(op.f("ix_email_notifications_recipient"), "email_notifications", ["recipient"])
    op.create_index(op.f("ix_email_notifications_status"), "email_notifications", ["status"])

    op.create_table("background_jobs", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("job_type", sa.String(40), nullable=True), sa.Column("payload", sa.Text(), nullable=True), sa.Column("status", sa.String(20), nullable=True), sa.Column("result", sa.Text(), nullable=True), sa.Column("created_at", sa.DateTime(), nullable=True), sa.Column("processed_at", sa.DateTime(), nullable=True))
    op.create_index(op.f("ix_background_jobs_id"), "background_jobs", ["id"])
    op.create_index(op.f("ix_background_jobs_job_type"), "background_jobs", ["job_type"])
    op.create_index(op.f("ix_background_jobs_status"), "background_jobs", ["status"])

    op.create_table("activity_logs", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("entity_type", sa.String(30), nullable=True), sa.Column("entity_id", sa.Integer(), nullable=True), sa.Column("action", sa.String(40), nullable=True), sa.Column("details", sa.Text(), nullable=True), sa.Column("created_at", sa.DateTime(), nullable=True))
    op.create_index(op.f("ix_activity_logs_id"), "activity_logs", ["id"])
    op.create_index(op.f("ix_activity_logs_entity_type"), "activity_logs", ["entity_type"])
    op.create_index(op.f("ix_activity_logs_entity_id"), "activity_logs", ["entity_id"])
    op.create_index(op.f("ix_activity_logs_action"), "activity_logs", ["action"])


def downgrade() -> None:
    for table in ["activity_logs", "background_jobs", "email_notifications", "task_dependencies", "comments", "subtasks", "tasks", "team_members", "projects", "teams", "users"]:
        op.drop_table(table)
