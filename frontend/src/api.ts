import type { StepLog, Task, TaskRunResponse, ToolCall } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

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

export function getTask(taskId: number): Promise<Task> {
  return request<Task>(`/tasks/${taskId}`);
}

export function getTaskLogs(taskId: number): Promise<StepLog[]> {
  return request<StepLog[]>(`/tasks/${taskId}/logs`);
}

export function getTaskToolCalls(taskId: number): Promise<ToolCall[]> {
  return request<ToolCall[]>(`/tasks/${taskId}/tool-calls`);
}

export function submitTask(task: string): Promise<TaskRunResponse> {
  return request<TaskRunResponse>("/tasks/", {
    method: "POST",
    body: JSON.stringify({ task }),
  });
}

export function approveTask(taskId: number, approved: boolean): Promise<TaskRunResponse> {
  return request<TaskRunResponse>(`/tasks/${taskId}/approve`, {
    method: "POST",
    body: JSON.stringify({ approved }),
  });
}
