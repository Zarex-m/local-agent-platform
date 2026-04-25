from langgraph.types import Command
from app.agent.graph import app


def run_normal_task():
    config = {"configurable": {"thread_id": "normal-task-1"}}

    result = app.invoke(
        {
            "Task": "读取 requirements.txt",
            "status": "created",
        },
        config=config,
    )

    print(result)


def run_approval_task():
    config = {"configurable": {"thread_id": "approval-task-1"}}

    result = app.invoke(
        {
            "Task": "帮我写入 demo.txt，内容是 hello",
            "status": "created",
        },
        config=config,
    )

    print(result)

    if "__interrupt__" in result:
        resumed = app.invoke(
            Command(resume={"approved": True}),
            config=config,
        )
        print(resumed)


if __name__ == "__main__":
    run_normal_task()
    run_approval_task()
