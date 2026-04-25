# Local Agent Platform

一个本地优先的 Agent 执行平台原型，基于 LangGraph、LangChain、FastAPI、MCP 和 SQLite 设计。当前阶段重点实现 Agent 内核：任务规划、工具选择、工具执行、高风险审批中断、恢复执行和步骤日志。

## 项目定位

这个项目的目标是构建一个可本地部署的个人 Agent 工作台。用户提交自然语言任务后，系统通过 LangGraph 编排执行流程，由大模型完成计划生成和工具选择，再通过统一工具层调用本地工具或未来的 MCP 工具。

长期目标包括：

- 本地任务执行与文件操作
- 高风险操作审批
- 执行过程日志和回放
- 多模型适配
- MCP 工具扩展
- FastAPI 接口和前端工作台

## 当前能力

当前已经完成的 Agent MVP 流程：

```text
用户任务
  -> plan_task 生成短计划
  -> select_tool 选择工具和参数
  -> check_approval 判断是否需要审批
  -> execute_tool 执行工具
  -> finalize_task 生成最终回复
```

已支持：

- LangGraph 线性流程和条件路由
- Kimi / DeepSeek 风格的 OpenAI 兼容模型配置
- 工具注册表和工具元信息
- 本地工具：`mock_tool`、`list_files`、`read_file`、`write_file`
- 高风险工具审批中断
- LangGraph 原生 `interrupt` / `Command(resume=...)` 恢复执行
- `step_logs` 执行日志累积
- SQLAlchemy + SQLite 任务和日志存储层

## 技术栈

- LangGraph：Agent 状态流转和节点编排
- LangChain：模型调用抽象
- FastAPI：后续 API 服务层
- MCP：后续标准化工具扩展
- SQLite：本地任务和日志存储
- SQLAlchemy：ORM 数据访问层

## 目录结构

```text
app/
  agent/
    state.py          # AgentState 定义
    node.py           # LangGraph 节点和路由函数
    graph.py          # 图结构组装
    test_graph.py     # 本地测试入口
  tools/
    builtin.py        # 本地工具实现
    registry.py       # 工具注册表和工具元信息
  storage/
    database.py       # SQLAlchemy ORM 模型和数据库初始化
    task_repository.py # 任务和日志存储函数
data/
  agent.db            # 本地 SQLite 数据库，默认不提交
```

## 快速开始

创建并激活虚拟环境：

```bash
python -m venv .venv
source .venv/bin/activate
```

安装依赖：

```bash
pip install -r requirements.txt
```

复制环境变量模板：

```bash
cp .env.example .env
```

填写 `.env` 中的大模型 API Key：

```env
LLM_PROVIDER=kimi
KIMI_API_KEY=your_kimi_api_key_here
KIMI_BASE_URL=https://api.moonshot.cn/v1
KIMI_MODEL=kimi-k2.5
```

初始化数据库：

```bash
python -c "from app.storage.database import init_db; init_db()"
```

运行本地 Agent 测试：

```bash
python -m app.agent.test_graph
```

## 当前测试场景

`app/agent/test_graph.py` 当前包含两个场景：

- 低风险任务：读取 `requirements.txt`
- 高风险任务：写入 `demo.txt`，触发审批中断后通过 `Command(resume={"approved": True})` 恢复执行

## 后续计划

近期计划：

- 将 storage 接入 Agent service
- 实现 `run_task` 和 `approve_task`
- 将任务状态、审批状态、步骤日志写入 SQLite
- 增加 FastAPI 任务提交、查询、审批接口

中期计划：

- 接入 MCP Client
- 支持 MCP 工具发现和调用
- 增加工具权限和风险等级配置
- 增加执行回放接口

长期计划：

- 构建本地 Web UI
- 支持模型配置管理
- 支持桌面 App 打包
- 支持 PostgreSQL 扩展

## 简历描述参考

基于 LangGraph、LangChain、FastAPI 和 MCP 设计本地 Agent 执行平台，支持任务规划、工具调用、高风险操作审批中断、恢复执行和执行日志记录。通过 SQLAlchemy 抽象本地 SQLite 存储层，预留 PostgreSQL 和 MCP 工具生态扩展能力。
