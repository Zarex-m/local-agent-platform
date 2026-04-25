from typing import Any,Optional
from typing_extensions import TypedDict
from typing_extensions import Annotated
import operator

class AgentState(TypedDict,total=False):
    Task:str
    status:str #状态：待执行、执行中、已完成、失败
    plan:list[str] #计划
    selected_tool:str #选中的工具
    tool_input:dict #工具参数
    tool_output:dict #工具结果
    final_response:str 
    error:str|None
    
    #审批相关
    approved: bool
    approval_required: bool
    approval_reason: str | None
    
    #日志
    step_logs: Annotated[list[dict], operator.add]