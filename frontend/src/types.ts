export type TaskStatus =
  | "created"
  | "running"
  | "planned"
  | "tool_selected"
  | "approved"
  | "pending_approval"
  | "tool_executed"
  | "completed"
  | "failed"
  | "cancelled"
  | "rejected"
  | string;

export interface Task {
  id: number;
  conversation_id: number | null;
  thread_id: string;
  task: string;
  status: TaskStatus;
  selected_tool: string | null;
  final_response: string | null;
  approval_required: boolean | null;
  approval_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface StepLog {
  id: number;
  task_id: number;
  node: string;
  status: string;
  message: string;
  created_at: string;
}

export interface ToolCall {
  id: number;
  task_id: number;
  step_index: number | null;
  step_description: string | null;
  tool_name: string;
  tool_input: unknown;
  tool_output: unknown;
  risk_level: string | null;
  approved: boolean | null;
  success: boolean | null;
  created_at: string;
}

export interface TaskRunResult {
  status?: TaskStatus;
  selected_tool?: string;
  tool_input?: Record<string, unknown>;
  final_response?: string;
  approval_required?: boolean;
  approval_reason?: string;
  step_logs?: StepLog[];
  __interrupt__?: unknown;
}

export interface TaskRunResponse {
  task_id: number;
  thread_id: string;
  conversation_id?: number;
  result: TaskRunResult;
}

export interface Conversation {
  id: number;
  title: string | null;
  summary: string | null;
  created_at: string;
  updated_at: string;
  latest_task_id: number | null;
  latest_task_title: string | null;
  latest_task_status: TaskStatus | null;
}

export interface ConversationMessage {
  id: number;
  conversation_id: number;
  task_id: number | null;
  role: string;
  content: string;
  created_at: string;
}
