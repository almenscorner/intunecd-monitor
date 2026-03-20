from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import require_api_key
from app.models import (
    SummaryAssignment,
    SummaryAverageDiffs,
    SummaryChange,
    SummaryConfigCount,
    SummaryDiffCount,
    Tenant,
)
from app.schemas import TenantPatch, TenantResponse

router = APIRouter(tags=["tenants"])


@router.get("/tenants", response_model=List[TenantResponse], dependencies=[Depends(require_api_key)])
def get_tenants(db: Annotated[Session, Depends(get_db)]):
    return db.query(Tenant).all()


@router.get("/tenants/{tenant_id}", response_model=TenantResponse, dependencies=[Depends(require_api_key)])
def get_tenant(tenant_id: int, db: Annotated[Session, Depends(get_db)]):
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


@router.patch("/tenants/{tenant_id}", response_model=TenantResponse, dependencies=[Depends(require_api_key)])
def patch_tenant(
    tenant_id: int,
    body: TenantPatch,
    db: Annotated[Session, Depends(get_db)],
):
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    if body.display_name is not None:
        tenant.display_name = body.display_name
    if body.repo is not None:
        tenant.repo = body.repo
    if body.update_args is not None:
        tenant.update_args = body.update_args
    if body.backup_args is not None:
        tenant.backup_args = body.backup_args

    if body.baseline == "true":
        current = db.query(Tenant).filter_by(baseline="true").first()
        if current:
            current.baseline = ""
        tenant.baseline = "true"
    elif body.baseline is not None:
        tenant.baseline = ""

    if body.pat and tenant.vault_name and settings.AZURE_VAULT_URL:
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient
        client = SecretClient(settings.AZURE_VAULT_URL, DefaultAzureCredential())
        client.set_secret(tenant.vault_name, body.pat)

    db.commit()
    db.refresh(tenant)
    return tenant


@router.delete("/tenants/{tenant_id}", dependencies=[Depends(require_api_key)])
def delete_tenant(tenant_id: int, db: Annotated[Session, Depends(get_db)]):
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    db.query(SummaryChange).filter_by(tenant=tenant_id).delete()
    db.query(SummaryAssignment).filter_by(tenant=tenant_id).delete()
    db.query(SummaryConfigCount).filter_by(tenant=tenant_id).delete()
    db.query(SummaryDiffCount).filter_by(tenant=tenant_id).delete()
    db.query(SummaryAverageDiffs).filter_by(tenant=tenant_id).delete()

    if tenant.vault_name and settings.AZURE_VAULT_URL:
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient
        client = SecretClient(settings.AZURE_VAULT_URL, DefaultAzureCredential())
        op = client.begin_delete_secret(tenant.vault_name)
        op.wait()
        client.purge_deleted_secret(tenant.vault_name)

    db.delete(tenant)
    db.commit()
    return {"success": True, "message": "Tenant deleted"}
