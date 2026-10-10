import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import BYTEA, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now():
    return datetime.now(UTC)

class Mailbox(Base):
    __tablename__ = "mailboxes"
    id_mailbox: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email_address: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(50)) # gamil |outlook | imap
    oauth_access_token: Mapped[bytes | None] = mapped_column(BYTEA)
    oauth_refresh_token: Mapped[bytes | None] = mapped_column(BYTEA)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    webhook_subscription_id: Mapped[str | None] = mapped_column(String(255))
    webhook_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sync_cursor: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    emails: Mapped[list["Email"]] = relationship(back_populates="mailbox", cascade="all, delete-orphan")

class Contact(Base):
    __tablename__ = "contacts"

    id_contact: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email_address: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    sender_name: Mapped[str | None] = mapped_column(String(255))
    company: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50))
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False)
    is_known_customer: Mapped[bool] = mapped_column(Boolean, default=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    email_count: Mapped[int] = mapped_column(Integer, default=0)

    emails: Mapped[list["Email"]] = relationship(back_populates="sender")

class Email(Base):
    __tablename__ = "emails"
    __table_args__ = (UniqueConstraint("id_mailbox", "message_id", name="uq_mailbox_message"),)

    id_email: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_mailbox: Mapped[uuid.UUID] = mapped_column(ForeignKey("mailboxes.id_mailbox"), index=True)
    id_sender: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contacts.id_contact"), index=True)

    message_id: Mapped[str] = mapped_column(String(998), index=True)
    thread_id: Mapped[str | None] = mapped_column(String(998), index=True)
    in_reply_to: Mapped[str | None] = mapped_column(String(998))
    subject: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    body_text: Mapped[str | None] = mapped_column(Text)
    body_clean: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(10))
    has_attachments: Mapped[bool] = mapped_column(Boolean, default=False)
    cc_emails: Mapped[list | None] = mapped_column(JSONB, default=None)
    bcc_emails: Mapped[list | None] = mapped_column(JSONB, default=None)

    # Workflow & HITL
    status: Mapped[str] = mapped_column(String(50), default="PENDING_ROUTING", index=True)
    assigned_agent: Mapped[str | None] = mapped_column(String(100), index=True)
    security_flags: Mapped[dict | None] = mapped_column(JSONB)

    # Storage
    raw_storage_key: Mapped[str | None] = mapped_column(String(1024))
    html_storage_key: Mapped[str | None] = mapped_column(String(1024))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    mailbox: Mapped["Mailbox"] = relationship(back_populates="emails")
    sender: Mapped["Contact"] = relationship(back_populates="emails")
    labels: Mapped[list["EmailLabel"]] = relationship(back_populates="email", cascade="all, delete-orphan")
    attachments: Mapped[list["Attachment"]] = relationship(back_populates="email", cascade="all, delete-orphan")
    summary: Mapped["EmailSummary"] = relationship(back_populates="email", uselist=False, cascade="all, delete-orphan")
    card: Mapped["EmailCard"] = relationship(back_populates="email", uselist=False, cascade="all, delete-orphan")

class Label(Base):
    __tablename__ = "labels"

    id_label: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    label_name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(SmallInteger, default=50)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class EmailLabel(Base):
    __tablename__ = "email_labels"

    id_email: Mapped[uuid.UUID] = mapped_column(ForeignKey("emails.id_email"), primary_key=True)
    id_label: Mapped[int] = mapped_column(ForeignKey("labels.id_label"), primary_key=True)
    source: Mapped[str] = mapped_column(String(20), primary_key=True) # ai | rule | user

    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    email: Mapped["Email"] = relationship(back_populates="labels")
    label: Mapped["Label"] = relationship()

class Attachment(Base):
    __tablename__ = "attachments"

    id_attachment: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_email: Mapped[uuid.UUID] = mapped_column(ForeignKey("emails.id_email"), index=True)
    file_name: Mapped[str] = mapped_column(String(1024))
    mime_type: Mapped[str | None] = mapped_column(String(255))
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    storage_key: Mapped[str] = mapped_column(String(1024))
    is_inline: Mapped[bool] = mapped_column(Boolean, default=False)
    process_status: Mapped[str] = mapped_column(String(50), default="pending")

    email: Mapped["Email"] = relationship(back_populates="attachments")

class EmailSummary(Base):
    __tablename__ = "email_summaries"

    id_summary: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_email: Mapped[uuid.UUID] = mapped_column(ForeignKey("emails.id_email"), unique=True)
    content_summarized: Mapped[str | None] = mapped_column(Text)
    key_points: Mapped[dict | list | None] = mapped_column(JSONB)
    model: Mapped[str | None] = mapped_column(String(128))
    prompt_version: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    email: Mapped["Email"] = relationship(back_populates="summary")

class EmailCard(Base):
    __tablename__ = "email_cards"

    id_email: Mapped[uuid.UUID] = mapped_column(ForeignKey("emails.id_email"), primary_key=True)
    card_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    email: Mapped["Email"] = relationship(back_populates="card")
