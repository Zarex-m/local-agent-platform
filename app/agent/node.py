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

    try:
        plan = llm.invoke(prompt)
    except Exception as e:
        return {
            "plan": ["模型调用失败，使用默认计划"],
            "status": "planned",
            "error": f"plan_task 模型调用失败：{str(e)}",
            "step_logs": [
                {
                    "node": "plan_task",
                    "message": f"模型调用失败，使用默认计划：{str(e)}",
                    "status": "planned",
                }
            ],
        }

    return {
        "plan": plan.content.split("\n"),
        "status": "planned",
        "step_logs": [
            {"node": "plan_task", "message": "生成任务计划", "status": "planned"}
        ],
    }


def select_tool(state: AgentState) -> dict:
    """
    根据计划，选择合适的工具
    """
    tools_text = get_tools_text()

    prompt = f"""
你是一个严格的 Agent 工具选择器。

你的任务是根据用户任务和执行计划，从可用工具中选择一个最合适的工具，并生成工具参数。

用户任务：
{state["Task"]}

执行计划：
{state.get("plan", [])}

可用工具：
{tools_text}

工具选择规则：
1. 如果用户要列出目录、查看目录下有哪些文件、查看项目结构，选择 list_files。
2. 如果用户要读取、查看、总结、分析某个文件的内容，必须选择 read_file。
3. 如果用户要创建、写入、修改、覆盖某个文件，选择 write_file。
4. 如果用户的问题不需要访问文件、不需要执行真实操作，选择 mock_tool。
5. 不要选择不存在于可用工具列表中的工具。
6. 工具参数必须严格匹配该工具的参数说明。

路径参数规则：
1. 如果用户明确给出文件名或目录名，必须提取为 path。
2. 例如 requirements.txt、README.md、app、docs 都应该作为 path。
3. 如果用户要列出当前目录，path 使用 "."。
4. 如果无法确定路径，path 使用 "."。

示例 1：
用户任务：读取 requirements.txt
返回：
{{
  "need_tool": true,
  "selected_tool": "read_file",
  "tool_input": {{"path": "requirements.txt"}}
}}

示例 2：
用户任务：帮我列出 app 目录下的文件
返回：
{{
  "need_tool": true,
  "selected_tool": "list_files",
  "tool_input": {{"path": "app"}}
}}

示例 3：
用户任务：帮我写入 demo.txt，内容是 hello
返回：
{{
  "need_tool": true,
  "selected_tool": "write_file",
  "tool_input": {{"path": "demo.txt", "content": "hello"}}
}}

示例 4：
用户任务：给我一个学习 LangGraph 的计划
返回：
{{
  "need_tool": false,
  "selected_tool": "mock_tool",
  "tool_input": {{}}
}}

请只返回 JSON，不要解释，不要 Markdown，不要代码块。
JSON 格式如下：
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

    try:
        response = llm.invoke(prompt)
    except Exception as e:
        return {
            "selected_tool": "mock_tool",
            "tool_input": {},
            "status": "tool_selected",
            "error": f"select_tool 模型调用失败：{str(e)}",
            "step_logs": [
                {
                    "node": "select_tool",
                    "message": f"模型调用失败，降级选择 mock_tool：{str(e)}",
                    "status": "tool_selected",
                }
            ],
        }
    content = response.content.strip()
    content = content.removeprefix("```json").removesuffix("```").strip()
    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        return {
            "selected_tool": "mock_tool",
            "tool_input": {},
            "status": "tool_selected",
            "step_logs": [
                {
                    "node": "select_tool",
                    "message": "解析工具选择结果失败，默认选择 mock_tool",
                    "status": "tool_selected",
                }
            ],
        }

    if not result.get("need_tool", True):
        return {
            "selected_tool": "mock_tool",
            "tool_input": {},
            "status": "tool_selected",
            "step_logs": [
                {
                    "node": "select_tool",
                    "message": "不需要真实工具，选择 mock_tool",
                    "status": "tool_selected",
                }
            ],
        }

    return {
        "selected_tool": result.get("selected_tool", "mock_tool"),
        "tool_input": result.get("tool_input", {}),
        "status": "tool_selected",
        "step_logs": [
            {
                "node": "select_tool",
                "message": f"选择工具 {result.get('selected_tool', 'mock_tool')}",
                "status": "tool_selected",
            }
        ],
    }


def check_approval(state: AgentState) -> dict:
    """
    如果工具风险较高，暂停等待用户审批
    """
    tool_name = state.get("selected_tool", "mock_tool")
    tool_info = TOOL_REGISTRY.get(tool_name, {})
    risk_level = tool_info.get("risk_level", "low")

    if risk_level == "high":
        decision = interrupt(
            {
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
                "step_logs": [
                    {
                        "node": "check_approval",
                        "message": f"用户批准执行高风险工具 {tool_name}",
                        "status": "approved",
                    }
                ],
            }
        return {
            "approved": False,
            "approval_required": True,
            "approval_reason": "用户拒绝了高风险工具的使用",
            "status": "rejected",
            "step_logs": [
                {
                    "node": "check_approval",
                    "message": f"用户拒绝执行高风险工具 {tool_name}",
                    "status": "rejected",
                }
            ],
        }

    return {
        "approved": True,
        "approval_required": False,
        "approval_reason": None,
        "status": "approved",
        "step_logs": [
            {
                "node": "check_approval",
                "message": f"工具 {tool_name} 风险等级为 {risk_level}，无需审批",
                "status": "approved",
            }
        ],
    }


def execute_tool(state: AgentState) -> dict:
    """
    执行选中的工具，获取结果
    """
    tool_name = state.get("selected_tool", "mock_tool")
    tool_input = state.get("tool_input", {})

    tool_info = TOOL_REGISTRY.get(tool_name)

    if tool_info is None:
        return {
            "tool_output": {
                "success": False,
                "data": None,
                "error": f"未知工具：{tool_name}",
            },
            "status": "failed",
            "step_logs": [
                {
                    "node": "execute_tool",
                    "message": f"未知工具：{tool_name}",
                    "status": "failed",
                }
            ],
        }
    handler = tool_info["handler"]
    tool_output = handler(tool_input)

    return {
        "tool_output": tool_output,
        "status": "tool_executed" if tool_output.get("success") else "failed",
        "step_logs": [
            {
                "node": "execute_tool",
                "message": f"执行工具 {tool_name}，结果：{tool_output}",
                "status": "tool_executed" if tool_output.get("success") else "failed",
            }
        ],
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

    try:
        final_response = llm.invoke(prompt).content.strip()
    except Exception as e:
        return {
            "final_response": f"任务已执行，但生成最终回复时失败：{str(e)}",
            "status": "completed" if tool_output.get("success") else "failed",
            "error": f"finalize_task 模型调用失败：{str(e)}",
            "step_logs": [
                {
                    "node": "finalize_task",
                    "message": f"模型调用失败，使用兜底回复：{str(e)}",
                    "status": "completed" if tool_output.get("success") else "failed",
                }
            ],
        }

    if state.get("status") == "pending_approval":
        return {
            "final_response": state.get("approval_reason", "该操作需要用户审批"),
            "status": "pending_approval",
        }
    return {
        "final_response": final_response,
        "status": "completed" if tool_output.get("success") else "failed",
        "step_logs": [
            {
                "node": "finalize_task",
                "message": f"生成最终响应，状态：{'completed' if tool_output.get('success') else 'failed'}",
                "status": "completed" if tool_output.get("success") else "failed",
            }
        ],
    }


# 路由函数
def route_after_approval(state: AgentState) -> str:
    if state.get("approved"):
        return "execute_tool"

    return "finalize_task"
