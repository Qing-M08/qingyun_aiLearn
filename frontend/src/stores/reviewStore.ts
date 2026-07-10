// stores/reviewStore.ts

import { create } from 'zustand';
import type {
  ReviewPlan,
  ReviewStats,
  ReviewSessionState,
  FlashcardContent,
  QuizContent,
  ExplanationContent,
} from '../types/review';
import { reviewAPI } from '../api/review';

interface ReviewState {
  // 复习计划列表
  plans: ReviewPlan[];
  plansTotal: number;
  plansLoading: boolean;

  // 复习统计
  stats: ReviewStats | null;

  // 当前复习会话
  sessionState: ReviewSessionState;

  // 筛选条件
  statusFilter: string;
  dateRange: { from: string; to: string } | null;

  // Actions
  fetchPlans: (params?: Record<string, string>) => Promise<void>;
  fetchStats: () => Promise<void>;
  setStatusFilter: (filter: string) => void;
  setDateRange: (range: { from: string; to: string } | null) => void;

  // 复习会话 actions
  initSession: (plan: ReviewPlan) => void;
  setCurrentContent: (content: FlashcardContent | QuizContent | ExplanationContent | null) => void;
  setIsFlipped: (flipped: boolean) => void;
  setSelectedOption: (option: number | null) => void;
  setSelfRating: (rating: number | null) => void;
  advanceToNextPlan: () => void;
  completeCurrentPlan: (performance: number, notes?: string) => Promise<void>;
}

export const useReviewStore = create<ReviewState>((set, get) => ({
  plans: [],
  plansTotal: 0,
  plansLoading: false,
  stats: null,
  sessionState: {
    currentPlanIndex: 0,
    plans: [],
    currentContent: null,
    isLoading: false,
    isFlipped: false,
    selectedOption: null,
    selfRating: null,
  },
  statusFilter: 'all',
  dateRange: null,

  fetchPlans: async (params) => {
    set({ plansLoading: true });
    try {
      const response = await reviewAPI.getPlans(params);
      // 兼容三种后端响应格式：裸数组、PaginatedResponse 或 ApiResponse 包装
      const body: any = response.data;
      let data: any;
      if (Array.isArray(body)) {
        data = { items: body, total: body.length };
      } else if (body?.items) {
        data = body;
      } else {
        data = body?.data ?? { items: [], total: 0 };
      }
      set({
        plans: data.items ?? [],
        plansTotal: data.total ?? 0,
        plansLoading: false,
      });
    } catch {
      set({ plansLoading: false });
    }
  },

  fetchStats: async () => {
    try {
      const response = await reviewAPI.getStats();
      // 兼容两种后端响应格式
      const body: any = response.data;
      set({ stats: body?.data ?? body });
    } catch {
      // 统计加载失败不影响主流程
    }
  },

  setStatusFilter: (filter) => set({ statusFilter: filter }),
  setDateRange: (range) => set({ dateRange: range }),

  initSession: (plan) =>
    set({
      sessionState: {
        currentPlanIndex: 0,
        plans: [plan],
        currentContent: null,
        isLoading: true,
        isFlipped: false,
        selectedOption: null,
        selfRating: null,
      },
    }),

  setCurrentContent: (content) =>
    set((state) => ({
      sessionState: { ...state.sessionState, currentContent: content, isLoading: false },
    })),

  setIsFlipped: (flipped) =>
    set((state) => ({
      sessionState: { ...state.sessionState, isFlipped: flipped },
    })),

  setSelectedOption: (option) =>
    set((state) => ({
      sessionState: { ...state.sessionState, selectedOption: option },
    })),

  setSelfRating: (rating) =>
    set((state) => ({
      sessionState: { ...state.sessionState, selfRating: rating },
    })),

  advanceToNextPlan: () =>
    set((state) => {
      const nextIndex = state.sessionState.currentPlanIndex + 1;
      return {
        sessionState: {
          ...state.sessionState,
          currentPlanIndex: nextIndex,
          currentContent: null,
          isFlipped: false,
          selectedOption: null,
          selfRating: null,
        },
      };
    }),

  completeCurrentPlan: async (performance, notes) => {
    const { sessionState } = get();
    const currentPlan = sessionState.plans[sessionState.currentPlanIndex];
    if (!currentPlan) return;

    try {
      await reviewAPI.completePlan(currentPlan.id, { performance, notes });
      set((state) => {
        const updatedPlans = [...state.plans];
        const planIndex = updatedPlans.findIndex((p) => p.id === currentPlan.id);
        if (planIndex >= 0) {
          updatedPlans[planIndex] = {
            ...updatedPlans[planIndex],
            status: 'completed' as const,
            completed_at: new Date().toISOString(),
          };
        }
        return { plans: updatedPlans };
      });
    } catch {
      throw new Error('提交复习结果失败');
    }
  },
}));
