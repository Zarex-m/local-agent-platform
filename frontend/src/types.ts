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
  | "rejected"
  | string;

export interface Task {
  id: number;
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
  result: TaskRunResult;
}
