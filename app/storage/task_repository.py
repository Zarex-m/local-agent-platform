import json

from app.storage.database import SessionLocal, Task, StepLog

from sqlalchemy import select

def create_task(task_text: str, status: str = "created") -> int:
    db = SessionLocal()

    try:
        task = Task(
            task=task_text,
            status=status,
        )

        db.add(task)
        db.commit()
        db.refresh(task)

        return task.id

    finally:
        db.close()


def update_task(task_id: int, state: dict) -> None:
    db = SessionLocal()

    try:
        stmt = select(Task).where(Task.id == task_id)
        task= db.execute(stmt).scalar_one_or_none()

        if task is None:
            raise ValueError(f"Task with id {task_id} not found")

        json_fields = {"plan", "tool_input", "tool_output"}

        for key, value in state.items():
            if not hasattr(task, key):
                continue

            if key in json_fields and value is not None:
                value = json.dumps(value, ensure_ascii=False)

            setattr(task, key, value)

        db.commit()

    finally:
        db.close()


def save_step_logs(task_id: int, step_logs: list[dict]) -> None:
    db = SessionLocal()

    try:
        stmt = select(Task).where(Task.id == task_id)
        task= db.execute(stmt).scalar_one_or_none()

        if task is None:
            raise ValueError(f"Task with id {task_id} not found")

        for log in step_logs:
            step_log = StepLog(
                task_id=task_id,
                node=log.get("node", ""),
                status=log.get("status", ""),
                message=log.get("message", ""),
            )
            db.add(step_log)

        db.commit()

    finally:
        db.close()


def get_task(task_id: int) -> Task | None:
    db = SessionLocal()

    try:
        stmt = select(Task).where(Task.id == task_id)
        return db.execute(stmt).scalar_one_or_none()

    finally:
        db.close()


def get_step_logs(task_id: int) -> list[StepLog]:
    db = SessionLocal()

    try:
        stmt = (
            select(StepLog)
            .where(StepLog.task_id == task_id)
            .order_by(StepLog.id)
        )

        return db.execute(stmt).scalars().all()

    finally:
        db.close()

