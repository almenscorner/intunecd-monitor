from datetime import datetime
from typing import Optional
from pydantic import BaseModel


# ── Tenant ────────────────────────────────────────────────────────────────────

class TenantResponse(BaseModel):
    id: int
    display_name: Optional[str]
    name: Optional[str]
    repo: Optional[str]
    update_args: Optional[str]
    backup_args: Optional[str]
    baseline: Optional[str]
    last_update_status: Optional[str]
    update_branch: Optional[str]

    model_config = {"from_attributes": True}


class TenantPatch(BaseModel):
    display_name: Optional[str] = None
    repo: Optional[str] = None
    update_args: Optional[str] = None
    backup_args: Optional[str] = None
    baseline: Optional[str] = None
    pat: Optional[str] = None


# ── Change ────────────────────────────────────────────────────────────────────

class ChangeResponse(BaseModel):
    id: int
    name: Optional[str]
    type: Optional[str]
    diffs: Optional[str]
    tenant: Optional[int]

    model_config = {"from_attributes": True}


# ── Assignment ────────────────────────────────────────────────────────────────

class AssignmentResponse(BaseModel):
    id: int
    name: Optional[str]
    type: Optional[str]
    membership_rule: Optional[str]
    assigned_to: Optional[str]
    tenant: Optional[int]

    model_config = {"from_attributes": True}


# ── Schedule ──────────────────────────────────────────────────────────────────

class ScheduleResponse(BaseModel):
    id: int
    name: Optional[str]
    task: Optional[str]
    args: Optional[str]
    schedule_id: Optional[int]
    last_run_at: Optional[datetime]
    total_run_count: Optional[int]
    date_changed: Optional[datetime]

    model_config = {"from_attributes": True}


# ── Generic API responses ─────────────────────────────────────────────────────

class SuccessResponse(BaseModel):
    success: bool = True
    message: Optional[str] = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
