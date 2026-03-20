import json
import os
import re
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import require_admin
from app.models import (
    SummaryAssignment,
    SummaryAverageDiffs,
    SummaryChange,
    SummaryConfigCount,
    SummaryDiffCount,
    Tenant,
)
from app.routers.pages import base_ctx, get_segment
from app.run_intunecd import get_branches

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/tenants", response_class=HTMLResponse)
async def tenants_page(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[dict, Depends(require_admin)],
):
    tenant_list = db.query(Tenant).all()
    baseline = db.query(Tenant).filter_by(baseline="true").first() is not None
    ctx = base_ctx(request, db, user)
    ctx.update({
        "segment": get_segment(request),
        "tenants": tenant_list,
        "baseline": baseline,
    })
    return templates.TemplateResponse("pages/tenants.html", ctx)


@router.post("/tenants/add")
async def add_tenant(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[dict, Depends(require_admin)],
):
    form = await request.form()
    display_name = form.get("tenant_display_name")
    tenant_name = form.get("tenant_name")
    tenant_repo = form.get("tenant_repo")
    tenant_pat = form.get("tenant_pat")
    update_args = form.get("tenant_update_args")
    backup_args = form.get("tenant_backup_args")
    baseline = form.get("tenant_baseline")
    new_branch = form.get("tenant_new_branch")

    vault_name = ""
    if tenant_repo and tenant_pat and settings.AZURE_VAULT_URL:
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient

        tenant_repo = re.sub(r"^https?://", "", tenant_repo)
        vault_name = re.sub(r"[^a-zA-Z0-9]+", "-", tenant_name)

        credential = DefaultAzureCredential()
        client = SecretClient(settings.AZURE_VAULT_URL, credential)
        try:
            client.get_secret(vault_name)
        except Exception as e:
            if "SecretNotFound" in str(e):
                client.set_secret(vault_name, tenant_pat)
            else:
                raise

    tenant = Tenant(
        display_name=display_name,
        name=tenant_name,
        repo=tenant_repo,
        vault_name=vault_name,
        update_args=update_args,
        backup_args=backup_args,
        baseline=baseline,
        last_update_status="unknown",
        new_branch=new_branch,
        update_branch="main",
    )
    db.add(tenant)
    db.commit()

    base_url = "https://login.microsoftonline.com/organizations/v2.0/adminconsent"
    scope = "https://graph.microsoft.com/.default"
    redirect_uri = f"{os.getenv('SERVER_NAME', '')}/tenants"
    consent_url = (
        f"{base_url}?client_id={settings.AZURE_CLIENT_ID}"
        f"&scope={scope}&redirect_uri={redirect_uri}"
    )
    return RedirectResponse(url=consent_url, status_code=303)


@router.get("/tenants/delete/{tenant_id}")
async def delete_tenant(
    tenant_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[dict, Depends(require_admin)],
):
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        return RedirectResponse(url="/tenants", status_code=303)

    # Delete related data
    db.query(SummaryChange).filter_by(tenant=tenant_id).delete()
    db.query(SummaryAssignment).filter_by(tenant=tenant_id).delete()
    db.query(SummaryConfigCount).filter_by(tenant=tenant_id).delete()
    db.query(SummaryDiffCount).filter_by(tenant=tenant_id).delete()
    db.query(SummaryAverageDiffs).filter_by(tenant=tenant_id).delete()

    if tenant.vault_name and settings.AZURE_VAULT_URL:
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient

        credential = DefaultAzureCredential()
        client = SecretClient(settings.AZURE_VAULT_URL, credential)
        op = client.begin_delete_secret(tenant.vault_name)
        op.wait()
        client.purge_deleted_secret(tenant.vault_name)

    db.delete(tenant)
    db.commit()
    return RedirectResponse(url="/tenants", status_code=303)


@router.get("/tenants/edit/{tenant_id}", response_class=HTMLResponse)
async def edit_tenant(
    tenant_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[dict, Depends(require_admin)],
):
    all_tenants = db.query(Tenant).all()
    tenants_list = [
        {
            "id": t.id,
            "display_name": t.display_name,
            "name": t.name,
            "repo": t.repo,
            "update_args": t.update_args,
            "backup_args": t.backup_args,
            "baseline": t.baseline,
            "last_update_status": t.last_update_status,
            "update_branch": t.update_branch,
            "new_branch": t.new_branch,
            "create_documentation": t.create_documentation,
        }
        for t in all_tenants
    ]

    branches = get_branches(tenant_id)
    if "HEAD" in branches:
        branches.remove("HEAD")

    ctx = base_ctx(request, db, user)
    ctx["data"] = {"edit_id": tenant_id, "tenants": tenants_list, "branches": branches}
    return templates.TemplateResponse("views/edit_tenant.html", ctx)


@router.post("/tenants/edit/{tenant_id}/save")
async def save_tenant(
    tenant_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[dict, Depends(require_admin)],
):
    form = await request.form()
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        return RedirectResponse(url="/tenants", status_code=303)

    tenant.display_name = form.get("tenant_display_name")
    tenant.repo = form.get("tenant_repo")
    tenant.update_args = form.get("tenant_update_args")
    tenant.backup_args = form.get("tenant_backup_args")
    tenant.new_branch = form.get("tenant_new_branch")
    tenant.update_branch = form.get("tenant_update_branch")
    tenant.create_documentation = form.get("tenant_create_documentation")
    tenant_baseline = form.get("tenant_baseline")
    tenant_pat = form.get("tenant_pat")

    if tenant_baseline == "true":
        current_baseline = db.query(Tenant).filter_by(baseline="true").first()
        if current_baseline:
            current_baseline.baseline = ""
        if tenant.baseline != "true":
            tenant.baseline = "true"
    else:
        tenant.baseline = ""

    if tenant.repo and tenant_pat and tenant.vault_name and settings.AZURE_VAULT_URL:
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient

        credential = DefaultAzureCredential()
        client = SecretClient(settings.AZURE_VAULT_URL, credential)
        client.set_secret(tenant.vault_name, tenant_pat)

    db.commit()
    return RedirectResponse(url="/tenants", status_code=303)
