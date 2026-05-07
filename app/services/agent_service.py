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
        "iterations": 0,
        "max_iterations": 3,
        "tool_history": [],
        "plan_steps": [],
        "current_step": {},
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
    task_repo.save_tool_calls(task_id, state_to_save.get("tool_history", []))


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
    task_repo.save_tool_calls(task_id, resumed.get("tool_history", []))

    return {
        "task_id": task_id,
        "thread_id": thread_id,
        "result": resumed,
    }

def create_task_job(task_text:str)->dict:
    init_db()
    
    thread_id = str(uuid4())
    task_id = task_repo.create_task(task_text, thread_id)
    
    return{
        "task_id": task_id,
        "thread_id": thread_id,
        "result": {
            "status":"running"
        }
    }
    
def run_task_background(task_id: int, thread_id: str, task_text: str) -> None:
    init_db()

    initial_state = {
        "Task": task_text,
        "status": "created",
        "iterations": 0,
        "max_iterations": 3,
        "tool_history": [],
        "plan_steps": [],
        "current_step": {},
    }

    config = {"configurable": {"thread_id": thread_id}}
    tool_history: list[dict] = []

    try:
        for chunk in app.stream(initial_state, config=config, stream_mode="updates"):
            if "__interrupt__" in chunk:
                interrupts = chunk.get("__interrupt__", [])
                interrupt_value = interrupts[0].value if interrupts else {}

                task_repo.update_task(
                    task_id,
                    {
                        "status": "pending_approval",
                        "approval_required": True,
                        "approval_reason": interrupt_value.get(
                            "reason",
                            "该操作需要用户审批",
                        ),
                    },
                )
                return

            for _node_name, update in chunk.items():
                if not isinstance(update, dict):
                    continue

                task_repo.update_task(task_id, update)

                if update.get("step_logs"):
                    task_repo.save_step_logs(task_id, update["step_logs"])

                if update.get("tool_history"):
                    tool_history.extend(update["tool_history"])
                    task_repo.save_tool_calls(task_id, tool_history)

    except Exception as e:
        task_repo.update_task(
            task_id,
            {
                "status": "failed",
                "final_response": f"任务执行失败：{str(e)}",
            },
        )
        task_repo.save_step_logs(
            task_id,
            [
                {
                    "node": "agent_service",
                    "status": "failed",
                    "message": f"后台任务执行失败：{str(e)}",
                }
            ],
        )
