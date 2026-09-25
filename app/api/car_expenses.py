from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_active_user
from app.models.car import Car
from app.models.car_expense import CarExpense
from app.models.user import User
from app.schemas.car_expense import CarExpenseCreate, CarExpenseListResponse, CarExpenseOut

router = APIRouter()


def _get_own_car_or_404(db: Session, car_id: str, user_id: str) -> Car:
    car = db.query(Car).filter(Car.id == car_id).first()
    if not car:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Машина не найдена")
    if car.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Это не ваша машина")
    return car


@router.post("", response_model=CarExpenseOut, status_code=status.HTTP_201_CREATED, summary="Добавить трату")
def create_expense(
    payload: CarExpenseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _get_own_car_or_404(db, payload.car_id, current_user.id)

    expense = CarExpense(user_id=current_user.id, **payload.model_dump())
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


@router.get("/car/{car_id}", response_model=CarExpenseListResponse, summary="Расходы по машине")
def list_for_car(
    car_id: str,
    month: str | None = Query(None, description="YYYY-MM — фильтр по месяцу"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _get_own_car_or_404(db, car_id, current_user.id)

    query = db.query(CarExpense).filter(CarExpense.car_id == car_id)
    items = query.order_by(CarExpense.date.desc()).all()
    if month:
        items = [e for e in items if e.date.strftime("%Y-%m") == month]

    by_category: dict[str, float] = defaultdict(float)
    total_amount = 0.0
    for e in items:
        by_category[e.category] += e.amount
        total_amount += e.amount

    return CarExpenseListResponse(
        total=len(items),
        total_amount=round(total_amount, 2),
        by_category={k: round(v, 2) for k, v in by_category.items()},
        items=items,
    )


@router.delete("/{expense_id}", summary="Удалить трату")
def delete_expense(
    expense_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    expense = db.query(CarExpense).filter(CarExpense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Трата не найдена")
    if expense.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа")
    db.delete(expense)
    db.commit()
    return {"message": "Удалено"}
