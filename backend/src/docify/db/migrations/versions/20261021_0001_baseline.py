"""baseline

Revision ID: 0001
Revises:
Create Date: 2026-10-21 15:21:13.264745
"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Extensions: no-ops in the cloud (db-bootstrap Job creates them as superuser).
    for ext in ("vector", "pg_trgm", "citext"):
        op.execute(f"CREATE EXTENSION IF NOT EXISTS {ext}")
    op.create_table('singletons',
    sa.Column('name', sa.String(length=60), nullable=False),
    sa.Column('owner', sa.String(length=100), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('name', name=op.f('pk_singletons'))
    )
    op.create_table('users',
    sa.Column('email', postgresql.CITEXT(), nullable=False),
    sa.Column('email_verified', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=True),
    sa.Column('avatar_url', sa.String(length=500), nullable=True),
    sa.Column('password_hash', sa.String(length=255), nullable=True),
    sa.Column('disabled', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('session_gen', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    sa.UniqueConstraint('email', name=op.f('uq_users_email'))
    )
    op.create_table('webhook_deliveries',
    sa.Column('delivery_id', sa.String(length=100), nullable=False),
    sa.Column('event', sa.String(length=60), nullable=False),
    sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('delivery_id', name=op.f('pk_webhook_deliveries'))
    )
    op.create_table('workspaces',
    sa.Column('slug', sa.String(length=60), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('is_public_demo', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('settings', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text('\'{"auto_publish": true, "chat_enabled": true}\'::jsonb'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_workspaces')),
    sa.UniqueConstraint('slug', name=op.f('uq_workspaces_slug'))
    )
    op.create_table('audit_events',
    sa.Column('workspace_id', sa.UUID(), nullable=True),
    sa.Column('actor_user_id', sa.UUID(), nullable=True),
    sa.Column('action', sa.String(length=60), nullable=False),
    sa.Column('target', sa.String(length=200), nullable=True),
    sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], name=op.f('fk_audit_events_actor_user_id_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name=op.f('fk_audit_events_workspace_id_workspaces'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_events'))
    )
    op.create_index('ix_audit_ws_created', 'audit_events', ['workspace_id', 'created_at'], unique=False)
    op.create_table('auth_identities',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('provider', sa.String(length=20), nullable=False),
    sa.Column('provider_user_id', sa.String(length=100), nullable=False),
    sa.Column('email', postgresql.CITEXT(), nullable=True),
    sa.Column('email_verified', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('login', sa.String(length=100), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("provider IN ('github', 'google')", name=op.f('ck_auth_identities_provider')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_auth_identities_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_auth_identities')),
    sa.UniqueConstraint('provider', 'provider_user_id', name=op.f('uq_auth_identities_provider_provider_user_id'))
    )
    op.create_index(op.f('ix_auth_identities_user_id'), 'auth_identities', ['user_id'], unique=False)
    op.create_table('chat_threads',
    sa.Column('workspace_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=True),
    sa.Column('title', sa.String(length=200), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_chat_threads_user_id_users'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name=op.f('fk_chat_threads_workspace_id_workspaces'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_chat_threads'))
    )
    op.create_index(op.f('ix_chat_threads_user_id'), 'chat_threads', ['user_id'], unique=False)
    op.create_index(op.f('ix_chat_threads_workspace_id'), 'chat_threads', ['workspace_id'], unique=False)
    op.create_table('email_tokens',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('purpose', sa.String(length=20), nullable=False),
    sa.Column('token_hmac', sa.LargeBinary(), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("purpose IN ('verify', 'reset', 'signup_notice')", name=op.f('ck_email_tokens_purpose')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_email_tokens_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_email_tokens')),
    sa.UniqueConstraint('token_hmac', name=op.f('uq_email_tokens_token_hmac'))
    )
    op.create_index(op.f('ix_email_tokens_user_id'), 'email_tokens', ['user_id'], unique=False)
    op.create_table('github_installations',
    sa.Column('installation_id', sa.BigInteger(), nullable=False),
    sa.Column('account_login', sa.String(length=100), nullable=False),
    sa.Column('account_type', sa.String(length=20), nullable=False),
    sa.Column('repository_selection', sa.String(length=20), nullable=True),
    sa.Column('permissions', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('installed_by_user_id', sa.UUID(), nullable=True),
    sa.Column('suspended_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['installed_by_user_id'], ['users.id'], name=op.f('fk_github_installations_installed_by_user_id_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_github_installations')),
    sa.UniqueConstraint('installation_id', name=op.f('uq_github_installations_installation_id'))
    )
    op.create_table('invites',
    sa.Column('workspace_id', sa.UUID(), nullable=False),
    sa.Column('email', postgresql.CITEXT(), nullable=False),
    sa.Column('role', sa.String(length=10), nullable=False),
    sa.Column('token_hmac', sa.LargeBinary(), nullable=False),
    sa.Column('invited_by', sa.UUID(), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("role IN ('admin', 'member')", name=op.f('ck_invites_role')),
    sa.ForeignKeyConstraint(['invited_by'], ['users.id'], name=op.f('fk_invites_invited_by_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name=op.f('fk_invites_workspace_id_workspaces'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_invites')),
    sa.UniqueConstraint('token_hmac', name=op.f('uq_invites_token_hmac'))
    )
    op.create_index('uq_invites_open_email', 'invites', ['workspace_id', 'email'], unique=True, postgresql_where=sa.text('accepted_at IS NULL AND revoked_at IS NULL'))
    op.create_table('llm_usage',
    sa.Column('workspace_id', sa.UUID(), nullable=True),
    sa.Column('job_id', sa.UUID(), nullable=True),
    sa.Column('purpose', sa.String(length=30), nullable=False),
    sa.Column('provider', sa.String(length=20), nullable=False),
    sa.Column('model', sa.String(length=60), nullable=False),
    sa.Column('input_tokens', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('output_tokens', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('cache_read_tokens', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('cost_usd', sa.Numeric(precision=10, scale=6), server_default=sa.text('0'), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name=op.f('fk_llm_usage_workspace_id_workspaces'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_llm_usage'))
    )
    op.create_index('ix_llm_usage_created', 'llm_usage', ['created_at'], unique=False)
    op.create_index('ix_llm_usage_ws_created', 'llm_usage', ['workspace_id', 'created_at'], unique=False)
    op.create_table('memberships',
    sa.Column('workspace_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('role', sa.String(length=10), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("role IN ('admin', 'member')", name=op.f('ck_memberships_role')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_memberships_user_id_users'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name=op.f('fk_memberships_workspace_id_workspaces'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_memberships')),
    sa.UniqueConstraint('workspace_id', 'user_id', name=op.f('uq_memberships_workspace_id_user_id'))
    )
    op.create_index(op.f('ix_memberships_user_id'), 'memberships', ['user_id'], unique=False)
    op.create_table('repositories',
    sa.Column('workspace_id', sa.UUID(), nullable=False),
    sa.Column('installation_id', sa.BigInteger(), nullable=False),
    sa.Column('github_repo_id', sa.BigInteger(), nullable=False),
    sa.Column('owner', sa.String(length=100), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('full_name', sa.String(length=201), nullable=False),
    sa.Column('default_branch', sa.String(length=255), nullable=False),
    sa.Column('indexed_branch', sa.String(length=255), nullable=True),
    sa.Column('private', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('archived', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('status', sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
    sa.Column('last_processed_sha', sa.String(length=40), nullable=True),
    sa.Column('last_full_index_sha', sa.String(length=40), nullable=True),
    sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('size_kb', sa.Integer(), nullable=True),
    sa.Column('error', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('sync_lease_owner', sa.String(length=100), nullable=True),
    sa.Column('sync_lease_expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("status IN ('pending', 'indexing', 'ready', 'error', 'empty', 'too_large', 'disconnected', 'suspended')", name=op.f('ck_repositories_status')),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name=op.f('fk_repositories_workspace_id_workspaces'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_repositories')),
    sa.UniqueConstraint('github_repo_id', name=op.f('uq_repositories_github_repo_id'))
    )
    op.create_index(op.f('ix_repositories_workspace_id'), 'repositories', ['workspace_id'], unique=False)
    op.create_table('sessions',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('token_hmac', sa.LargeBinary(), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('absolute_expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('ip', sa.String(length=64), nullable=True),
    sa.Column('user_agent', sa.String(length=300), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_sessions_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_sessions')),
    sa.UniqueConstraint('token_hmac', name=op.f('uq_sessions_token_hmac'))
    )
    op.create_index(op.f('ix_sessions_expires_at'), 'sessions', ['expires_at'], unique=False)
    op.create_index(op.f('ix_sessions_user_id'), 'sessions', ['user_id'], unique=False)
    op.create_table('changelog_entries',
    sa.Column('workspace_id', sa.UUID(), nullable=False),
    sa.Column('repo_id', sa.UUID(), nullable=False),
    sa.Column('from_sha', sa.String(length=40), nullable=True),
    sa.Column('to_sha', sa.String(length=40), nullable=False),
    sa.Column('content_md', sa.Text(), nullable=False),
    sa.Column('pr_numbers', sa.ARRAY(sa.Integer()), server_default=sa.text("'{}'"), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('job_id', sa.UUID(), nullable=True),
    sa.Column('reviewed_by', sa.UUID(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('tsv', postgresql.TSVECTOR(), sa.Computed("to_tsvector('english', content_md)", persisted=True), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("status IN ('published', 'pending_review', 'rejected')", name=op.f('ck_changelog_entries_status')),
    sa.ForeignKeyConstraint(['repo_id'], ['repositories.id'], name=op.f('fk_changelog_entries_repo_id_repositories'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], name=op.f('fk_changelog_entries_reviewed_by_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name=op.f('fk_changelog_entries_workspace_id_workspaces'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_changelog_entries'))
    )
    op.create_index('ix_changelog_entries_tsv', 'changelog_entries', ['tsv'], unique=False, postgresql_using='gin')
    op.create_index('ix_changelog_repo_created', 'changelog_entries', ['repo_id', sa.literal_column('created_at DESC')], unique=False)
    op.create_table('chat_messages',
    sa.Column('workspace_id', sa.UUID(), nullable=False),
    sa.Column('thread_id', sa.UUID(), nullable=False),
    sa.Column('role', sa.String(length=10), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('sources', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['thread_id'], ['chat_threads.id'], name=op.f('fk_chat_messages_thread_id_chat_threads'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name=op.f('fk_chat_messages_workspace_id_workspaces'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_chat_messages'))
    )
    op.create_index(op.f('ix_chat_messages_thread_id'), 'chat_messages', ['thread_id'], unique=False)
    op.create_table('documents',
    sa.Column('workspace_id', sa.UUID(), nullable=False),
    sa.Column('repo_id', sa.UUID(), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('published_version_id', sa.UUID(), nullable=True),
    sa.Column('source_paths', sa.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("kind IN ('overview', 'setup', 'api')", name=op.f('ck_documents_kind')),
    sa.ForeignKeyConstraint(['published_version_id'], ['document_versions.id'], name=op.f('fk_documents_published_version_id_document_versions'), ondelete='SET NULL', use_alter=True),
    sa.ForeignKeyConstraint(['repo_id'], ['repositories.id'], name=op.f('fk_documents_repo_id_repositories'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name=op.f('fk_documents_workspace_id_workspaces'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_documents')),
    sa.UniqueConstraint('repo_id', 'kind', name=op.f('uq_documents_repo_id_kind'))
    )
    op.create_index(op.f('ix_documents_workspace_id'), 'documents', ['workspace_id'], unique=False)
    op.create_table('files',
    sa.Column('workspace_id', sa.UUID(), nullable=False),
    sa.Column('repo_id', sa.UUID(), nullable=False),
    sa.Column('path', sa.Text(), nullable=False),
    sa.Column('blob_sha', sa.String(length=64), nullable=False),
    sa.Column('language', sa.String(length=40), nullable=True),
    sa.Column('size', sa.Integer(), nullable=False),
    sa.Column('line_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('summary', sa.Text(), nullable=True),
    sa.Column('symbols', sa.ARRAY(sa.Text()), nullable=True),
    sa.Column('summary_model', sa.String(length=60), nullable=True),
    sa.Column('summary_blob_sha', sa.String(length=64), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['repo_id'], ['repositories.id'], name=op.f('fk_files_repo_id_repositories'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name=op.f('fk_files_workspace_id_workspaces'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_files')),
    sa.UniqueConstraint('repo_id', 'path', name=op.f('uq_files_repo_id_path'))
    )
    op.create_table('jobs',
    sa.Column('workspace_id', sa.UUID(), nullable=True),
    sa.Column('repo_id', sa.UUID(), nullable=True),
    sa.Column('type', sa.String(length=30), nullable=False),
    sa.Column('status', sa.String(length=20), server_default=sa.text("'queued'"), nullable=False),
    sa.Column('attempts', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('max_attempts', sa.Integer(), server_default=sa.text('5'), nullable=False),
    sa.Column('dedupe_key', sa.String(length=120), nullable=True),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('error', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('lease_owner', sa.String(length=100), nullable=True),
    sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('fence', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('run_after', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("status IN ('queued', 'running', 'succeeded', 'failed', 'dead', 'blocked_budget')", name=op.f('ck_jobs_status')),
    sa.CheckConstraint("type IN ('repo_index', 'repo_sync', 'repo_purge', 'installation_sync', 'reembed')", name=op.f('ck_jobs_type')),
    sa.ForeignKeyConstraint(['repo_id'], ['repositories.id'], name=op.f('fk_jobs_repo_id_repositories'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name=op.f('fk_jobs_workspace_id_workspaces'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_jobs'))
    )
    op.create_index('ix_jobs_status_lease', 'jobs', ['status', 'lease_expires_at'], unique=False)
    op.create_index('ix_jobs_status_run_after', 'jobs', ['status', 'run_after'], unique=False)
    op.create_index('ix_jobs_ws_created', 'jobs', ['workspace_id', sa.literal_column('created_at DESC')], unique=False)
    op.create_index('uq_jobs_dedupe_open', 'jobs', ['dedupe_key'], unique=True, postgresql_where=sa.text("status IN ('queued', 'blocked_budget')"))
    op.create_table('oauth_states',
    sa.Column('state_hmac', sa.LargeBinary(), nullable=False),
    sa.Column('provider', sa.String(length=20), nullable=False),
    sa.Column('session_id', sa.UUID(), nullable=True),
    sa.Column('purpose', sa.String(length=20), nullable=False),
    sa.Column('workspace_id', sa.UUID(), nullable=True),
    sa.Column('code_verifier', sa.String(length=128), nullable=True),
    sa.Column('nonce', sa.String(length=128), nullable=True),
    sa.Column('redirect_to', sa.String(length=300), nullable=True),
    sa.Column('installation_id', sa.BigInteger(), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("purpose IN ('login', 'link', 'install')", name=op.f('ck_oauth_states_purpose')),
    sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], name=op.f('fk_oauth_states_session_id_sessions'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name=op.f('fk_oauth_states_workspace_id_workspaces'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('state_hmac', name=op.f('pk_oauth_states'))
    )
    op.create_table('workspace_installations',
    sa.Column('workspace_id', sa.UUID(), nullable=False),
    sa.Column('installation_id', sa.BigInteger(), nullable=False),
    sa.Column('added_by', sa.UUID(), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['added_by'], ['users.id'], name=op.f('fk_workspace_installations_added_by_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['installation_id'], ['github_installations.installation_id'], name=op.f('fk_workspace_installations_installation_id_github_installations'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name=op.f('fk_workspace_installations_workspace_id_workspaces'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_workspace_installations')),
    sa.UniqueConstraint('workspace_id', 'installation_id', name=op.f('uq_workspace_installations_workspace_id_installation_id'))
    )
    op.create_index(op.f('ix_workspace_installations_installation_id'), 'workspace_installations', ['installation_id'], unique=False)
    op.create_table('chunks',
    sa.Column('workspace_id', sa.UUID(), nullable=False),
    sa.Column('repo_id', sa.UUID(), nullable=False),
    sa.Column('file_id', sa.UUID(), nullable=False),
    sa.Column('path', sa.Text(), nullable=False),
    sa.Column('start_line', sa.Integer(), nullable=False),
    sa.Column('end_line', sa.Integer(), nullable=False),
    sa.Column('commit_sha', sa.String(length=40), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('content_hash', sa.String(length=64), nullable=False),
    sa.Column('search_text', sa.Text(), nullable=False),
    sa.Column('tsv', postgresql.TSVECTOR(), sa.Computed("to_tsvector('simple', search_text)", persisted=True), nullable=False),
    sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=1024), nullable=True),
    sa.Column('embed_model', sa.String(length=60), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['file_id'], ['files.id'], name=op.f('fk_chunks_file_id_files'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['repo_id'], ['repositories.id'], name=op.f('fk_chunks_repo_id_repositories'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name=op.f('fk_chunks_workspace_id_workspaces'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_chunks'))
    )
    op.create_index(op.f('ix_chunks_file_id'), 'chunks', ['file_id'], unique=False)
    op.create_index('ix_chunks_path_trgm', 'chunks', ['path'], unique=False, postgresql_using='gin', postgresql_ops={'path': 'gin_trgm_ops'})
    op.create_index('ix_chunks_tsv', 'chunks', ['tsv'], unique=False, postgresql_using='gin')
    op.create_index('ix_chunks_ws_repo', 'chunks', ['workspace_id', 'repo_id'], unique=False)
    op.create_table('document_versions',
    sa.Column('workspace_id', sa.UUID(), nullable=False),
    sa.Column('document_id', sa.UUID(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('base_version_id', sa.UUID(), nullable=True),
    sa.Column('content_md', sa.Text(), nullable=False),
    sa.Column('commit_sha', sa.String(length=40), nullable=False),
    sa.Column('job_id', sa.UUID(), nullable=True),
    sa.Column('model', sa.String(length=60), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('partial', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('reviewed_by', sa.UUID(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('tsv', postgresql.TSVECTOR(), sa.Computed("to_tsvector('english', content_md)", persisted=True), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("status IN ('published', 'pending_review', 'rejected', 'superseded')", name=op.f('ck_document_versions_status')),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], name=op.f('fk_document_versions_document_id_documents'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], name=op.f('fk_document_versions_reviewed_by_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name=op.f('fk_document_versions_workspace_id_workspaces'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_document_versions')),
    sa.UniqueConstraint('document_id', 'version', name=op.f('uq_document_versions_document_id_version'))
    )
    op.create_index('ix_document_versions_tsv', 'document_versions', ['tsv'], unique=False, postgresql_using='gin')
    # documents <-> document_versions reference each other, so this FK is added last.
    op.create_foreign_key(
        op.f("fk_documents_published_version_id_document_versions"), "documents", "document_versions",
        ["published_version_id"], ["id"], ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("fk_documents_published_version_id_document_versions"), "documents", type_="foreignkey")
    op.drop_index('ix_document_versions_tsv', table_name='document_versions', postgresql_using='gin')
    op.drop_table('document_versions')
    op.drop_index('ix_chunks_ws_repo', table_name='chunks')
    op.drop_index('ix_chunks_tsv', table_name='chunks', postgresql_using='gin')
    op.drop_index('ix_chunks_path_trgm', table_name='chunks', postgresql_using='gin', postgresql_ops={'path': 'gin_trgm_ops'})
    op.drop_index(op.f('ix_chunks_file_id'), table_name='chunks')
    op.drop_table('chunks')
    op.drop_index(op.f('ix_workspace_installations_installation_id'), table_name='workspace_installations')
    op.drop_table('workspace_installations')
    op.drop_table('oauth_states')
    op.drop_index('uq_jobs_dedupe_open', table_name='jobs', postgresql_where=sa.text("status IN ('queued', 'blocked_budget')"))
    op.drop_index('ix_jobs_ws_created', table_name='jobs')
    op.drop_index('ix_jobs_status_run_after', table_name='jobs')
    op.drop_index('ix_jobs_status_lease', table_name='jobs')
    op.drop_table('jobs')
    op.drop_table('files')
    op.drop_index(op.f('ix_documents_workspace_id'), table_name='documents')
    op.drop_table('documents')
    op.drop_index(op.f('ix_chat_messages_thread_id'), table_name='chat_messages')
    op.drop_table('chat_messages')
    op.drop_index('ix_changelog_repo_created', table_name='changelog_entries')
    op.drop_index('ix_changelog_entries_tsv', table_name='changelog_entries', postgresql_using='gin')
    op.drop_table('changelog_entries')
    op.drop_index(op.f('ix_sessions_user_id'), table_name='sessions')
    op.drop_index(op.f('ix_sessions_expires_at'), table_name='sessions')
    op.drop_table('sessions')
    op.drop_index(op.f('ix_repositories_workspace_id'), table_name='repositories')
    op.drop_table('repositories')
    op.drop_index(op.f('ix_memberships_user_id'), table_name='memberships')
    op.drop_table('memberships')
    op.drop_index('ix_llm_usage_ws_created', table_name='llm_usage')
    op.drop_index('ix_llm_usage_created', table_name='llm_usage')
    op.drop_table('llm_usage')
    op.drop_index('uq_invites_open_email', table_name='invites', postgresql_where=sa.text('accepted_at IS NULL AND revoked_at IS NULL'))
    op.drop_table('invites')
    op.drop_table('github_installations')
    op.drop_index(op.f('ix_email_tokens_user_id'), table_name='email_tokens')
    op.drop_table('email_tokens')
    op.drop_index(op.f('ix_chat_threads_workspace_id'), table_name='chat_threads')
    op.drop_index(op.f('ix_chat_threads_user_id'), table_name='chat_threads')
    op.drop_table('chat_threads')
    op.drop_index(op.f('ix_auth_identities_user_id'), table_name='auth_identities')
    op.drop_table('auth_identities')
    op.drop_index('ix_audit_ws_created', table_name='audit_events')
    op.drop_table('audit_events')
    op.drop_table('workspaces')
    op.drop_table('webhook_deliveries')
    op.drop_table('users')
    op.drop_table('singletons')
