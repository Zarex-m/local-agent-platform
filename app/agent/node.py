import time

from app.agent.state import AgentState
from app.agent.llm import invoke_llm, invoke_llm_json, invoke_llm_stream
from app.storage import task_repository as task_repo
from app.tools.registry import TOOL_REGISTRY, get_tools_text, is_tool_enabled
from langgraph.types import interrupt
from app.tools.safety import analyze_tool_risk, format_risk_reason

LOG_STARTED = "started"
LOG_SUCCESS = "success"
LOG_WAITING_APPROVAL = "waiting_approval"
LOG_FAILED = "failed"
LOG_SKIPPED = "skipped"

PERSISTENT_ACTION_KEYWORDS = [
    "保存",
    "写入",
    "生成文件",
    "输出到",
    "移动",
    "复制",
    "重命名",
    "归档",
    "报告保存",
    "reports/",
]

PERSISTENT_ACTION_TOOLS = {
    "write_file",
    "mcp.workspace.write_markdown_report",
    "mcp.workspace.move_file",
    "mcp.workspace.copy_file",
    "mcp.workspace.rename_file",
}

MAX_STEP_RETRIES = 2

RECOVERABLE_ERROR_KEYWORDS = [
    "not found",
    "no such file",
    "不存在",
    "路径",
    "path",
    "required",
    "missing",
    "invalid",
    "参数",
    "未知工具",
    "停用",
]


def append_runtime_log(state: AgentState, node: str, status: str, message: str) -> None:
    task_id = state.get("task_id")
    if not task_id:
        return

    try:
        task_repo.append_step_log(task_id, node, status, message)
    except Exception:
        pass


def task_requires_persistent_action(state: AgentState) -> bool:
    task_text = state.get("Task", "")
    criteria_text = " ".join(str(item) for item in state.get("completion_criteria", []))
    combined_text = f"{task_text}\n{criteria_text}"

    return any(keyword in combined_text for keyword in PERSISTENT_ACTION_KEYWORDS)


def has_successful_persistent_action(state: AgentState) -> bool:
    for item in state.get("tool_history", []):
        tool_name = item.get("tool_name", "")
        tool_output = item.get("tool_output", {})

        if tool_name not in PERSISTENT_ACTION_TOOLS:
            continue

        if tool_output.get("success"):
            return True

    return False


def get_tool_error_text(tool_output: dict) -> str:
    if not isinstance(tool_output, dict):
        return str(tool_output)

    error = (
        tool_output.get("error")
        or tool_output.get("message")
        or tool_output.get("data")
        or tool_output
    )
    return str(error)


def is_recoverable_tool_failure(tool_output: dict) -> bool:
    error_text = get_tool_error_text(tool_output).lower()
    return any(keyword.lower() in error_text for keyword in RECOVERABLE_ERROR_KEYWORDS)


def get_completion_blocker(state: AgentState) -> str | None:
    if task_requires_persistent_action(state) and not has_successful_persistent_action(state):
        return "任务要求保存、写入或生成文件，但没有成功的持久化工具调用。"

    tool_output = state.get("tool_output", {})
    if isinstance(tool_output, dict) and tool_output.get("success") is False:
        return f"最后一次工具调用失败：{get_tool_error_text(tool_output)}"

    return None

