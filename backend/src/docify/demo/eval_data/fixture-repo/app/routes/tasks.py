from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import current_user_id
from app.db import get_session
from app.models import Task

router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskIn(BaseModel):
    title: str
    priority: int = 2
    due_date: date | None = None


class TaskPatch(BaseModel):
    title: str | None = None
    done: bool | None = None
    priority: int | None = None


@router.get("")
def list_tasks(done: bool | None = None, user_id: int = Depends(current_user_id), db: Session = Depends(get_session)):
    """List the caller's tasks, optionally filtered by completion (done), highest priority first."""
    q = db.query(Task).filter_by(owner_id=user_id)
    if done is not None:
        q = q.filter_by(done=done)
    return q.order_by(Task.priority, Task.due_date).all()


@router.post("", status_code=201)
def create_task(body: TaskIn, user_id: int = Depends(current_user_id), db: Session = Depends(get_session)):
    if not 1 <= body.priority <= 3:
        raise HTTPException(status_code=422, detail="priority must be 1, 2 or 3")
    task = Task(owner_id=user_id, title=body.title, priority=body.priority, due_date=body.due_date)
    db.add(task)
    db.commit()
    return task


@router.patch("/{task_id}")
def update_task(task_id: int, body: TaskPatch, user_id: int = Depends(current_user_id),
                db: Session = Depends(get_session)):
    task = db.query(Task).filter_by(id=task_id, owner_id=user_id).first()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(task, field, value)
    db.commit()
    return task


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: int, user_id: int = Depends(current_user_id), db: Session = Depends(get_session)):
    deleted = db.query(Task).filter_by(id=task_id, owner_id=user_id).delete()
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    db.commit()
