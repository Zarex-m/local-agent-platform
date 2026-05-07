import json

from app.storage.database import SessionLocal, Task, StepLog, ToolCall

from sqlalchemy import select,delete

def create_task(
    task_text: str,
    thread_id: str,
    status: str = "created",
) -> int:
    db = SessionLocal()

    try:
        task = Task(
            task=task_text,
            status=status,
            thread_id=thread_id,
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

def list_tasks(limit:int=20)->list[Task]:
    db=SessionLocal()
    try:
        stmt=select(Task).order_by(Task.id.desc()).limit(limit)
        return db.execute(stmt).scalars().all()
    finally:
        db.close()
        
def save_tool_calls(task_id: int, tool_history: list[dict]) -> None:
    db = SessionLocal()

    try:
        db.execute(delete(ToolCall).where(ToolCall.task_id == task_id))
        for item in tool_history:
            step = item.get("step", {})
            tool_output = item.get("tool_output", {})

            tool_call = ToolCall(
                task_id=task_id,
                step_index=step.get("index"),
                step_description=step.get("description"),
                tool_name=item.get("tool_name", ""),
                tool_input=json.dumps(item.get("tool_input"), ensure_ascii=False),
                tool_output=json.dumps(tool_output, ensure_ascii=False),
                risk_level=item.get("risk_level"),
                approved=item.get("approved"),
                success=tool_output.get("success"),
            )
            db.add(tool_call)

        db.commit()
    finally:
        db.close()

def get_tool_calls(task_id: int) -> list[dict]:
    db = SessionLocal()
    try:
        stmt = (
            select(ToolCall)
            .where(ToolCall.task_id == task_id)
            .order_by(ToolCall.id)
        )
        tool_calls = db.execute(stmt).scalars().all()

        return [
            {
                "id": item.id,
                "task_id": item.task_id,
                "step_index": item.step_index,
                "step_description": item.step_description,
                "tool_name": item.tool_name,
                "tool_input": parse_json_field(item.tool_input),
                "tool_output": parse_json_field(item.tool_output),
                "risk_level": item.risk_level,
                "approved": item.approved,
                "success": item.success,
                "created_at": item.created_at,
            }
            for item in tool_calls
        ]
    finally:
        db.close()


def parse_json_field(value):
    if value is None:
        return None

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value
