import { FormEvent, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  Bot,
  Check,
  Clock3,
  Trash2,
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
  deleteConversation,
  getConversation,
  getConversationMessages,
  getTask,
  getTaskLogs,
  getTaskToolCalls,
  listConversations,
  submitTask,
  updateConversation,
} from "./api";
import type { Conversation, ConversationMessage, StepLog, Task, ToolCall } from "./types";

const statusLabels: Record<string, string> = {
  completed: "已完成",
  pending_approval: "待审批",
  failed: "失败",
  rejected: "已拒绝",
  running: "运行中",
  finalizing: "生成回复中",
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
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedConversation, setSelectedConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [logs, setLogs] = useState<StepLog[]>([]);
  const [toolCalls, setToolCalls] = useState<ToolCall[]>([]);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [taskText, setTaskText] = useState("查询上海当前时间");
  const taskInputRef = useRef<HTMLTextAreaElement | null>(null);
  const chatViewportRef = useRef<HTMLDivElement | null>(null);
  const messageEndRef = useRef<HTMLDivElement | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [showTrace, setShowTrace] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function closeTaskStream() {
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
  }

  function resetConversationView() {
    closeTaskStream();
    setSelectedConversation(null);
    setSelectedTask(null);
    setMessages([]);
    setLogs([]);
    setToolCalls([]);
    setConversationId(null);
    setShowTrace(false);
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
      setConversationId(detail.conversation_id ?? null);
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

  async function refreshConversationList() {
    const nextConversations = await listConversations();
    setConversations(nextConversations);
    return nextConversations;
  }

  async function refreshConversationMessages(targetConversationId: number) {
    const nextMessages = await getConversationMessages(targetConversationId);
    setMessages(nextMessages);
    return nextMessages;
  }

  function startTaskStream(taskId: number) {
    closeTaskStream();

    const source = createTaskEventSource(taskId);
    eventSourceRef.current = source;

    const refreshFromStream = () => {
      if (eventSourceRef.current !== source) return;

      void refreshTaskSnapshot(taskId, { silent: true });
      void refreshConversationList().catch(() => undefined);
    };

    source.addEventListener("task", refreshFromStream);
    source.addEventListener("log", refreshFromStream);
    source.addEventListener("tool_call", refreshFromStream);

    source.addEventListener("final_response", (event) => {
      if (eventSourceRef.current !== source) return;

      try {
        const data = JSON.parse((event as MessageEvent).data) as {
          final_response?: string;
          status?: string;
        };

        setSelectedTask((current) => {
          if (!current || current.id !== taskId) return current;

          return {
            ...current,
            status: data.status ?? current.status,
            final_response: data.final_response ?? current.final_response,
          };
        });
      } catch {
        refreshFromStream();
      }
    });

    source.addEventListener("done", () => {
      refreshFromStream();
      void refreshTaskSnapshot(taskId, { silent: true }).then((detail) => {
        if (detail?.conversation_id) {
          void refreshConversationMessages(detail.conversation_id).catch(() => undefined);
        }
      });
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

  async function selectConversation(targetConversationId: number, options?: { silent?: boolean }) {
    if (!options?.silent) {
      setIsLoading(true);
    }
    setError(null);

    try {
      const [conversation, nextMessages] = await Promise.all([
        getConversation(targetConversationId),
        getConversationMessages(targetConversationId),
      ]);

      setSelectedConversation(conversation);
      setConversationId(conversation.id);
      setMessages(nextMessages);
      setShowTrace(false);

      if (conversation.latest_task_id) {
        const detail = await refreshTaskSnapshot(conversation.latest_task_id, { silent: true });

        if (detail && !isTerminalStatus(detail.status)) {
          startTaskStream(detail.id);
        } else {
          closeTaskStream();
        }
      } else {
        closeTaskStream();
        setSelectedTask(null);
        setLogs([]);
        setToolCalls([]);
      }
    } catch (err) {
      if (!options?.silent) {
        setError(err instanceof Error ? err.message : "请求失败");
      }
    } finally {
      if (!options?.silent) {
        setIsLoading(false);
      }
    }
  }

  async function refreshConversations(selectConversationId?: number) {
    setIsLoading(true);
    setError(null);

    try {
      const nextConversations = await refreshConversationList();

      const nextSelected =
        nextConversations.find((conversation) => conversation.id === selectConversationId) ??
        (conversationId
          ? nextConversations.find((conversation) => conversation.id === conversationId)
          : undefined) ??
        nextConversations[0] ??
        null;

      if (nextSelected) {
        await selectConversation(nextSelected.id, { silent: true });
      } else {
        closeTaskStream();
        setSelectedConversation(null);
        setSelectedTask(null);
        setConversationId(null);
        setMessages([]);
        setLogs([]);
        setToolCalls([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "请求失败");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = taskText.trim();
    if (!text) return;

    setIsSubmitting(true);
    setError(null);

    try {
      const payload = await submitTask(text, conversationId);
      const nextConversationId = payload.conversation_id ?? conversationId;
      setConversationId(nextConversationId ?? null);
      setTaskText("");
      setShowTrace(false);
      await refreshConversations(nextConversationId ?? undefined);
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
      await refreshTaskSnapshot(payload.task_id);
      if (conversationId) {
        await refreshConversationMessages(conversationId);
        await refreshConversationList();
      }
      startTaskStream(payload.task_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "审批失败");
    } finally {
      setIsApproving(false);
    }
  }

  async function handleRenameConversation(conversation: Conversation) {
    const currentTitle = conversation.title ?? conversation.latest_task_title ?? "";
    const title = window.prompt("修改会话标题", currentTitle)?.trim();

    if (!title || title === currentTitle) return;

    setError(null);

    try {
      const updatedConversation = await updateConversation(conversation.id, { title });

      setConversations((current) =>
        current.map((item) =>
          item.id === updatedConversation.id ? updatedConversation : item,
        ),
      );

      if (conversationId === updatedConversation.id) {
        setSelectedConversation(updatedConversation);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "修改会话标题失败");
    }
  }

  async function handleDeleteConversation(conversation: Conversation) {
    const title = conversation.title ?? conversation.latest_task_title ?? "这个会话";
    const confirmed = window.confirm(`确定删除「${title}」吗？删除后无法在历史中查看。`);

    if (!confirmed) return;

    setError(null);

    try {
      await deleteConversation(conversation.id);

      if (conversationId === conversation.id) {
        resetConversationView();
      }

      const nextConversations = await refreshConversationList();

      if (conversationId === conversation.id) {
        return;
      }

      if (!nextConversations.some((item) => item.id === conversationId)) {
        resetConversationView();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除会话失败");
    }
  }

  useEffect(() => {
    void refreshConversations();

    return () => {
      closeTaskStream();
    };
  }, []);

  useLayoutEffect(() => {
    const input = taskInputRef.current;
    if (!input) return;

    const maxHeight = 92;
    const minHeight = 28;

    if (!taskText.trim()) {
      input.style.height = `${minHeight}px`;
      input.style.overflowY = "hidden";
      return;
    }

    input.style.height = "auto";
    const nextHeight = Math.min(Math.max(input.scrollHeight, minHeight), maxHeight);
    input.style.height = `${nextHeight}px`;
    input.style.overflowY = input.scrollHeight > maxHeight ? "auto" : "hidden";
  }, [taskText]);

  useLayoutEffect(() => {
    if (!selectedTask && messages.length === 0) return;

    requestAnimationFrame(() => {
      messageEndRef.current?.scrollIntoView({
        block: "end",
        behavior: "smooth",
      });

      const viewport = chatViewportRef.current;
      if (viewport) {
        viewport.scrollTo({
          top: viewport.scrollHeight,
          behavior: "smooth",
        });
      }
    });
  }, [
    messages.length,
    selectedTask?.id,
    selectedTask?.final_response,
    selectedTask?.status,
    logs.length,
    toolCalls.length,
    showTrace,
  ]);

  const activeConversation =
    selectedConversation ??
    (conversationId
      ? conversations.find((conversation) => conversation.id === conversationId) ?? null
      : null);
  const hasActiveChat = Boolean(activeConversation || selectedTask || messages.length > 0);
  const workspaceTitle =
    activeConversation?.title ?? selectedTask?.task ?? activeConversation?.latest_task_title ?? "新对话";
  const selectedStatus =
    selectedTask?.status ?? activeConversation?.latest_task_status ?? "created";
  const needsApproval = selectedTask?.status === "pending_approval";
  const sourceLabel = toolSource(selectedTask?.selected_tool);
  const hasPersistedAssistantForTask = Boolean(
    selectedTask &&
      messages.some(
        (message) => message.role === "assistant" && message.task_id === selectedTask.id,
      ),
  );
  const shouldShowLiveAssistant = Boolean(
    selectedTask &&
      !needsApproval &&
      (!isTerminalStatus(selectedTask.status) ||
        (selectedTask.final_response && !hasPersistedAssistantForTask)),
  );

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
            resetConversationView();
            setTaskText("");
          }}
          type="button"
        >
          <MessageSquarePlus size={16} />
          新对话
        </button>

        <button className="refreshButton" onClick={() => refreshConversations()} disabled={isLoading}>
          {isLoading ? <Loader2 className="spin" size={16} /> : <RefreshCw size={16} />}
          刷新会话
        </button>

        <div className="conversationList">
          {conversations.length === 0 && (
            <div className="emptyConversationList">暂无历史会话</div>
          )}
          {conversations.map((conversation) => (
            <div
              className={`conversationItem ${conversationId === conversation.id ? "active" : ""}`}
              key={conversation.id}
            >
              <button
                className="conversationSelect"
                onClick={() => selectConversation(conversation.id)}
                type="button"
              >
                <span className={`dot ${statusTone(conversation.latest_task_status ?? "created")}`} />
                <span className="conversationCopy">
                  <strong>{conversation.title ?? conversation.latest_task_title ?? "新会话"}</strong>
                  <small>
                    #{conversation.id} ·{" "}
                    {conversation.latest_task_status
                      ? statusLabels[conversation.latest_task_status] ??
                        conversation.latest_task_status
                      : "会话"}{" "}
                    · {formatTime(conversation.updated_at)}
                  </small>
                </span>
              </button>

              <div className="conversationActions">
                <button
                  aria-label="重命名会话"
                  onClick={() => handleRenameConversation(conversation)}
                  title="重命名"
                  type="button"
                >
                  <Pencil size={14} />
                </button>
                <button
                  aria-label="删除会话"
                  onClick={() => handleDeleteConversation(conversation)}
                  title="删除"
                  type="button"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
      </aside>

      <section className={`chatWorkspace ${hasActiveChat ? "" : "startMode"}`}>
        {hasActiveChat && (
          <header className="chatHeader">
            <div>
              <p className="eyebrow">Workspace</p>
              <h2>{workspaceTitle}</h2>
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

        <div className="chatViewport" ref={chatViewportRef}>
          {!hasActiveChat && (
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

          {hasActiveChat && (
            <div className="messageStack">
              {messages.map((message) => {
                const isUserMessage = message.role === "user";

                return (
                  <article
                    className={`messageRow ${isUserMessage ? "user" : "assistant"}`}
                    key={message.id}
                  >
                    <div className={`avatar ${isUserMessage ? "userAvatar" : "botAvatar"}`}>
                      {isUserMessage ? <User size={18} /> : <Bot size={18} />}
                    </div>
                    <div
                      className={`messageBubble ${
                        isUserMessage ? "userBubble" : "assistantBubble final"
                      }`}
                    >
                      {isUserMessage ? <p>{message.content}</p> : <pre>{message.content}</pre>}
                      {isUserMessage && <span>{formatTime(message.created_at)}</span>}
                    </div>
                  </article>
                );
              })}

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

              {shouldShowLiveAssistant && (
                <article className="messageRow assistant">
                  <div className="avatar botAvatar">
                    <Bot size={18} />
                  </div>
                  <div className="messageBubble assistantBubble final">
                    <pre>
                      {selectedTask?.final_response ??
                        (selectedTask && isTerminalStatus(selectedTask.status)
                          ? "任务还没有生成最终回复。"
                          : "正在生成回复...")}
                    </pre>
                  </div>
                </article>
              )}

              {selectedTask && (
                <article className="traceToggleRow">
                  <button
                    className="traceToggleButton"
                    onClick={() => setShowTrace((value) => !value)}
                    type="button"
                  >
                    <Clock3 size={16} />
                    {showTrace ? "隐藏执行过程" : "查看执行过程"}
                    <span>
                      {orderedLogs.length} 条日志 · {orderedToolCalls.length} 次工具调用
                    </span>
                  </button>
                </article>
              )}

              {showTrace && selectedTask && (
                <article className="messageRow assistant tracePanelRow">
                  <div className="avatar toolCallAvatar">
                    <Wrench size={17} />
                  </div>
                  <div className="messageBubble toolCallsBubble">
                    <div className="toolCallsHeader">
                      <div>
                        <strong>执行过程</strong>
                        <span>
                          {selectedTask.selected_tool ?? "等待选择工具"} · {sourceLabel} ·{" "}
                          {formatTime(selectedTask.updated_at)}
                        </span>
                      </div>
                      <b>{statusLabels[selectedStatus] ?? selectedStatus}</b>
                    </div>

                    <div className="traceSection">
                      <div className="traceSectionTitle">
                        <Wrench size={14} />
                        工具调用
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

                    <div className="traceSection">
                      <div className="traceSectionTitle">
                        <Clock3 size={14} />
                        执行日志
                      </div>
                      {orderedLogs.length === 0 ? (
                        <p className="emptyToolCalls">暂无日志。</p>
                      ) : (
                        <div className="traceLogList">
                          {orderedLogs.map((log) => (
                            <section className="traceLogCard" key={log.id}>
                              <div className="traceHead">
                                <strong>{log.node}</strong>
                                <span className={`miniStatus ${statusTone(log.status)}`}>
                                  {statusLabels[log.status] ?? log.status}
                                </span>
                              </div>
                              <pre>{compactMessage(log.message)}</pre>
                              <small>{formatTime(log.created_at)}</small>
                            </section>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </article>
              )}
              <div className="messageEnd" ref={messageEndRef} />
            </div>
          )}
        </div>

        {hasActiveChat && renderComposer("chatComposer dockComposer")}
      </section>
    </main>
  );
}
