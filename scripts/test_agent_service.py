from app.services.agent_service import approve_task, run_task


def print_summary(label: str, payload: dict) -> None:
    result = payload["result"]
    tool_history = result.get("tool_history", [])

    print(f"\n[{label}]")
    print("task_id:", payload["task_id"])
    print("thread_id:", payload["thread_id"])
    print("status:", result.get("status"))
    print("selected_tool:", result.get("selected_tool"))
    print("tool_input:", result.get("tool_input"))
    print("has_interrupt:", "__interrupt__" in result)
    print("step_logs_count:", len(result.get("step_logs", [])))
    print("tool_history_count:", len(tool_history))
    print("tool_history_tools:", [item.get("tool_name") for item in tool_history])

    final_response = result.get("final_response")
    if final_response:
        print("final_response:", final_response[:300])


def run_normal_case() -> None:
    payload = run_task("读取 requirements.txt")
    print_summary("normal task", payload)


def run_multi_tool_case() -> None:
    payload = run_task("先列出当前目录，再读取 requirements.txt，然后总结依赖")
    print_summary("multi-tool task", payload)


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
    run_multi_tool_case()
    run_approval_case()
