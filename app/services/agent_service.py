from langgraph.types import Command

from app.agent.graph import app
from app.storage.database import init_db
from app.storage import task_repository as task_repo
from uuid import uuid4

def run_task(task_text: str) -> dict:
    init_db()

    thread_id = str(uuid4())
    task_id = task_repo.create_task(task_text, thread_id)


    result = app.invoke(
        {
            "Task": task_text,
            "status": "created",
        },
        config={"configurable": {"thread_id": thread_id}},
    )

    state_to_save = dict(result)
    if "__interrupt__" in result:
        interrupts = result.get("__interrupt__", [])
        interrupt_value = interrupts[0].value if interrupts else {}
        state_to_save.update(
            {
                "status": "pending_approval",
                "approval_required": True,
                "approval_reason": interrupt_value.get("reason", "该操作需要用户审批"),
            }
        )

    task_repo.update_task(task_id, state_to_save)
    task_repo.save_step_logs(task_id, state_to_save.get("step_logs", []))

    return {
        "task_id": task_id,
        "thread_id": thread_id,
        "result": state_to_save,
    }


def approve_task(task_id: int, thread_id: str, approved: bool) -> dict:
    init_db()

    resumed = app.invoke(
        Command(resume={"approved": approved}),
        config={"configurable": {"thread_id": thread_id}},
    )

    task_repo.update_task(task_id, resumed)
    task_repo.save_step_logs(task_id, resumed.get("step_logs", []))

    return {
        "task_id": task_id,
        "thread_id": thread_id,
        "result": resumed,
    }
