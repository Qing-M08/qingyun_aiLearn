// api/learning.ts

import { apiClient } from './client';
import type { LearningRoute, Lecture, QASession, QAMessage } from '../types/learning';
import type { PaginatedResponse } from '../types/common';

export interface RouteParams {
  topic: string;
  goal?: string;
  available_hours?: number;
  current_level?: 'beginner' | 'intermediate' | 'advanced';
  preferences?: Record<string, unknown>;
}

export const learningAPI = {
  generateRoute: (data: RouteParams) =>
    apiClient.post<LearningRoute>('/learning/routes', data),

  getRoute: (routeId: string) =>
    apiClient.get<LearningRoute>(`/learning/routes/${routeId}`),

  listRoutes: (params?: { status?: string; page?: number; page_size?: number }) =>
    apiClient.get<PaginatedResponse<LearningRoute>>('/learning/routes', { params }),

  completeStep: (routeId: string, stepId: string, data?: { duration_seconds?: number; notes?: string }) =>
    apiClient.patch(`/learning/routes/${routeId}/steps/${stepId}/complete`, data),

  generateLecture: (data: {
    route_id: string;
    step_id: string;
    node_id?: string;
    custom_instructions?: string;
  }) => apiClient.post<{ lecture_id: string; status: string }>('/learning/lectures/generate', data),

  getLecture: (lectureId: string) =>
    apiClient.get<Lecture>(`/learning/lectures/${lectureId}`),

  createQASession: (data: { lecture_id?: string; node_id?: string; topic?: string }) =>
    apiClient.post<QASession>('/learning/qa/sessions', data),

  sendQAMessage: (sessionId: string, content: string) =>
    apiClient.post<{ user_message: QAMessage; assistant_message: QAMessage }>(
      `/learning/qa/sessions/${sessionId}/messages`,
      { content }
    ),

  getQAMessages: (sessionId: string, params?: { before?: string; limit?: number }) =>
    apiClient.get<QAMessage[]>(`/learning/qa/sessions/${sessionId}/messages`, { params }),

  generatePersonalizedSummary: (data: { lecture_id: string; node_id?: string }) =>
    apiClient.post<{ lecture_id: string; status: string }>('/learning/personalized-summary', data),

  getQASessions: (params?: { lecture_id?: string; status?: string }) =>
    apiClient.get<QASession[]>('/learning/qa/sessions', { params }),

  closeQASession: (sessionId: string) =>
    apiClient.post(`/learning/qa/sessions/${sessionId}/close`),

  deleteRoute: (routeId: string) =>
    apiClient.delete(`/learning/routes/${routeId}`),

  batchDeleteRoutes: (routeIds: string[]) =>
    apiClient.delete('/learning/routes/batch', { data: { route_ids: routeIds } }),
};
