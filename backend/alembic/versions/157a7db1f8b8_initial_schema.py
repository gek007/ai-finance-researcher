"""initial schema

Revision ID: 157a7db1f8b8
Revises:
Create Date: 2026-07-01 21:13:19.916071

"""

from typing import Sequence, Union

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "157a7db1f8b8"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "profiles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        """
        ALTER TABLE profiles
        ADD CONSTRAINT profiles_id_fkey
        FOREIGN KEY (id) REFERENCES auth.users (id) ON DELETE CASCADE
        """
    )

    op.create_table(
        "source_documents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("filing_type", sa.String(length=16), nullable=False),
        sa.Column("filing_date", sa.Date(), nullable=True),
        sa.Column("fiscal_year", sa.Integer(), nullable=True),
        sa.Column("accession_number", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("markdown_content", sa.Text(), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "accession_number", name="uq_source_documents_accession_number"
        ),
    )
    op.create_index(
        op.f("ix_source_documents_ticker"), "source_documents", ["ticker"], unique=False
    )

    op.create_table(
        "chat_threads",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "title", sa.String(length=255), server_default="New chat", nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_chat_threads_user_id"), "chat_threads", ["user_id"], unique=False
    )

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("page_label", sa.String(length=128), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column(
            "embedding", pgvector.sqlalchemy.vector.VECTOR(dim=1536), nullable=True
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["source_documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id", "chunk_index", name="uq_document_chunks_document_index"
        ),
    )
    op.create_index(
        op.f("ix_document_chunks_document_id"),
        "document_chunks",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        "ix_document_chunks_metadata",
        "document_chunks",
        ["metadata"],
        unique=False,
        postgresql_using="gin",
    )
    op.execute(
        """
        ALTER TABLE document_chunks
        ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (to_tsvector('english', coalesce(text, ''))) STORED
        """
    )
    op.execute(
        """
        CREATE INDEX ix_document_chunks_search_vector
        ON document_chunks USING gin (search_vector)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_document_chunks_embedding
        ON document_chunks USING hnsw (embedding vector_cosine_ops)
        """
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("thread_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "message_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["thread_id"], ["chat_threads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_chat_messages_thread_id"), "chat_messages", ["thread_id"], unique=False
    )

    op.create_table(
        "message_citations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("message_id", sa.UUID(), nullable=False),
        sa.Column("chunk_id", sa.UUID(), nullable=False),
        sa.Column("citation_index", sa.Integer(), nullable=False),
        sa.Column("quote", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id"], ["document_chunks.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["message_id"], ["chat_messages.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_message_citations_chunk_id"),
        "message_citations",
        ["chunk_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_message_citations_message_id"),
        "message_citations",
        ["message_id"],
        unique=False,
    )

    _enable_rls()


def downgrade() -> None:
    _disable_rls()

    op.drop_index(
        op.f("ix_message_citations_message_id"), table_name="message_citations"
    )
    op.drop_index(op.f("ix_message_citations_chunk_id"), table_name="message_citations")
    op.drop_table("message_citations")
    op.drop_index(op.f("ix_chat_messages_thread_id"), table_name="chat_messages")
    op.drop_table("chat_messages")
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding")
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_search_vector")
    op.drop_index("ix_document_chunks_metadata", table_name="document_chunks")
    op.drop_index(op.f("ix_document_chunks_document_id"), table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_index(op.f("ix_chat_threads_user_id"), table_name="chat_threads")
    op.drop_table("chat_threads")
    op.drop_index(op.f("ix_source_documents_ticker"), table_name="source_documents")
    op.drop_table("source_documents")
    op.execute("ALTER TABLE profiles DROP CONSTRAINT IF EXISTS profiles_id_fkey")
    op.drop_table("profiles")


def _enable_rls() -> None:
    op.execute("ALTER TABLE profiles ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE chat_threads ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE message_citations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE source_documents ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE POLICY profiles_select_own ON profiles
        FOR SELECT USING (auth.uid() = id)
        """
    )
    op.execute(
        """
        CREATE POLICY profiles_insert_own ON profiles
        FOR INSERT WITH CHECK (auth.uid() = id)
        """
    )
    op.execute(
        """
        CREATE POLICY profiles_update_own ON profiles
        FOR UPDATE USING (auth.uid() = id)
        """
    )

    op.execute(
        """
        CREATE POLICY chat_threads_owner ON chat_threads
        FOR ALL USING (auth.uid() = user_id)
        """
    )

    op.execute(
        """
        CREATE POLICY chat_messages_owner ON chat_messages
        FOR ALL USING (
            EXISTS (
                SELECT 1 FROM chat_threads t
                WHERE t.id = chat_messages.thread_id
                  AND t.user_id = auth.uid()
            )
        )
        """
    )

    op.execute(
        """
        CREATE POLICY message_citations_read_owner ON message_citations
        FOR SELECT USING (
            EXISTS (
                SELECT 1 FROM chat_messages m
                JOIN chat_threads t ON t.id = m.thread_id
                WHERE m.id = message_citations.message_id
                  AND t.user_id = auth.uid()
            )
        )
        """
    )

    op.execute(
        """
        CREATE POLICY source_documents_read_authenticated ON source_documents
        FOR SELECT TO authenticated USING (true)
        """
    )
    op.execute(
        """
        CREATE POLICY document_chunks_read_authenticated ON document_chunks
        FOR SELECT TO authenticated USING (true)
        """
    )


def _disable_rls() -> None:
    for table, policies in [
        (
            "profiles",
            ("profiles_select_own", "profiles_insert_own", "profiles_update_own"),
        ),
        ("chat_threads", ("chat_threads_owner",)),
        ("chat_messages", ("chat_messages_owner",)),
        ("message_citations", ("message_citations_read_owner",)),
        ("source_documents", ("source_documents_read_authenticated",)),
        ("document_chunks", ("document_chunks_read_authenticated",)),
    ]:
        for policy in policies:
            op.execute(f"DROP POLICY IF EXISTS {policy} ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
