from app.services.agent_service import (
    approve_task,
    create_task_job,
    run_task_background,
)
from app.services.attachment_service import build_task_with_attachments
from app.storage import task_repository as task_repo


TERMINAL_STATUSES = {"completed", "failed", "rejected", "cancelled"}


class TaskServiceError(Exception):
    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def create_task_submission(
    task_text: str,
    conversation_id: int | None,
    attachment_paths: list[str],
) -> tuple[dict, str]:
    agent_task = build_task_with_attachments(task_text, attachment_paths)
    payload = create_task_job(task_text, conversation_id)
    return payload, agent_task


def enqueue_task(background_tasks, payload: dict, agent_task: str) -> None:
    background_tasks.add_task(
        run_task_background,
        payload["task_id"],
        payload["thread_id"],
        agent_task,
        payload["conversation_id"],
    )


def get_task(task_id: int):
    return task_repo.get_task(task_id)


def get_task_or_error(task_id: int):
    task = get_task(task_id)

    if task is None:
        raise TaskServiceError("Task not found", status_code=404)

    return task


def list_tasks(limit: int = 20):
    return task_repo.list_tasks(limit)


def get_step_logs(task_id: int):
    return task_repo.get_step_logs(task_id)


def get_tool_calls(task_id: int):
    return task_repo.get_tool_calls(task_id)


def approve_task_request(task_id: int, approved: bool) -> dict:
    task = get_task_or_error(task_id)

    if task.thread_id is None:
        raise TaskServiceError("task thread_id is missing")

    return approve_task(task_id, task.thread_id, approved)


def request_cancel(task_id: int) -> dict:
    task = get_task_or_error(task_id)

    if task.status in TERMINAL_STATUSES:
        return {"task_id": task_id, "status": task.status}

    task_repo.request_cancel_task(task_id)
    return {"task_id": task_id, "status": "cancelled"}
