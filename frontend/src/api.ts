import type {
  Conversation,
  ConversationMessage,
  StepLog,
  Task,
  TaskRunResponse,
  ToolCall,
} from "./types";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function listTasks(limit = 20): Promise<Task[]> {
  return request<Task[]>(`/tasks/?limit=${limit}`);
}

export function listConversations(limit = 30): Promise<Conversation[]> {
  return request<Conversation[]>(`/conversations/?limit=${limit}`);
}

export function getConversation(conversationId: number): Promise<Conversation> {
  return request<Conversation>(`/conversations/${conversationId}`);
}

export function getConversationMessages(
  conversationId: number,
): Promise<ConversationMessage[]> {
  return request<ConversationMessage[]>(`/conversations/${conversationId}/messages`);
}

export function updateConversation(
  conversationId: number,
  payload: { title?: string; summary?: string },
): Promise<Conversation> {
  return request<Conversation>(`/conversations/${conversationId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteConversation(
  conversationId: number,
): Promise<{ success: boolean }> {
  return request<{ success: boolean }>(`/conversations/${conversationId}`, {
    method: "DELETE",
  });
}

export function getTask(taskId: number): Promise<Task> {
  return request<Task>(`/tasks/${taskId}`);
}

export function getTaskLogs(taskId: number): Promise<StepLog[]> {
  return request<StepLog[]>(`/tasks/${taskId}/logs`);
}

export function getTaskToolCalls(taskId: number): Promise<ToolCall[]> {
  return request<ToolCall[]>(`/tasks/${taskId}/tool-calls`);
}

export function createTaskEventSource(taskId: number): EventSource {
  return new EventSource(`${API_BASE_URL}/tasks/${taskId}/events`);
}

export function submitTask(
  task: string,
  conversationId?: number | null,
): Promise<TaskRunResponse> {
  return request<TaskRunResponse>("/tasks/", {
    method: "POST",
    body: JSON.stringify({ task, conversation_id: conversationId ?? null }),
  });
}

export function approveTask(taskId: number, approved: boolean): Promise<TaskRunResponse> {
  return request<TaskRunResponse>(`/tasks/${taskId}/approve`, {
    method: "POST",
    body: JSON.stringify({ approved }),
  });
}