# plan
def plan_task(state: AgentState) -> dict:
    """
    根据当前任务，制定计划
    """
    append_runtime_log(state, "plan_task", LOG_STARTED, "正在生成任务计划")

    prompt = f"""
你是 Agent 的计划节点。

用户任务：
{state["Task"]}

请生成 3-6 步内部执行计划，并给出任务完成条件。
要求：
1. 不要回答用户问题
2. 不要写教程
3. 每一步只保留一句话
4. 如果用户要求保存、写入、移动、复制、重命名或生成文件，计划中必须包含对应的执行步骤
5. 如果用户要求把内容保存到某个路径，完成条件必须包含“目标文件已成功写入”
6. 不要把“生成内容”误判为“已保存文件”
对话历史：
{state.get("conversation_context", "")}

请只返回 JSON，不要解释，不要 Markdown，不要代码块。
JSON 格式：
{{
  "steps": [
    {{"description": "第一步", "type": "tool"}},
    {{"description": "第二步", "type": "reasoning"}}
  ],
  "completion_criteria": [
    "完成条件 1",
    "完成条件 2"
  ]
}}
"""

    result = invoke_llm_json(
        prompt,
        default={
            "steps": [
                {
                    "description": "使用可用工具完成用户任务",
                    "type": "tool",
                }
            ],
            "completion_criteria": ["用户任务已被实际完成"],
        },
    )

    if result.get("_error"):
        default_steps = [
            {
                "index": 1,
                "description": "使用可用工具完成用户任务",
                "type": "tool",
                "status": "pending",
            }
        ]
        return {
            "plan": ["模型调用失败,使用可用工具完成用户任务"],
            "plan_steps": default_steps,
            "current_step": default_steps[0],
            "completion_criteria": ["用户任务已被实际完成"],
            "status": "planned",
            "error": f"plan_task 模型调用失败：{result['_error']}",
            "step_logs": [
                {
                    "node": "plan_task",
                    "message": f"模型调用失败，使用默认计划：{result['_error']}",
                    "status": LOG_SUCCESS,
                }
            ],
        }

    raw_steps = result.get("steps", [])
    if not isinstance(raw_steps, list) or not raw_steps:
        raw_steps = [{"description": "使用可用工具完成用户任务", "type": "tool"}]

    plan_steps = [
        {
            "index": index + 1,
            "description": step.get("description", str(step)) if isinstance(step, dict) else str(step),
            "type": step.get("type", "tool") if isinstance(step, dict) else "tool",
            "status": "pending",
        }
        for index, step in enumerate(raw_steps[:6])
    ]
    completion_criteria = result.get("completion_criteria", [])
    if not isinstance(completion_criteria, list):
        completion_criteria = [str(completion_criteria)]

    return {
        "plan": [step["description"] for step in plan_steps],
        "plan_steps": plan_steps,
        "current_step": plan_steps[0] if plan_steps else {},
        "completion_criteria": completion_criteria,
        "status": "planned",
        "step_logs": [
            {"node": "plan_task", "message": "生成结构化任务计划", "status": LOG_SUCCESS}
        ],
    }


def select_tool(state: AgentState) -> dict:
    """
    根据计划，选择合适的工具
    """
    append_runtime_log(state, "select_tool", LOG_STARTED, "正在选择工具")
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

任务完成条件：
{state.get("completion_criteria", [])}

已执行工具历史：
{state.get("tool_history", [])}

当前执行轮次：
{state.get("iterations", 0)}

可用工具：
{tools_text}

对话历史：
{state.get("conversation_context", "")}


工具域优先级：
1. workspace_files、workspace、工作区文件、inbox、reports 等工作区任务，优先使用 mcp.workspace.* 工具。
2. 项目根目录下的普通文件任务，使用 list_files、read_file、write_file。
3. shell 命令、测试、脚本、安装依赖、查看命令输出，使用 run_shell。
4. URL、HTTP API、网页请求，使用 http_request。
5. 不需要真实工具、只需要基于已有历史组织最终回答时，选择 mock_tool 并设置 need_tool=false。

