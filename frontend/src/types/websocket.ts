// types/websocket.ts

import type { Lecture, QAMessage, DiagnosisResult } from './learning';
import type { ReviewPlan } from './review';

export type WSMessage =
  | { type: 'progress'; data: { stage: string; percent: number } }
  | { type: 'complete'; data: { lecture: Lecture; note_id: string | null } }
  | { type: 'token'; data: { content: string } }
  | { type: 'done'; data: { message: QAMessage } }
  | { type: 'diagnosis'; data: DiagnosisResult }
  | { type: 'error'; data: { message: string } }
  | { type: 'review_reminder'; data: { plan: ReviewPlan } }
  | { type: 'task_complete'; data: { task_type: string; result: unknown } };
