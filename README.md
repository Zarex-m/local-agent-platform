# Tool Pet Agent / Local Agent Platform

一个本地优先的工具增强型 Agent 工作台原型。项目基于 LangGraph、FastAPI、React、SQLite 和 MCP 构建，目标是探索一个“桌宠形态的本地 Agent”：它不是单纯聊天助手，而是能理解任务、选择工具、请求审批、执行本地工作流，并把执行过程清楚展示给用户。

当前阶段重点是 Agent 应用开发底座：

- 多步 Agent 状态流转
- 本地工具与 MCP 工具统一注册
- 工具风险等级、启用/禁用和持久化配置
- 高风险操作审批
- 危险 shell 命令识别
- 任务取消 / 停止生成
- 工具调用日志和执行过程回放
- React 工作台展示任务状态、审批、工具调用和日志

后续会在这个底座上发展“陪伴式工具 Agent / Tool Pet Agent”交互，让桌宠负责表达状态、提醒用户、解释风险，而 Agent 负责调用工具完成日常工作流。

## 项目定位

这个项目不是代码生成助手，也不是单纯的桌面宠物，而是一个本地工具增强型 Agent 工作台：

```text
用户任务
  -> Agent 规划
  -> 选择工具
  -> 检查风险
  -> 必要时请求审批
  -> 执行工具
  -> 记录过程
  -> 返回结果
```

简历展示重点：

- Agent 编排：LangGraph 状态机、条件路由、interrupt/resume
- 工具系统：本地工具、MCP 工具、统一注册表、参数 schema、风险等级
- 安全机制：高风险审批、危险命令识别、任务取消、工具启用/禁用
- 可观测性：任务状态、执行日志、工具调用历史、SSE 流式更新
- 产品化：React 工作台、工具管理页、前端审批体验

## 当前能力

### Agent 流程

当前 LangGraph 流程：

```text
START
  -> plan_task
  -> select_tool
  -> check_approval
  -> execute_tool
  -> update_plan_step
  -> decide_next_step
  -> finalize_task
  -> END
```

支持：

- 任务规划
- 多轮工具调用
- 高风险工具审批中断
- 审批后恢复执行
- 执行日志记录
- 工具调用历史记录
- 最终回复流式更新
- 任务取消

### 工具系统

当前内置本地工具：

```text
mock_tool
list_files
read_file
write_file
run_shell
http_request
```

同时支持从 MCP Server 动态加载工具，例如当前的 time MCP：

```text
mcp.time.get_current_time
mcp.time.convert_time
```

每个工具包含：

```text
name
description
input_schema
risk_level
enabled
handler
```

工具启用/禁用状态保存在 SQLite `tool_settings` 表中，重启后端后仍然生效。

### 安全机制

已支持：

- `write_file`、`run_shell` 等高风险工具审批
- `run_shell` 动态风险识别
- 识别 `rm -rf`、`sudo`、`chmod -R`、`chown -R`、`curl | sh`、`dd of=`、`mkfs` 等危险命令
- 工具启用/禁用
- 停用工具不会出现在 Agent 可选工具列表中
- `execute_tool` 执行前兜底检查停用状态
- 任务取消后后台执行停止
- SSE 对 `completed`、`failed`、`rejected`、`cancelled` 终态收口

### 前端工作台

React 前端支持：

- 会话列表
- 任务提交
- 实时任务状态
- 最终回复流式展示
- 审批高风险工具
- 停止生成 / 取消任务
- 执行时间线
- 工具调用历史
- 工具输入/输出查看
- 工具管理页
- 工具启用/禁用 toggle

## 技术栈

- LangGraph：Agent 状态流转和中断恢复
- LangChain：模型调用抽象
- FastAPI：后端 API
- SQLite：本地任务、日志、工具设置持久化
- SQLAlchemy：ORM
- MCP：外部工具扩展协议
- React + Vite：前端工作台
- Server-Sent Events：任务状态和最终回复更新

## 架构

```text
React Frontend
  ├─ Chat Workspace
  ├─ Approval UI
  ├─ Tool Calls / Logs
  └─ Tool Management

FastAPI Backend
  ├─ /tasks
  ├─ /tools
  └─ /conversations

LangGraph Agent
  ├─ plan_task
  ├─ select_tool
  ├─ check_approval
  ├─ execute_tool
  ├─ decide_next_step
  └─ finalize_task

Tool Layer
  ├─ Local Tools
  ├─ MCP Tools
  ├─ Safety Policy
  └─ Tool Registry

SQLite
  ├─ tasks
  ├─ step_logs
  ├─ tool_calls
  ├─ conversations
  ├─ messages
  └─ tool_settings
```

## 目录结构

```text
app/
  main.py
  api/
    routes.py                 # 任务接口
    conversation_routes.py    # 会话接口
    tool_routes.py            # 工具管理接口
  agent/
    graph.py                  # LangGraph 图结构
    node.py                   # Agent 节点逻辑
    state.py                  # AgentState
    llm.py                    # 模型调用
  tools/
    builtin.py                # 本地工具实现
    registry.py               # 工具注册表
    safety.py                 # 工具风险分析
  mcp/
    adapter.py                # MCP 工具适配
    client.py                 # MCP Client
    config.py                 # MCP Server 配置
  storage/
    database.py               # ORM 模型和数据库初始化
    task_repository.py        # 任务、日志、工具调用存储
    conversation_repository.py
    tool_settings_repository.py
  services/
    agent_service.py          # 后台任务执行
frontend/
  src/
    App.tsx
    api.ts
    types.ts
    styles.css
data/
  agent.db                    # 本地 SQLite 数据库，默认不提交
```

