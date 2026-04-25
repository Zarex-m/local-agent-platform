from langgraph.types import Command
from app.agent.graph import app

config = {"configurable": {"thread_id": "task-1"}}

result = app.invoke({
    "Task": "帮我写入 demo.txt，内容是 hello",
    "status": "created",
},
    config=config,
)

print(result)

resumed = app.invoke(
    Command(resume={"approved": True}),
    config=config,
)
print(resumed)
