from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_api_key
from app.models import SummaryChange
from app.schemas import ChangeResponse

router = APIRouter(tags=["changes"])


@router.get("/changes", response_model=List[ChangeResponse], dependencies=[Depends(require_api_key)])
def get_changes(db: Annotated[Session, Depends(get_db)]):
    return db.query(SummaryChange).all()


@router.get("/changes/{tenant_id}", response_model=List[ChangeResponse], dependencies=[Depends(require_api_key)])
def get_changes_for_tenant(tenant_id: int, db: Annotated[Session, Depends(get_db)]):
    changes = db.query(SummaryChange).filter_by(tenant=tenant_id).all()
    if not changes:
        raise HTTPException(status_code=404, detail="No changes found for this tenant")
    return changes