## 快速开始

创建虚拟环境：

```bash
python -m venv .venv
source .venv/bin/activate
```

安装依赖：

```bash
pip install -r requirements.txt
```

配置环境变量：

```bash
cp .env.example .env
```

填写模型配置，例如：

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

启动后端：

```bash
uvicorn app.main:app --reload
```

启动前端：

```bash
cd frontend
npm install
npm run dev
```

打开：

```text
http://127.0.0.1:5173/
```

## API

### 任务

```text
POST /tasks/
GET  /tasks/?limit=20
GET  /tasks/{task_id}
GET  /tasks/{task_id}/logs
GET  /tasks/{task_id}/tool-calls
GET  /tasks/{task_id}/events
POST /tasks/{task_id}/approve
POST /tasks/{task_id}/cancel
```

### 工具

```text
GET   /tools/
PATCH /tools/{tool_name}
```

示例：

```bash
curl http://127.0.0.1:8000/tools/
```

停用 `run_shell`：

```bash
curl -X PATCH http://127.0.0.1:8000/tools/run_shell \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'
```

重新启用：

```bash
curl -X PATCH http://127.0.0.1:8000/tools/run_shell \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'
```

### 会话

```text
GET    /conversations/
GET    /conversations/{conversation_id}
GET    /conversations/{conversation_id}/messages
PATCH  /conversations/{conversation_id}
DELETE /conversations/{conversation_id}
```

## 自测清单

### 1. 健康检查

```bash
curl http://127.0.0.1:8000/health
```

预期：

```json
{"status":"ok"}
```

### 2. 工具列表

```bash
curl http://127.0.0.1:8000/tools/
```

预期看到本地工具和 MCP 工具：

```text
mock_tool
list_files
read_file
write_file
run_shell
http_request
mcp.time.get_current_time
mcp.time.convert_time
```

### 3. 工具启用/禁用持久化

停用：

```bash
curl -X PATCH http://127.0.0.1:8000/tools/run_shell \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'
```

检查数据库：

```bash
sqlite3 data/agent.db "select tool_name, enabled from tool_settings;"
```

预期：

```text
run_shell|0
```

重启后端后再次请求：

```bash
curl http://127.0.0.1:8000/tools/
```

预期 `run_shell` 仍然是：

```json
"enabled": false
```

恢复：

```bash
curl -X PATCH http://127.0.0.1:8000/tools/run_shell \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'
```

### 4. 普通任务

```bash
curl -X POST http://127.0.0.1:8000/tasks/ \
  -H "Content-Type: application/json" \
  -d '{"task": "查询上海当前时间"}'
```

预期：Agent 选择 MCP time 工具或相关工具完成任务。

### 5. 高风险任务审批

```bash
curl -X POST http://127.0.0.1:8000/tasks/ \
  -H "Content-Type: application/json" \
  -d '{"task": "帮我写入 demo.txt，内容是 hello"}'
```

预期：任务进入 `pending_approval`。

审批：

```bash
curl -X POST http://127.0.0.1:8000/tasks/{task_id}/approve \
  -H "Content-Type: application/json" \
  -d '{"approved": true}'
```

### 6. 危险 shell 命令识别

```bash
curl -X POST http://127.0.0.1:8000/tasks/ \
  -H "Content-Type: application/json" \
  -d '{"task": "执行 shell 命令 rm -rf data"}'
```

预期：审批原因中出现 `rm -rf` 风险说明，任务不会直接执行。

### 7. 取消任务

```bash
curl -X POST http://127.0.0.1:8000/tasks/{task_id}/cancel
```

预期：任务状态变为 `cancelled`，SSE 发送 `done`。

## 当前演示场景

建议用于录屏或面试演示：

1. 查询当前时间，展示 MCP 工具调用。
2. 写入文件，展示高风险审批和恢复执行。
3. 停用 `run_shell`，展示工具管理和持久化。
4. 执行危险 shell 命令，展示风险识别和审批理由。
5. 提交长任务后取消，展示任务控制能力。

## 发展路线

### 第一阶段：Agent 平台底座

状态：进行中

- 工具启用/禁用持久化
- README 和自测清单
- 当前功能稳定性验证

### 第二阶段：日常工作流工具

计划能力：

- 文件扫描
- 文件整理
- Markdown 报告生成
- CSV 读写
- PDF 文本读取
- 简单提醒任务

目标 demo：

```text
帮我整理 downloads 目录下最近 7 天的文件，按类型归档，并生成一份 markdown 报告。
```

### 第三阶段：桌宠交互层

计划能力：

- 桌宠状态：空闲、思考、执行工具、等待审批、完成、失败、取消
- 用桌宠表达 Agent 当前状态
- 审批时用更自然的风险说明提醒用户
- 保留工作台中的详细日志和工具调用

### 第四阶段：桌面化

计划能力：

- Electron 或 Tauri 打包
- 桌面窗口启动
- 可选系统托盘
- 可选右下角桌宠窗口

## 简历描述参考

```text
Tool Pet Agent：基于 LangGraph 的本地工具增强型 Agent 工作台，支持任务规划、工具选择、审批中断、恢复执行、任务取消和结果总结。
设计统一工具注册中心，接入本地工具与 MCP 工具，支持工具风险等级、启用禁用、SQLite 持久化配置和调用审计。
实现 Human-in-the-loop 安全机制，对 write_file、run_shell 等高风险工具进行审批，并识别 rm -rf、sudo、chmod -R 等危险命令。
构建 React 工作台，实时展示任务状态、工具调用、执行日志、审批流程和工具管理。
```

