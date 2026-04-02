from __future__ import annotations

from datetime import datetime
from typing import Optional

import bcrypt
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SummaryConfigCount(Base):
    __tablename__ = "summary_config_count"

    id: Mapped[int] = mapped_column(primary_key=True)
    config_count: Mapped[Optional[int]]
    last_update: Mapped[Optional[datetime]]
    tenant: Mapped[Optional[int]]


class SummaryDiffCount(Base):
    __tablename__ = "summary_diff_count"

    id: Mapped[int] = mapped_column(primary_key=True)
    diff_count: Mapped[Optional[int]]
    last_update: Mapped[Optional[datetime]]
    tenant: Mapped[Optional[int]]


class SummaryAverageDiffs(Base):
    __tablename__ = "summary_average_diffs"

    id: Mapped[int] = mapped_column(primary_key=True)
    average_diffs: Mapped[Optional[float]]
    last_update: Mapped[Optional[datetime]]
    tenant: Mapped[Optional[int]]


class SummaryChange(Base):
    __tablename__ = "summary_changes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String)
    type: Mapped[Optional[str]] = mapped_column(String)
    diffs: Mapped[Optional[str]] = mapped_column(String)
    tenant: Mapped[Optional[int]]


class SummaryAssignment(Base):
    __tablename__ = "summary_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String)
    type: Mapped[Optional[str]] = mapped_column(String)
    membership_rule: Mapped[Optional[str]] = mapped_column(String)
    assigned_to: Mapped[Optional[str]] = mapped_column(String)
    tenant: Mapped[Optional[int]]


class Tenant(Base):
    __tablename__ = "intunecd_tenants"

    id: Mapped[int] = mapped_column(primary_key=True)
    display_name: Mapped[Optional[str]] = mapped_column(String)
    name: Mapped[Optional[str]] = mapped_column(String)
    repo: Mapped[Optional[str]] = mapped_column(String)
    encrypted_pat: Mapped[Optional[str]] = mapped_column(String)
    update_args: Mapped[Optional[str]] = mapped_column(String)
    backup_args: Mapped[Optional[str]] = mapped_column(String)
    baseline: Mapped[Optional[str]] = mapped_column(String)
    update_feed: Mapped[Optional[str]] = mapped_column(String)
    backup_feed: Mapped[Optional[str]] = mapped_column(String)
    last_update: Mapped[Optional[datetime]]
    last_update_status: Mapped[Optional[str]] = mapped_column(String)
    last_update_message: Mapped[Optional[str]] = mapped_column(String)
    last_task_id: Mapped[Optional[str]] = mapped_column(String)
    new_branch: Mapped[Optional[str]] = mapped_column(String)
    update_branch: Mapped[Optional[str]] = mapped_column(String)
    create_documentation: Mapped[Optional[str]] = mapped_column(String)
    documentation_html: Mapped[Optional[str]] = mapped_column(Text)


class ApiKey(Base):
    __tablename__ = "api_key"

    id: Mapped[int] = mapped_column(primary_key=True)
    key_hash: Mapped[Optional[str]] = mapped_column(String(500), unique=True)
    key_expiration: Mapped[Optional[datetime]]

    def set_key(self, plain_text_key: str) -> None:
        self.key_hash = bcrypt.hashpw(
            plain_text_key.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

    def check_key(self, attempted_key: str) -> bool:
        if not self.key_hash:
            return False
        return bcrypt.checkpw(
            attempted_key.encode("utf-8"), self.key_hash.encode("utf-8")
        )
