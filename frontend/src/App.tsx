import { FormEvent, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  Bot,
  Check,
  Clock3,
  Database,
  FileText,
  Globe2,
  Loader2,
  MessageSquarePlus,
  Pencil,
  Play,
  Plus,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  User,
  Wrench,
  X,
} from "lucide-react";
import {
  approveTask,
  createTaskEventSource,
  getTask,
  getTaskLogs,
  getTaskToolCalls,
  listTasks,
  submitTask,
} from "./api";
import type { StepLog, Task, ToolCall } from "./types";

const statusLabels: Record<string, string> = {
  completed: "已完成",
  pending_approval: "待审批",
  failed: "失败",
  rejected: "已拒绝",
  running: "运行中",
  tool_selected: "已选工具",
  tool_executed: "已执行",
  approved: "已批准",
  created: "已创建",
  planned: "已规划",
};

function formatTime(value?: string) {
  if (!value) return "-";
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(value));
}

function statusTone(status: string) {
  if (status === "completed") return "success";
  if (status === "pending_approval") return "warning";
  if (status === "failed" || status === "rejected") return "danger";
  return "neutral";
}

function toolSource(tool?: string | null) {
  if (!tool) return "未选择工具";
  return tool.startsWith("mcp.") ? "MCP 工具" : "本地工具";
}

function compactMessage(message: string) {
  if (message.length <= 900) return message;
  return `${message.slice(0, 900)}\n...`;
}

function normalizeJsonValue(value: unknown) {
  if (typeof value !== "string") return value;

  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}

function formatJsonValue(value: unknown) {
  const normalized = normalizeJsonValue(value);
  if (normalized === null || normalized === undefined) return "-";
  if (typeof normalized === "string") return normalized;
  return JSON.stringify(normalized, null, 2);
}

function riskTone(risk?: string | null) {
  if (risk === "high") return "high";
  if (risk === "medium") return "medium";
  if (risk === "low") return "low";
  return "unknown";
}

function isTerminalStatus(status?: string | null) {
  return status === "completed" || status === "failed" || status === "rejected";
}

