from app.agent.state import AgentState
from langchain_openai import ChatOpenAI
import json
import os
from dotenv import load_dotenv
from app.tools.registry import TOOL_REGISTRY, get_tools_text
from langgraph.types import interrupt
load_dotenv()

# 导入env
KIMI_API_KEY = os.getenv("KIMI_API_KEY")
KIMI_BASE_URL = os.getenv("KIMI_BASE_URL")
KIMI_MODEL = os.getenv("KIMI_MODEL")


# plan
def plan_task(state: AgentState) -> dict:
    """
    根据当前任务，制定计划
    """

    llm = ChatOpenAI(
        model=KIMI_MODEL,
        temperature=1,
        openai_api_key=KIMI_API_KEY,
        base_url=KIMI_BASE_URL,
    )
    prompt = f"""
你是 Agent 的计划节点。

用户任务：
{state["Task"]}

请只生成 3-5 步内部执行计划。
要求：
1. 不要回答用户问题
2. 不要写教程
3. 不要写 Markdown 表格
4. 每一步只保留一句话
"""

    plan = llm.invoke(prompt)

    return {
        "plan": plan.content.split("\n"),
        "status": "planned",
        "step_logs":[
            {
                "node":"plan_task",
                "message":"生成任务计划",
                "status":"planned"
            }
        ]
    }


def select_tool(state: AgentState) -> dict:
    """
    根据计划，选择合适的工具
    """
    tools_text=get_tools_text()

    prompt = f"""
你是一个工具选择器。

用户任务：
{state["Task"]}

执行计划：
{state.get("plan", [])}

可用工具：
{tools_text}

请判断是否需要调用工具，并选择最合适的工具。

只返回 JSON，不要解释：
{{
  "need_tool": true,
  "selected_tool": "工具名",
  "tool_input": {{}}
}}
"""

    llm = ChatOpenAI(
        model=KIMI_MODEL,
        temperature=1,
        openai_api_key=KIMI_API_KEY,
        base_url=KIMI_BASE_URL,
    )

    response = llm.invoke(prompt)
    content = response.content.strip()
    content = content.removeprefix("```json").removesuffix("```").strip()
    result = json.loads(content)

    if not result.get("need_tool", True):
        return {
            "selected_tool": "mock_tool",
            "tool_input": {},
            "status": "tool_selected",
            "step_logs":[
                {
                    "node":"select_tool",
                    "message":"不需要真实工具，选择 mock_tool",
                    "status":"tool_selected"
                }
            ]
        }

    return {
        "selected_tool": result.get("selected_tool", "mock_tool"),
        "tool_input": result.get("tool_input", {}),
        "status": "tool_selected",
        "step_logs":[
            {
                "node":"select_tool",
                "message":f"选择工具 {result.get('selected_tool', 'mock_tool')}",
                "status":"tool_selected"
            }
        ]
    }

def check_approval(state: AgentState) -> dict:
    """
    如果工具风险较高，暂停等待用户审批
    """
    tool_name = state.get("selected_tool", "mock_tool")
    tool_info = TOOL_REGISTRY.get(tool_name, {})
    risk_level = tool_info.get("risk_level", "low")

    if risk_level == "high":
        decision=interrupt({
            "tool_name": tool_name,
            "tool_input": state.get("tool_input", {}),
            "risk_level": risk_level,
            "reason": f"工具 {tool_name} 风险等级为 high，需要用户审批",
        }
        )
        if decision.get("approved"):
            return {
            "approved": True,
            "approval_required": False,
            "approval_reason": None,
            "status": "approved",
            "step_logs":[
                {
                    "node":"check_approval",
                    "message":f"用户批准执行高风险工具 {tool_name}",
                    "status":"approved"
                }
            ]
        }
        return {
                "approved": False,
                "approval_required": True,
                "approval_reason":"用户拒绝了高风险工具的使用",
                "status": "rejected",
                "step_logs":[
                    {
                        "node":"check_approval",
                        "message":f"用户拒绝执行高风险工具 {tool_name}",
                        "status":"rejected"
                    }
                ]
            }

    return {
        "approved": True,
        "approval_required": False,
        "approval_reason": None,
        "status": "approved",
        "step_logs":[
            {
                "node":"check_approval",
                "message":f"工具 {tool_name} 风险等级为 {risk_level}，无需审批",
                "status":"approved"
            }
        ]
    }

def execute_tool(state: AgentState) -> dict:
    """
    执行选中的工具，获取结果
    """
    tool_name=state.get("selected_tool","mock_tool")
    tool_input=state.get("tool_input",{})
    
    tool_info=TOOL_REGISTRY.get(tool_name)
    
    if tool_info is None:
        return {
            "tool_output": {
                "success": False,
                "data": None,
                "error": f"未知工具：{tool_name}",
            },
            "status": "failed",
        }
    handler = tool_info["handler"]
    tool_output = handler(tool_input)          
   
    return {
        "tool_output": tool_output,
        "status": "tool_executed" if tool_output.get("success") else "failed",
        "step_logs":[
            {
                "node":"execute_tool",
                "message":f"执行工具 {tool_name}，结果：{tool_output}",
                "status":"tool_executed" if tool_output.get("success") else "failed"
            }
        ]
    }

def finalize_task(state: AgentState) -> dict:
    """
    根据工具结果，生成最终响应
    """
    tool_output = state.get("tool_output", {})

    prompt = f"""
根据工具执行结果，生成对用户的最终响应。

用户任务：
{state["Task"]}

用户计划：
{state.get("plan", [])}

工具名称：
{state.get("selected_tool", "")}

工具结果：
{tool_output}

要求：
1. 用简洁中文回答
2. 如果工具执行失败，说明失败原因
3. 不要编造工具结果中没有的信息
"""

    llm = ChatOpenAI(
        model=KIMI_MODEL,
        temperature=1,
        openai_api_key=KIMI_API_KEY,
        base_url=KIMI_BASE_URL,
    )

    final_response = llm.invoke(prompt).content.strip()
    if state.get("status") == "pending_approval":
        return {
        "final_response": state.get("approval_reason", "该操作需要用户审批"),
        "status": "pending_approval",
    }
    return {
        "final_response": final_response,
        "status": "completed" if tool_output.get("success") else "failed",
        "step_logs":[
            {
                "node":"finalize_task",
                "message":f"生成最终响应，状态：{'completed' if tool_output.get('success') else 'failed'}",
                "status":"completed" if tool_output.get("success") else "failed"
            }
        ]
    }

#路由函数
def route_after_approval(state: AgentState) -> str:
    if state.get("approved"):
        return "execute_tool"

    return "finalize_task"
