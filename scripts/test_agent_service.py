from app.services.agent_service import approve_task, run_task


def print_summary(label: str, payload: dict) -> None:
    result = payload["result"]

    print(f"\n[{label}]")
    print("task_id:", payload["task_id"])
    print("thread_id:", payload["thread_id"])
    print("status:", result.get("status"))
    print("selected_tool:", result.get("selected_tool"))
    print("tool_input:", result.get("tool_input"))
    print("has_interrupt:", "__interrupt__" in result)
    print("step_logs_count:", len(result.get("step_logs", [])))

    final_response = result.get("final_response")
    if final_response:
        print("final_response:", final_response[:300])


def run_normal_case() -> None:
    payload = run_task("读取 requirements.txt")
    print_summary("normal task", payload)


def run_approval_case() -> None:
    payload = run_task("帮我写入 service_demo.txt，内容是 hello")
    print_summary("approval task before resume", payload)

    if "__interrupt__" not in payload["result"]:
        return

    resumed = approve_task(
        task_id=payload["task_id"],
        thread_id=payload["thread_id"],
        approved=True,
    )
    print_summary("approval task after resume", resumed)


if __name__ == "__main__":
    run_normal_case()
    run_approval_case()
