from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_api_key
from app.models import SummaryAssignment
from app.schemas import AssignmentResponse

router = APIRouter(tags=["assignments"])


@router.get("/assignments", response_model=List[AssignmentResponse], dependencies=[Depends(require_api_key)])
def get_assignments(db: Annotated[Session, Depends(get_db)]):
    return db.query(SummaryAssignment).all()


@router.get("/assignments/{tenant_id}", response_model=List[AssignmentResponse], dependencies=[Depends(require_api_key)])
def get_assignments_for_tenant(tenant_id: int, db: Annotated[Session, Depends(get_db)]):
    assignments = db.query(SummaryAssignment).filter_by(tenant=tenant_id).all()
    if not assignments:
        raise HTTPException(status_code=404, detail="No assignments found for this tenant")
    return assignments
