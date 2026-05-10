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

NODE_PLAN = "plan_task"
NODE_SELECT_TOOL = "select_tool"
NODE_CHECK_APPROVAL = "check_approval"
NODE_EXECUTE_TOOL = "execute_tool"
NODE_UPDATE_PLAN = "update_plan_step"
NODE_DECIDE_NEXT = "decide_next_step"
NODE_FINALIZE = "finalize_task"


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node(NODE_PLAN, plan_task)
    graph.add_node(NODE_SELECT_TOOL, select_tool)
    graph.add_node(NODE_CHECK_APPROVAL, check_approval)
    graph.add_node(NODE_EXECUTE_TOOL, execute_tool)
    graph.add_node(NODE_UPDATE_PLAN, update_plan_step)
    graph.add_node(NODE_DECIDE_NEXT, decide_next_step)
    graph.add_node(NODE_FINALIZE, finalize_task)

    graph.add_edge(START, NODE_PLAN)
    graph.add_edge(NODE_PLAN, NODE_SELECT_TOOL)
    graph.add_edge(NODE_SELECT_TOOL, NODE_CHECK_APPROVAL)
    graph.add_edge(NODE_EXECUTE_TOOL, NODE_UPDATE_PLAN)
    graph.add_edge(NODE_UPDATE_PLAN, NODE_DECIDE_NEXT)
    graph.add_edge(NODE_FINALIZE, END)

    graph.add_conditional_edges(
        NODE_CHECK_APPROVAL,
        route_after_approval,
        {
            NODE_EXECUTE_TOOL: NODE_EXECUTE_TOOL,
            NODE_FINALIZE: NODE_FINALIZE,
        },
    )

    graph.add_conditional_edges(
        NODE_DECIDE_NEXT,
        route_after_decide,
        {
            NODE_SELECT_TOOL: NODE_SELECT_TOOL,
            NODE_FINALIZE: NODE_FINALIZE,
        },
    )

    return graph


checkpoint = MemorySaver()
app = build_graph().compile(checkpointer=checkpoint)
