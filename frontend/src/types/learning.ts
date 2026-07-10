// types/learning.ts

export interface LearningRoute {
  id: string;
  user_id: string;
  topic: string;
  description: string | null;
  status: 'active' | 'completed' | 'paused' | 'generating';
  total_steps: number;
  current_step: number;
  estimated_hours: number | null;
  metadata: Record<string, unknown>;
  steps: RouteStep[];
  created_at: string;
  updated_at: string;
}

export interface RouteStep {
  id: string;
  route_id: string;
  node_id: string | null;
  step_order: number;
  title: string;
  description: string | null;
  estimated_minutes: number | null;
  status: 'pending' | 'in_progress' | 'completed';
  prerequisites: string[];
  created_at: string;
  updated_at: string;
}

export interface Lecture {
  id: string;
  route_id: string | null;
  step_id: string | null;
  user_id: string;
  node_id: string | null;
  title: string;
  content: string;
  content_json: object | null;
  source_urls: string[];
  version: number;
  status: 'generating' | 'generated' | 'personalized';
  note_id: string | null;
  token_usage: number;
  created_at: string;
  updated_at: string;
}

export interface QASession {
  id: string;
  user_id: string;
  lecture_id: string | null;
  node_id: string | null;
  topic: string | null;
  status: 'active' | 'closed';
  created_at: string;
  updated_at: string;
}

export interface QAMessage {
  id: string;
  session_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

// === Sprint 5 新增：路线视图类型 ===

/** 路线视图模式 */
export type RouteViewMode = 'timeline' | 'graph' | 'list';

/** 步骤筛选状态 */
export type StepFilterStatus = 'all' | 'pending' | 'in_progress' | 'completed';

/** 路线进度摘要 */
export interface RouteProgress {
  totalSteps: number;
  completedSteps: number;
  inProgressSteps: number;
  pendingSteps: number;
  percentComplete: number;
  estimatedMinutesRemaining: number;
}

// === Sprint 6 新增：QA扩展类型 ===

/** 对话消息（扩展显示用） */
export interface DisplayMessage extends QAMessage {
  isStreaming?: boolean;
  renderedContent?: string;
}

/** QA上下文信息 */
export interface QAContextInfo {
  lectureId?: string;
  lectureTitle?: string;
  nodeName?: string;
  masteryScore?: number;
}

/** 批量删除请求 */
export interface BatchDeleteRoutesRequest {
  route_ids: string[];
}

/** 批量删除响应 */
export interface BatchDeleteRoutesResponse {
  deleted_count: number;
  failed_ids: Array<{ id: string; reason: string }>;
}

/** AI诊断结果 */
export interface DiagnosisResult {
  node_id: string;
  mastery_update: number;
  weak_points?: string[];
  suggestion?: string;
}
