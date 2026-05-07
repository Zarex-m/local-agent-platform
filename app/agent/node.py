import time

from app.agent.state import AgentState
from app.agent.llm import invoke_llm, invoke_llm_json, invoke_llm_stream
from app.storage import task_repository as task_repo
from app.tools.registry import TOOL_REGISTRY, get_tools_text
from langgraph.types import interrupt


# plan
def plan_task(state: AgentState) -> dict:
    """
    根据当前任务，制定计划
    """

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
        plan_content = invoke_llm(prompt)
    except Exception as e:
        default_steps = [
            {
                "index": 1,
                "description": "使用可用工具完成用户任务",
                "status": "pending",
            }
        ]
        return {
            "plan": ["模型调用失败,使用可用工具完成用户任务"],
            "plan_steps": default_steps,
            "current_step": default_steps[0],
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
    raw_steps = [line.strip() for line in plan_content.split("\n") if line.strip()]

    plan_steps = [
        {
            "index": index + 1,
            "description": step,
            "status": "pending",
        }
        for index, step in enumerate(raw_steps)
    ]
    return {
        "plan": raw_steps,
        "plan_steps": plan_steps,
        "current_step": plan_steps[0] if plan_steps else {},
        "status": "planned",
        "step_logs": [
            {"node": "plan_task", "message": "生成结构化任务计划", "status": "planned"}
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

结构化计划：
{state.get("plan_steps", [])}

当前应执行步骤：
{state.get("current_step", {})}

已执行工具历史：
{state.get("tool_history", [])}

当前执行轮次：
{state.get("iterations", 0)}

可用工具：
{tools_text}

工具选择规则：
1. 如果用户要列出目录、查看目录下有哪些文件、查看项目结构，选择 list_files。
2. 如果用户要读取、查看、总结、分析某个文件的内容，必须选择 read_file。
3. 如果用户要创建、写入、修改、覆盖某个文件，选择 write_file。
4. 如果用户的问题不需要访问文件、不需要执行真实操作，选择 mock_tool。
5. 不要选择不存在于可用工具列表中的工具。
6. 工具参数必须严格匹配该工具的参数说明。
7.如果用户要执行 shell 命令、运行测试、运行脚本、安装依赖、查看命令输出，选择 run_shell。
8.如果用户要访问 URL、请求 API、测试 HTTP 接口、发送 GET/POST/PUT/DELETE 请求，选择 http_request。
9.如果任务适合某个 MCP 工具，并且该工具出现在可用工具列表中，可以选择名称以 mcp. 开头的工具。
10. 如果已执行工具历史已经满足用户任务，不要重复选择相同工具。
11. 如果任务需要多步完成，请根据历史结果选择下一步工具。
12. 如果用户要求先做 A 再做 B，应按顺序选择尚未执行的下一步工具。
13. 优先根据 current_step 选择工具，而不是重新理解整个任务。
14. 如果 current_step 是读取文件，选择 read_file。
15. 如果 current_step 是列出目录，选择 list_files。
16. 如果 current_step 是总结、分析、回答，并且已有工具历史足够支撑，可以选择 mock_tool 并设置 need_tool 为 false。

路径参数规则：
1. 如果用户明确给出文件名或目录名，必须提取为 path。
2. 例如 requirements.txt、README.md、app、docs 都应该作为 path。
3. 如果用户要列出当前目录，path 使用 "."。
4. 如果无法确定路径，path 使用 "."。
5.如果用户没有指定 cwd，cwd 使用 "."。
6.如果用户没有指定 timeout，timeout 使用 30。

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

示例 5：
用户任务：运行 pytest
返回：
{{
  "need_tool": true,
  "selected_tool": "run_shell",
  "tool_input": {{"command": "pytest", "cwd": ".", "timeout": 60}}
}}

示例 6：
用户任务：请求 http://127.0.0.1:8000/tasks
返回：
{{
  "need_tool": true,
  "selected_tool": "http_request",
  "tool_input": {{
    "method": "GET",
    "url": "http://127.0.0.1:8000/tasks",
    "headers": {{}},
    "params": {{}},
    "timeout": 30
  }}
}}

示例 7：
用户任务：向 http://127.0.0.1:8000/tasks 提交任务 hello
返回：
{{
  "need_tool": true,
  "selected_tool": "http_request",
  "tool_input": {{
    "method": "POST",
    "url": "http://127.0.0.1:8000/tasks",
    "headers": {{"Content-Type": "application/json"}},
    "json": {{"task": "hello"}},
    "timeout": 30
  }}
}}


请只返回 JSON，不要解释，不要 Markdown，不要代码块。
JSON 格式如下：
{{
  "need_tool": true,
  "selected_tool": "工具名",
  "tool_input": {{}}
}}
"""

    result = invoke_llm_json(
        prompt,
        default={
            "need_tool": True,
            "selected_tool": "mock_tool",
            "tool_input": {},
        },
    )

    if result.get("_error"):
        return {
            "selected_tool": "mock_tool",
            "tool_input": {},
            "status": "tool_selected",
            "error": f"select_tool 模型调用失败：{result['_error']}",
            "step_logs": [
                {
                    "node": "select_tool",
                    "message": f"模型调用失败，降级选择 mock_tool：{result['_error']}",
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

    next_iterations = state.get("iterations", 0) + 1

    return {
        "tool_output": tool_output,
        "iterations": next_iterations,
        "status": "tool_executed" if tool_output.get("success") else "failed",
        "tool_history": [
            {
                "step": state.get("current_step", {}),
                "tool_name": tool_name,
                "tool_input": tool_input,
                "tool_output": tool_output,
                "risk_level": tool_info.get("risk_level"),
                "approved": state.get("approved"),
            }
        ],
        "step_logs": [
            {
                "node": "execute_tool",
                "message": f"执行工具 {tool_name}，结果：{tool_output}",
                "status": "tool_executed" if tool_output.get("success") else "failed",
            }
        ],
    }

def update_plan_step(state: AgentState) -> dict:
    """
    根据刚刚的工具执行结果，更新当前计划步骤状态
    """
    plan_steps = state.get("plan_steps", [])
    current_step = state.get("current_step", {})
    tool_output = state.get("tool_output", {})

    if not plan_steps or not current_step:
        return {
            "plan_steps": plan_steps,
            "current_step": {},
            "step_logs": [
                {
                    "node": "update_plan_step",
                    "message": "没有可更新的计划步骤",
                    "status": "planned",
                }
            ],
        }

    current_index = current_step.get("index")

    updated_steps = []
    for step in plan_steps:
        if step.get("index") == current_index:
            updated_steps.append(
                {
                    **step,
                    "status": "completed" if tool_output.get("success") else "failed",
                }
            )
        else:
            updated_steps.append(step)

    next_step = {}
    for step in updated_steps:
        if step.get("status") == "pending":
            next_step = step
            break

    return {
        "plan_steps": updated_steps,
        "current_step": next_step,
        "status": "plan_updated",
        "step_logs": [
            {
                "node": "update_plan_step",
                "message": f"更新计划步骤 {current_index}，下一步：{next_step or '无'}",
                "status": "plan_updated",
            }
        ],
    }


def decide_next_step(state: AgentState) -> dict:
    """
    判断任务是否需要继续调用工具
    """
    iterations = state.get("iterations", 0)
    max_iterations = state.get("max_iterations", 3)

    if iterations >= max_iterations:
        return {
            "next_action": "finish",
            "status": "decided",
            "step_logs": [
                {
                    "node": "decide_next_step",
                    "message": f"已达到最大执行轮次 {max_iterations}，结束任务",
                    "status": "decided",
                }
            ],
        }
    
    current_step = state.get("current_step", {})
    plan_steps = state.get("plan_steps", [])
    if not current_step:
        return{
            "next_action": "finish",
            "status": "decided",
            "step_logs": [{
                "node": "decide_next_step",
                "message": f"没有当前步骤，结束任务",
                "status": "decided",
            }]
        }
    
    if not state.get("tool_output", {}).get("success", False):
        return {
            "next_action": "finish",
            "status": "decided",
            "step_logs": [
                {
                    "node": "decide_next_step",
                    "message": f"工具执行失败，结束任务",
                    "status": "decided",
                }
            ],
        }

    current_step_description = str(current_step.get("description", ""))
    finish_keywords = ["总结", "分析", "回答", "回复", "归纳", "说明", "解析"]
    if any(keyword in current_step_description for keyword in finish_keywords):
        return {
            "next_action": "finish",
            "status": "decided",
            "step_logs": [
                {
                    "node": "decide_next_step",
                    "message": f"当前步骤适合直接生成最终回答：{current_step}",
                    "status": "decided",
                }
            ],
        }

    if current_step and state.get("tool_output", {}).get("success"):
        return {
        "next_action": "continue",
        "status": "decided",
        "step_logs": [
            {
                "node": "decide_next_step",
                "message": f"还有待执行步骤：{current_step}",
                "status": "decided",
            }
        ],
    }

    prompt = f"""
你是 Agent 的任务进度判断节点。

用户任务：
{state["Task"]}

执行计划：
{state.get("plan", [])}

已执行工具历史：
{state.get("tool_history", [])}

当前执行轮次：
{iterations}

最大执行轮次：
{max_iterations}

请判断用户任务是否已经完成。

判断规则：
1. 如果工具历史已经足够回答用户任务，返回 finish。
2. 如果用户任务明确包含多个步骤，并且还有步骤没有执行，返回 continue。
3. 如果继续执行也不会获得更多有用信息，返回 finish。
4. 如果不确定，优先返回 finish，避免重复循环。

只返回 JSON，不要解释，不要 Markdown。
格式：
{{
  "next_action": "continue 或 finish",
  "reason": "简短原因"
}}
"""
    result = invoke_llm_json(
        prompt,
        default={
            "next_action": "finish",
            "reason": "LLM 判断失败，默认结束",
        },
    )

    if result.get("_error"):
        return {
            "next_action": "finish",
            "status": "decided",
            "error": f"decide_next_step 模型调用失败：{result['_error']}",
            "step_logs": [
                {
                    "node": "decide_next_step",
                    "message": f"判断失败，默认结束：{result['_error']}",
                    "status": "decided",
                }
            ],
        }
    next_action = result.get("next_action", "finish")
    if next_action not in ["continue", "finish"]:
        next_action = "finish"
    return {
        "next_action": next_action,
        "status": "decided",
        "step_logs": [
            {
                "node": "decide_next_step",
                "message": f"判断下一步动作：{next_action}，原因：{result.get('reason','无')}",
                "status": "decided",
            }
        ],
    }


def finalize_task(state: AgentState) -> dict:
    """
    根据工具结果，生成最终响应
    """
    tool_output = state.get("tool_output", {})

    if state.get("status") == "pending_approval":
        return {
            "final_response": state.get("approval_reason", "该操作需要用户审批"),
            "status": "pending_approval",
        }

    final_status = "completed" if tool_output.get("success") else "failed"

    prompt = f"""
根据工具执行结果，生成对用户的最终响应。

用户任务：
{state["Task"]}

用户计划：
{state.get("plan", [])}

结构化计划完成情况：
{state.get("plan_steps", [])}

工具名称：
{state.get("selected_tool", "")}

工具结果：
{tool_output}

最近一次工具结果：
{tool_output}

完整工具执行历史：
{state.get("tool_history", [])}

要求：
1. 用简洁中文回答
2. 如果工具执行失败，说明失败原因
3. 不要编造工具结果中没有的信息
"""

    final_response = ""
    task_id = state.get("task_id")
    should_stream = bool(state.get("stream_final_response") and task_id)

    try:
        if should_stream:
            task_repo.update_task(
                task_id,
                {
                    "status": "finalizing",
                    "final_response": "",
                },
            )
            last_flush_at = time.monotonic()

            for token in invoke_llm_stream(prompt):
                final_response += token
                now = time.monotonic()

                if now - last_flush_at >= 0.08:
                    task_repo.update_task(
                        task_id,
                        {
                            "status": "finalizing",
                            "final_response": final_response,
                        },
                    )
                    last_flush_at = now

            task_repo.update_task(
                task_id,
                {
                    "status": final_status,
                    "final_response": final_response,
                },
            )
        else:
            final_response = invoke_llm(prompt)
    except Exception as e:
        fallback_response = final_response or f"任务已执行，但生成最终回复时失败：{str(e)}"
        if should_stream:
            task_repo.update_task(
                task_id,
                {
                    "status": final_status,
                    "final_response": fallback_response,
                },
            )

        return {
            "final_response": fallback_response,
            "status": final_status,
            "error": f"finalize_task 模型调用失败：{str(e)}",
            "step_logs": [
                {
                    "node": "finalize_task",
                    "message": f"模型调用失败，使用兜底回复：{str(e)}",
                    "status": final_status,
                }
            ],
        }

    return {
        "final_response": final_response,
        "status": final_status,
        "step_logs": [
            {
                "node": "finalize_task",
                "message": f"生成最终响应，状态：{final_status}",
                "status": final_status,
            }
        ],
    }


# 路由函数
def route_after_approval(state: AgentState) -> str:
    if state.get("approved"):
        return "execute_tool"

    return "finalize_task"


def route_after_decide(state: AgentState) -> str:
    if state.get("next_action") == "continue":
        return "select_tool"

    return "finalize_task"
