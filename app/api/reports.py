"""
Жалобы пользователей на аккаунты, сходки, клубы, автосервисы,
сообщения в чате и фото. Рассмотрение жалоб — в app/api/admin.py.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_active_user
from app.models.report import Report
from app.models.user import User
from app.schemas.report import ReportCreate, ReportOut
from app.schemas.user import UserPublic

router = APIRouter()


@router.post(
    "/",
    response_model=ReportOut,
    status_code=201,
    summary="Отправить жалобу",
)
def create_report(
    payload: ReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if payload.target_type == "user":
        if payload.target_id == current_user.id:
            raise HTTPException(status_code=400, detail="Нельзя пожаловаться на самого себя")
        if not db.query(User.id).filter(User.id == payload.target_id).first():
            raise HTTPException(status_code=404, detail="Пользователь не найден")

    report = Report(
        reporter_id=current_user.id,
        target_type=payload.target_type,
        target_id=payload.target_id,
        reason=payload.reason,
        description=payload.description,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    out = ReportOut.model_validate(report)
    out.reporter = UserPublic.model_validate(current_user)
    return out


@router.get("/my", response_model=List[ReportOut], summary="Мои отправленные жалобы")
def my_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    reports = (
        db.query(Report)
        .filter(Report.reporter_id == current_user.id)
        .order_by(Report.created_at.desc())
        .all()
    )
    return [ReportOut.model_validate(r) for r in reports]