export default function App() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [logs, setLogs] = useState<StepLog[]>([]);
  const [toolCalls, setToolCalls] = useState<ToolCall[]>([]);
  const [taskText, setTaskText] = useState("查询上海当前时间");
  const taskInputRef = useRef<HTMLTextAreaElement | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function closeTaskStream() {
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
  }

  async function refreshTaskSnapshot(taskId: number, options?: { silent?: boolean }) {
    if (!options?.silent) {
      setIsLoading(true);
    }
    setError(null);

    try {
      const [detail, nextLogs, nextToolCalls] = await Promise.all([
        getTask(taskId),
        getTaskLogs(taskId),
        getTaskToolCalls(taskId),
      ]);
      setSelectedTask(detail);
      setLogs(nextLogs);
      setToolCalls(nextToolCalls);

      if (isTerminalStatus(detail.status)) {
        closeTaskStream();
      }

      return detail;
    } catch (err) {
      if (!options?.silent) {
        setError(err instanceof Error ? err.message : "请求失败");
      }
      return null;
    } finally {
      if (!options?.silent) {
        setIsLoading(false);
      }
    }
  }

  function startTaskStream(taskId: number) {
    closeTaskStream();

    const source = createTaskEventSource(taskId);
    eventSourceRef.current = source;

    const refreshFromStream = () => {
      if (eventSourceRef.current !== source) return;

      void refreshTaskSnapshot(taskId, { silent: true });
      void listTasks().then(setTasks).catch(() => undefined);
    };

    source.addEventListener("task", refreshFromStream);
    source.addEventListener("log", refreshFromStream);
    source.addEventListener("tool_call", refreshFromStream);

    source.addEventListener("done", () => {
      refreshFromStream();
      if (eventSourceRef.current === source) {
        closeTaskStream();
      }
    });

    source.onerror = () => {
      if (eventSourceRef.current === source) {
        closeTaskStream();
      }
    };
  }

  async function refreshTasks(selectTaskId?: number) {
    setIsLoading(true);
    setError(null);

    try {
      const nextTasks = await listTasks();
      setTasks(nextTasks);

      const nextSelected =
        nextTasks.find((task) => task.id === selectTaskId) ??
        (selectedTask ? nextTasks.find((task) => task.id === selectedTask.id) : undefined) ??
        nextTasks[0] ??
        null;

      if (nextSelected) {
        const [detail, nextLogs, nextToolCalls] = await Promise.all([
          getTask(nextSelected.id),
          getTaskLogs(nextSelected.id),
          getTaskToolCalls(nextSelected.id),
        ]);
        setSelectedTask(detail);
        setLogs(nextLogs);
        setToolCalls(nextToolCalls);
      } else {
        setSelectedTask(null);
        setLogs([]);
        setToolCalls([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "请求失败");
    } finally {
      setIsLoading(false);
    }
  }

  async function selectTask(taskId: number) {
    const detail = await refreshTaskSnapshot(taskId);
    if (!detail) return;

    if (isTerminalStatus(detail.status)) {
      closeTaskStream();
    } else {
      startTaskStream(taskId);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = taskText.trim();
    if (!text) return;

    setIsSubmitting(true);
    setError(null);

    try {
      const payload = await submitTask(text);
      setTaskText("");
      await refreshTasks(payload.task_id);
      startTaskStream(payload.task_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "任务提交失败");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleApproval(approved: boolean) {
    if (!selectedTask) return;

    setIsApproving(true);
    setError(null);

    try {
      const payload = await approveTask(selectedTask.id, approved);
      await refreshTasks(payload.task_id);
      startTaskStream(payload.task_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "审批失败");
    } finally {
      setIsApproving(false);
    }
  }

  useEffect(() => {
    void refreshTasks();

    return () => {
      closeTaskStream();
    };
  }, []);

  useLayoutEffect(() => {
    const input = taskInputRef.current;
    if (!input) return;

    const maxHeight = 132;
    const minHeight = 38;
    input.style.height = "auto";
    const nextHeight = Math.min(Math.max(input.scrollHeight, minHeight), maxHeight);
    input.style.height = `${nextHeight}px`;
    input.style.overflowY = input.scrollHeight > maxHeight ? "auto" : "hidden";
  }, [taskText]);

  const selectedStatus = selectedTask?.status ?? "created";
  const needsApproval = selectedTask?.status === "pending_approval";
  const sourceLabel = toolSource(selectedTask?.selected_tool);

  const orderedLogs = useMemo(
    () => [...logs].sort((a, b) => a.id - b.id),
    [logs],
  );

  const orderedToolCalls = useMemo(
    () => [...toolCalls].sort((a, b) => a.id - b.id),
    [toolCalls],
  );

  function renderComposer(className = "chatComposer") {
    return (
      <form className={className} onSubmit={handleSubmit}>
        <textarea
          ref={taskInputRef}
          value={taskText}
          onChange={(event) => setTaskText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              event.currentTarget.form?.requestSubmit();
            }
          }}
          placeholder="有问题，尽管问"
          rows={1}
        />
        <div className="composerBar">
          <div className="composerTools">
            <button className="toolButton" type="button" aria-label="添加">
              <Plus size={18} />
            </button>
            <button
              className="modeButton"
              type="button"
              onClick={() => setTaskText("查询上海当前时间")}
            >
              <Sparkles size={17} />
              进阶
            </button>
          </div>
          <button className="sendButton" disabled={isSubmitting || !taskText.trim()}>
            {isSubmitting ? <Loader2 className="spin" size={18} /> : <Play size={18} />}
          </button>
        </div>
      </form>
    );
  }

  return (
    <main className="chatShell">
      <aside className="chatSidebar">
        <div className="brand">
          <div className="brandMark">
            <Sparkles size={20} />
          </div>
          <div>
            <p className="eyebrow">Local Agent</p>
            <h1>对话</h1>
          </div>
        </div>

        <button
          className="newChatButton"
          onClick={() => {
            closeTaskStream();
            setSelectedTask(null);
            setLogs([]);
            setToolCalls([]);
            setTaskText("");
          }}
          type="button"
        >
          <MessageSquarePlus size={16} />
          新对话
        </button>

        <button className="refreshButton" onClick={() => refreshTasks()} disabled={isLoading}>
          {isLoading ? <Loader2 className="spin" size={16} /> : <RefreshCw size={16} />}
          刷新任务
        </button>

        <div className="conversationList">
          {tasks.map((task) => (
            <button
              className={`conversationItem ${selectedTask?.id === task.id ? "active" : ""}`}
              key={task.id}
              onClick={() => selectTask(task.id)}
              type="button"
            >
              <span className={`dot ${statusTone(task.status)}`} />
              <span className="conversationCopy">
                <strong>{task.task}</strong>
                <small>
                  #{task.id} · {statusLabels[task.status] ?? task.status}
                </small>
              </span>
            </button>
          ))}
        </div>
      </aside>

      <section className={`chatWorkspace ${selectedTask ? "" : "startMode"}`}>
        {selectedTask && (
          <header className="chatHeader">
            <div>
              <p className="eyebrow">Workspace</p>
              <h2>{selectedTask.task}</h2>
            </div>
            <div className="headerBadges">
              <span className={`statusPill ${statusTone(selectedStatus)}`}>
                {statusLabels[selectedStatus] ?? selectedStatus}
              </span>
              <span className="sourcePill">
                <Wrench size={14} />
                {sourceLabel}
              </span>
            </div>
          </header>
        )}

        {error && <div className="errorBanner">{error}</div>}

        <div className="chatViewport">
          {!selectedTask && (
            <div className="startScreen">
              <h2>我们先从哪里开始呢？</h2>
              {renderComposer("chatComposer startComposer")}
              <div className="promptChips">
                <button type="button" onClick={() => setTaskText("读取 requirements.txt")}>
                  <FileText size={16} />
                  读取文件
                </button>
                <button type="button" onClick={() => setTaskText("帮我写一份项目总结")}>
                  <Pencil size={16} />
                  撰写或编辑
                </button>
                <button type="button" onClick={() => setTaskText("查询上海当前时间")}>
                  <Globe2 size={16} />
                  调用 MCP
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setTaskText("先列出当前目录，再读取 requirements.txt，然后总结依赖")
                  }
                >
                  <Wrench size={16} />
                  多工具测试
                </button>
              </div>
            </div>
          )}

          {selectedTask && (
            <div className="messageStack">
              <article className="messageRow user">
                <div className="avatar userAvatar">
                  <User size={18} />
                </div>
                <div className="messageBubble userBubble">
                  <p>{selectedTask.task}</p>
                  <span>{formatTime(selectedTask.created_at)}</span>
                </div>
              </article>

              <article className="messageRow assistant">
                <div className="avatar botAvatar">
                  <Bot size={18} />
                </div>
                <div className="messageBubble assistantBubble">
                  <div className="toolSummary">
                    <span>
                      <Wrench size={15} />
                      {selectedTask.selected_tool ?? "等待选择工具"}
                    </span>
                    <span>
                      <Database size={15} />
                      {sourceLabel}
                    </span>
                    <span>
                      <Clock3 size={15} />
                      {formatTime(selectedTask.updated_at)}
                    </span>
                  </div>
                </div>
              </article>

              <article className="messageRow assistant">
                <div className="avatar toolCallAvatar">
                  <Wrench size={17} />
                </div>
                <div className="messageBubble toolCallsBubble">
                  <div className="toolCallsHeader">
                    <div>
                      <strong>工具调用</strong>
                      <span>记录 Agent 每次实际执行的工具</span>
                    </div>
                    <b>{orderedToolCalls.length} 次</b>
                  </div>

                  {orderedToolCalls.length === 0 ? (
                    <p className="emptyToolCalls">暂无工具调用记录。</p>
                  ) : (
                    <div className="toolCallList">
                      {orderedToolCalls.map((toolCall, index) => (
                        <section className="toolCallCard" key={toolCall.id}>
                          <div className="toolCallTop">
                            <div className="toolCallTitle">
                              <strong>{toolCall.tool_name}</strong>
                              <span>
                                Step {toolCall.step_index ?? "-"} ·{" "}
                                {toolCall.step_description ?? "未记录步骤"}
                              </span>
                            </div>
                            <div className="toolCallBadges">
                              <span className={`riskBadge ${riskTone(toolCall.risk_level)}`}>
                                {toolCall.risk_level ?? "unknown"}
                              </span>
                              <span
                                className={`callResult ${
                                  toolCall.success === true
                                    ? "ok"
                                    : toolCall.success === false
                                      ? "bad"
                                      : "unknown"
                                }`}
                              >
                                {toolCall.success === true
                                  ? "成功"
                                  : toolCall.success === false
                                    ? "失败"
                                    : "未知"}
                              </span>
                            </div>
                          </div>

                          <div className="toolPayloadGrid">
                            <details open={index === orderedToolCalls.length - 1}>
                              <summary>输入</summary>
                              <pre>{compactMessage(formatJsonValue(toolCall.tool_input))}</pre>
                            </details>
                            <details>
                              <summary>输出</summary>
                              <pre>{compactMessage(formatJsonValue(toolCall.tool_output))}</pre>
                            </details>
                          </div>
                        </section>
                      ))}
                    </div>
                  )}
                </div>
              </article>

              {orderedLogs.map((log) => (
                <article className="messageRow trace" key={log.id}>
                  <div className="avatar traceAvatar">
                    <Clock3 size={17} />
                  </div>
                  <div className="messageBubble traceBubble">
                    <div className="traceHead">
                      <strong>{log.node}</strong>
                      <span className={`miniStatus ${statusTone(log.status)}`}>
                        {statusLabels[log.status] ?? log.status}
                      </span>
                    </div>
                    <pre>{compactMessage(log.message)}</pre>
                    <small>{formatTime(log.created_at)}</small>
                  </div>
                </article>
              ))}

              {needsApproval && (
                <article className="messageRow assistant">
                  <div className="avatar approvalAvatar">
                    <ShieldAlert size={18} />
                  </div>
                  <div className="messageBubble approvalBubble">
                    <strong>需要审批</strong>
                    <p>{selectedTask.approval_reason ?? "该操作需要用户审批。"}</p>
                    <div className="approvalActions">
                      <button
                        className="secondaryButton"
                        onClick={() => handleApproval(false)}
                        disabled={isApproving}
                        type="button"
                      >
                        <X size={16} />
                        拒绝
                      </button>
                      <button
                        className="approveButton"
                        onClick={() => handleApproval(true)}
                        disabled={isApproving}
                        type="button"
                      >
                        {isApproving ? (
                          <Loader2 className="spin" size={16} />
                        ) : (
                          <Check size={16} />
                        )}
                        批准
                      </button>
                    </div>
                  </div>
                </article>
              )}

              {!needsApproval && (
                <article className="messageRow assistant">
                  <div className="avatar botAvatar">
                    <Bot size={18} />
                  </div>
                  <div className="messageBubble assistantBubble final">
                    <pre>{selectedTask.final_response ?? "任务还没有生成最终回复。"}</pre>
                  </div>
                </article>
              )}
            </div>
          )}
        </div>

        {selectedTask && renderComposer("chatComposer dockComposer")}
      </section>
    </main>
  );
}
