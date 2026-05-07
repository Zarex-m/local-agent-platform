from app.agent.state import AgentState
from app.agent.node import (
    plan_task,
    select_tool,
    check_approval,
    route_after_approval,
    execute_tool,
    decide_next_step,
    route_after_decide,
    finalize_task,
    update_plan_step,
)

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
checkpoint = MemorySaver()



graph = StateGraph(AgentState)


graph.add_node("plan_task", plan_task)
graph.add_node("select_tool", select_tool)
graph.add_node("execute_tool", execute_tool)
graph.add_node("finalize_task", finalize_task)
graph.add_node("check_approval", check_approval)
graph.add_node("decide_next_step", decide_next_step)
graph.add_node("update_plan_step", update_plan_step)

graph.add_edge(START, "plan_task")
graph.add_edge("plan_task", "select_tool")
graph.add_edge("select_tool", "check_approval")
graph.add_edge("execute_tool", "update_plan_step")
graph.add_edge("update_plan_step", "decide_next_step")
graph.add_edge("finalize_task", END)

#条件路由
graph.add_conditional_edges(
    "check_approval",
    route_after_approval,
    {
    "execute_tool": "execute_tool",
    "finalize_task": "finalize_task", 
    }
)

graph.add_conditional_edges(
    "decide_next_step",
    route_after_decide,
    {
        "select_tool": "select_tool",
        "finalize_task": "finalize_task",
    }
)

app=graph.compile(checkpointer=checkpoint)
