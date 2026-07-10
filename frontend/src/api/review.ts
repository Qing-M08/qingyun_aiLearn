// api/review.ts

import { apiClient } from './client';
import type { ReviewPlan, ReviewStats } from '../types/review';
import type { PaginatedResponse } from '../types/common';

export interface ReviewPlanListParams {
  status?: string;
  from_date?: string;
  to_date?: string;
  page?: number;
  page_size?: number;
}

export interface ReviewGenerateContentParams {
  node_id: string;
  review_type?: 'flashcard' | 'quiz' | 'explanation';
}

export interface ReviewCompleteParams {
  performance?: number;
  notes?: string;
}

export const reviewAPI = {
  /**
   * 获取复习计划列表
   * GET /api/v1/review/plans
   */
  getPlans: (params?: ReviewPlanListParams) =>
    apiClient.get<PaginatedResponse<ReviewPlan>>('/review/plans', { params }),

  /**
   * 获取单个复习计划详情
   * GET /api/v1/review/plans/{planId}
   */
  getPlan: (planId: string) =>
    apiClient.get<ReviewPlan>(`/review/plans/${planId}`),

  /**
   * 完成复习计划
   * POST /api/v1/review/plans/{planId}/complete
   */
  completePlan: (planId: string, data?: ReviewCompleteParams) =>
    apiClient.post(`/review/plans/${planId}/complete`, data),

  /**
   * 生成复习内容
   * POST /api/v1/review/generate-content
   */
  generateContent: (data: ReviewGenerateContentParams) =>
    apiClient.post<{ content: string; type: string }>('/review/generate-content', data),

  /**
   * 获取复习统计
   * GET /api/v1/review/stats
   */
  getStats: () =>
    apiClient.get<ReviewStats>('/review/stats'),

  /**
   * 跳过复习计划
   * POST /api/v1/review/plans/{planId}/skip
   */
  skipPlan: (planId: string) =>
    apiClient.post(`/review/plans/${planId}/skip`),
};