工具选择原则：
1. 不要选择不存在于可用工具列表中的工具。
2. 工具参数必须严格匹配该工具的参数说明。
3. 优先根据 current_step 和 completion_criteria 选择下一步工具。
4. 如果已执行工具历史已经满足当前步骤，不要重复选择相同工具。
5. 如果任务需要保存、写入、移动、复制、重命名或生成文件，不能只返回内容，必须继续选择能完成该动作的工具。
6. 如果任务要求保存 markdown 报告到 workspace_files 或 reports/*.md，选择 mcp.workspace.write_markdown_report。
7. workspace MCP 工具的路径参数都是相对 workspace_files 的路径，例如 workspace_files/inbox/c.csv 应传入 inbox/c.csv。
8. read_file/write_file 只用于项目根目录文件，不用于 workspace_files 工作区任务。
9. 如果 current_step 中有 last_error，说明上一次工具调用失败，不要原样重复上一轮 tool_input。
10. 遇到 last_error 时，必须根据错误原因修正路径、参数或更换工具；如果是 workspace_files 路径问题，优先使用相对 workspace_files 的路径。

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
                    "status": LOG_SUCCESS,
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
                    "status": LOG_SUCCESS,
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
                "status": LOG_SUCCESS,
            }
        ],
    }


def check_approval(state: AgentState) -> dict:
    """
    如果工具风险较高，暂停等待用户审批
    """
    append_runtime_log(state, "check_approval", LOG_STARTED, "正在检查工具风险")

    tool_name = state.get("selected_tool", "mock_tool")
    tool_input = state.get("tool_input", {})
    tool_info = TOOL_REGISTRY.get(tool_name, {})
    default_risk_level = tool_info.get("risk_level", "low")

    risk = analyze_tool_risk(
        tool_name=tool_name,
        tool_input=tool_input,
        default_risk_level=default_risk_level,
    )
    risk_level = risk.get("risk_level", default_risk_level)
    risk_reasons = risk.get("risk_reasons", [])
    matched_rules = risk.get("matched_rules", [])
    approval_reason = format_risk_reason(tool_name, tool_input, risk)

    if risk.get("requires_approval"):
        append_runtime_log(
            state,
            "check_approval",
            LOG_WAITING_APPROVAL,
            approval_reason,
        )
        decision = interrupt(
            {
                "tool_name": tool_name,
                "tool_input": tool_input,
                "risk_level": risk_level,
                "risk_reasons": risk_reasons,
                "matched_rules": matched_rules,
                "reason": approval_reason,
            }
        )
        if decision.get("approved"):
            return {
                "approved": True,
                "approval_required": False,
                "approval_reason": None,
                "risk_level": risk_level,
                "risk_reasons": risk_reasons,
                "matched_risk_rules": matched_rules,
                "status": "approved",
                "step_logs": [
                    {
                        "node": "check_approval",
                        "message": f"用户批准执行工具 {tool_name}，风险等级：{risk_level}",
                        "status": LOG_SUCCESS,
                    }
                ],
            }
        return {
            "approved": False,
            "approval_required": True,
            "approval_reason": "用户拒绝了高风险工具的使用",
            "risk_level": risk_level,
            "risk_reasons": risk_reasons,
            "matched_risk_rules": matched_rules,
            "status": "rejected",
            "step_logs": [
                {
                    "node": "check_approval",
                    "message": f"用户拒绝执行工具 {tool_name}，风险等级：{risk_level}",
                    "status": LOG_FAILED,
                }
            ],
        }

    return {
        "approved": True,
        "approval_required": False,
        "approval_reason": None,
        "risk_level": risk_level,
        "risk_reasons": risk_reasons,
        "matched_risk_rules": matched_rules,
        "status": "approved",
        "step_logs": [
            {
                "node": "check_approval",
                "message": f"工具 {tool_name} 风险等级为 {risk_level}，无需审批",
                "status": LOG_SKIPPED,
            }
        ],
    }


def execute_tool(state: AgentState) -> dict:
    """
    执行选中的工具，获取结果
    """
    tool_name = state.get("selected_tool", "mock_tool")
    tool_input = state.get("tool_input", {})
    append_runtime_log(state, "execute_tool", LOG_STARTED, f"正在执行工具 {tool_name}")

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
                    "status": LOG_FAILED,
                }
            ],
        }

    if not is_tool_enabled(tool_name):
        return {
            "tool_output": {
                "success": False,
                "data": None,
                "error": f"工具已停用：{tool_name}",
            },
            "status": "failed",
            "step_logs": [
                {
                    "node": "execute_tool",
                    "message": f"工具已停用，拒绝执行：{tool_name}",
                    "status": LOG_FAILED,
                }
            ],
        }

    handler = tool_info["handler"]

    try:
        tool_output = handler(tool_input)
    except Exception as exc:
        tool_output = {
            "success": False,
            "data": None,
            "error": f"工具执行异常：{str(exc)}",
        }

    if not isinstance(tool_output, dict):
        tool_output = {
            "success": False,
            "data": tool_output,
            "error": "工具返回了非结构化结果",
        }

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
                "risk_level": state.get("risk_level") or tool_info.get("risk_level"),
                "approved": state.get("approved"),
            }
        ],
        "step_logs": [
            {
                "node": "execute_tool",
                "message": f"执行工具 {tool_name}，结果：{tool_output}",
                "status": LOG_SUCCESS if tool_output.get("success") else LOG_FAILED,
            }
        ],
    }

def update_plan_step(state: AgentState) -> dict:
    """
    根据刚刚的工具执行结果，更新当前计划步骤状态
    """
    append_runtime_log(state, "update_plan_step", LOG_STARTED, "正在更新计划进度")
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
                    "status": LOG_SKIPPED,
                }
            ],
        }

    current_index = current_step.get("index")
    tool_success = bool(tool_output.get("success"))
    retry_count = int(current_step.get("retry_count", 0) or 0)
    can_retry = (
        not tool_success
        and retry_count < MAX_STEP_RETRIES
        and is_recoverable_tool_failure(tool_output)
    )

    if can_retry:
        next_retry_count = retry_count + 1
        retry_step = {
            **current_step,
            "status": "pending",
            "retry_count": next_retry_count,
            "last_error": get_tool_error_text(tool_output),
        }
        updated_steps = [
            retry_step if step.get("index") == current_index else step
            for step in plan_steps
        ]

        return {
            "plan_steps": updated_steps,
            "current_step": retry_step,
            "status": "plan_updated",
            "step_logs": [
                {
                    "node": "update_plan_step",
                    "message": (
                        f"步骤 {current_index} 执行失败但可恢复，"
                        f"准备第 {next_retry_count}/{MAX_STEP_RETRIES} 次重试："
                        f"{get_tool_error_text(tool_output)}"
                    ),
                    "status": LOG_SUCCESS,
                }
            ],
        }

    updated_steps = []
    for step in plan_steps:
        if step.get("index") == current_index:
            updated_steps.append(
                {
                    **step,
                    "status": "completed" if tool_success else "failed",
                    "last_error": None if tool_success else get_tool_error_text(tool_output),
                    "retry_count": retry_count,
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
                "status": LOG_SUCCESS,
            }
        ],
    }


def decide_next_step(state: AgentState) -> dict:
    """
    判断任务是否需要继续调用工具
    """
    append_runtime_log(state, "decide_next_step", LOG_STARTED, "正在判断是否继续执行")
    iterations = state.get("iterations", 0)
    max_iterations = state.get("max_iterations", 3)

    if iterations >= max_iterations:
        message = f"已达到最大执行轮次 {max_iterations}，结束任务"
        if task_requires_persistent_action(state) and not has_successful_persistent_action(state):
            message = f"已达到最大执行轮次 {max_iterations}，但持久化动作尚未完成，结束任务"

        return {
            "next_action": "finish",
            "status": "decided",
            "step_logs": [
                {
                    "node": "decide_next_step",
                    "message": message,
                    "status": LOG_SUCCESS,
                }
            ],
        }
    
    current_step = state.get("current_step", {})

    if not state.get("tool_output", {}).get("success", False):
        if current_step.get("retry_count", 0) > 0:
            return {
                "next_action": "continue",
                "status": "decided",
                "step_logs": [
                    {
                        "node": "decide_next_step",
                        "message": (
                            "工具执行失败但当前步骤仍可重试，"
                            f"继续修正工具参数：{current_step.get('last_error', '无错误详情')}"
                        ),
                        "status": LOG_SUCCESS,
                    }
                ],
            }

        return {
            "next_action": "finish",
            "status": "decided",
            "step_logs": [
                {
                    "node": "decide_next_step",
                    "message": f"工具执行失败，结束任务",
                    "status": LOG_SUCCESS,
                }
            ],
        }

    if task_requires_persistent_action(state) and not has_successful_persistent_action(state):
        return {
            "next_action": "continue",
            "status": "decided",
            "step_logs": [
                {
                    "node": "decide_next_step",
                    "message": "任务要求保存/写入/移动等持久化动作，但尚未看到成功工具调用，继续执行",
                    "status": LOG_SUCCESS,
                }
            ],
        }

    if not current_step:
        return{
            "next_action": "finish",
            "status": "decided",
            "step_logs": [{
                "node": "decide_next_step",
                "message": f"没有当前步骤，结束任务",
                "status": LOG_SUCCESS,
            }]
        }

    if current_step and state.get("tool_output", {}).get("success"):
        return {
            "next_action": "continue",
            "status": "decided",
            "step_logs": [
                {
                    "node": "decide_next_step",
                    "message": f"还有待执行步骤：{current_step}",
                    "status": LOG_SUCCESS,
                }
            ],
        }

    prompt = f"""
你是 Agent 的任务进度判断节点。

用户任务：
{state["Task"]}

执行计划：
{state.get("plan", [])}

任务完成条件：
{state.get("completion_criteria", [])}

已执行工具历史：
{state.get("tool_history", [])}

当前执行轮次：
{iterations}

最大执行轮次：
{max_iterations}

请判断用户任务是否已经完成。

判断规则：
1. 如果所有任务完成条件已经满足，返回 finish。
2. 如果用户要求保存、写入、移动、复制、重命名或生成文件，但历史中没有对应成功工具调用，返回 continue。
3. 如果用户任务明确包含多个步骤，并且还有步骤没有执行，返回 continue。
4. 如果工具历史已经足够回答用户任务，返回 finish。
5. 如果继续执行也不会获得更多有用信息，返回 finish。
6. 如果不确定，优先根据 completion_criteria 判断，不要仅因为已经生成文本内容就 finish。

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
                    "status": LOG_FAILED,
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
                "status": LOG_SUCCESS,
            }
        ],
    }


def finalize_task(state: AgentState) -> dict:
    """
    根据工具结果，生成最终响应
    """
    append_runtime_log(state, "finalize_task", LOG_STARTED, "正在生成最终回复")
    tool_output = state.get("tool_output", {})

    if state.get("status") == "pending_approval":
        return {
            "final_response": state.get("approval_reason", "该操作需要用户审批"),
            "status": "pending_approval",
            "step_logs": [
                {
                    "node": "finalize_task",
                    "message": "任务正在等待审批，暂不生成最终回复",
                    "status": LOG_WAITING_APPROVAL,
                }
            ],
        }

    if state.get("status") == "rejected":
        return {
            "final_response": state.get("approval_reason", "用户拒绝了工具使用请求，任务已停止。"),
            "status": "rejected",
            "step_logs": [
                {
                    "node": "finalize_task",
                    "message": "任务已被用户拒绝，保持 rejected 状态",
                    "status": LOG_FAILED,
                }
            ],
        }

    if state.get("status") == "cancelled":
        return {
            "final_response": state.get("final_response", "任务已取消。"),
            "status": "cancelled",
            "step_logs": [
                {
                    "node": "finalize_task",
                    "message": "任务已取消，保持 cancelled 状态",
                    "status": LOG_SKIPPED,
                }
            ],
        }

    completion_blocker = get_completion_blocker(state)
    final_status = "failed" if completion_blocker else "completed"

    prompt = f"""
根据工具执行结果，生成对用户的最终响应。

用户任务：
{state["Task"]}

用户计划：
{state.get("plan", [])}

结构化计划完成情况：
{state.get("plan_steps", [])}

任务完成条件：
{state.get("completion_criteria", [])}

工具名称：
{state.get("selected_tool", "")}

工具结果：
{tool_output}

最近一次工具结果：
{tool_output}

完整工具执行历史：
{state.get("tool_history", [])}
对话历史：
{state.get("conversation_context", "")}

完成阻塞原因：
{completion_blocker or "无"}

要求：
1. 像桌面助手一样回复用户，不要暴露 plan_task、select_tool、execute_tool、update_plan_step 等内部节点名。
2. 如果完成阻塞原因为“无”，第一句话直接说“已完成。”
3. 如果完成阻塞原因不为“无”，第一句话直接说“未完成。”
4. 成功时重点说明最终结果；如果生成或保存了文件，明确给出文件路径。
5. 失败时说明失败原因和下一步建议。
6. 不要编造工具结果中没有的信息。
7. 不要把“已生成内容”说成“已保存文件”。
8. 详细执行过程已经在前端“查看执行状态/查看详细日志”里展示，最终回复只保留结果。

建议格式：
成功：
已完成。

结果：
- ...

文件：
- ...

失败：
未完成。

原因：
- ...

建议：
- ...
"""

    final_response = ""
    task_id = state.get("task_id")
    should_stream = bool(state.get("stream_final_response") and task_id)

    def stop_if_cancelled_during_stream() -> dict | None:
        if not task_id:
            return None

        task = task_repo.get_task(task_id)
        if not task or not getattr(task, "cancel_requested", False):
            return None

        cancelled_response = final_response or "任务已取消。"
        task_repo.update_task(
            task_id,
            {
                "status": "cancelled",
                "final_response": cancelled_response,
                "approval_required": False,
                "approval_reason": None,
            },
        )
        return {
            "final_response": cancelled_response,
            "status": "cancelled",
            "step_logs": [
                {
                    "node": "finalize_task",
                    "message": "生成回复时收到取消请求",
                    "status": "cancelled",
                }
            ],
        }

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
                cancelled_result = stop_if_cancelled_during_stream()
                if cancelled_result:
                    return cancelled_result

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
                    "status": LOG_FAILED,
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
                "status": LOG_SUCCESS if final_status == "completed" else LOG_FAILED,
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
