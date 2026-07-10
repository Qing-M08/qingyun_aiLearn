// stores/learningStore.ts

import { create } from 'zustand';
import { learningAPI } from '../api/learning';
import type { RouteParams } from '../api/learning';
import type {
  LearningRoute,
  Lecture,
  QASession,
  QAMessage,
  RouteViewMode,
  StepFilterStatus,
  DisplayMessage,
  DiagnosisResult,
} from '../types/learning';

interface LearningState {
  // === Phase 1 已有状态 ===
  currentRoute: LearningRoute | null;
  currentLecture: Lecture | null;
  qaSessions: QASession[];

  // === Sprint 5 新增：路线导航 ===
  routeViewMode: RouteViewMode;
  stepFilterStatus: StepFilterStatus;
  selectedStepId: string | null;
  lectureGenerating: boolean;
  lectureProgress: { stage: string; percent: number } | null;

  // === Sprint 8 新增：讲义→笔记跳转 ===
  lectureCompleteNoteId: string | null;
  lectureNoteFailed: boolean;

  // === Sprint 6 新增：QA会话 ===
  currentQASession: QASession | null;
  qaMessages: DisplayMessage[];
  isQASending: boolean;
  diagnoses: DiagnosisResult[];

  // === Sprint 5 actions ===
  setCurrentRoute: (route: LearningRoute | null) => void;
  setRouteViewMode: (mode: RouteViewMode) => void;
  setStepFilterStatus: (status: StepFilterStatus) => void;
  setSelectedStepId: (stepId: string | null) => void;
  setLectureGenerating: (generating: boolean) => void;
  setLectureProgress: (progress: { stage: string; percent: number } | null) => void;
  set: (partial: Partial<LearningState>) => void;
  generateRoute: (params: RouteParams) => Promise<LearningRoute>;
  generateLecture: (routeId: string, stepId: string, nodeId?: string) => Promise<string>;

  // === Sprint 6 actions ===
  setCurrentQASession: (session: QASession | null) => void;
  setQaMessages: (messages: DisplayMessage[]) => void;
  addQaMessage: (message: DisplayMessage) => void;
  appendStreamingToken: (token: string) => void;
  finalizeStreamingMessage: (message: QAMessage) => void;
  setIsQASending: (sending: boolean) => void;
  addDiagnosis: (diagnosis: DiagnosisResult) => void;
  clearDiagnoses: () => void;
  createQASession: (data: { lecture_id?: string; node_id?: string; topic?: string }) => Promise<QASession>;
  sendQAMessage: (sessionId: string, content: string) => Promise<void>;
}

export const useLearningStore = create<LearningState>((set, get) => ({
  // === 初始状态 ===
  currentRoute: null,
  currentLecture: null,
  qaSessions: [],
  routeViewMode: 'timeline',
  stepFilterStatus: 'all',
  selectedStepId: null,
  lectureGenerating: false,
  lectureProgress: null,
  lectureCompleteNoteId: null,
  lectureNoteFailed: false,
  currentQASession: null,
  qaMessages: [],
  isQASending: false,
  diagnoses: [],

  // === Sprint 5 actions ===
  setCurrentRoute: (route) => set({ currentRoute: route }),
  setRouteViewMode: (mode) => set({ routeViewMode: mode }),
  setStepFilterStatus: (status) => set({ stepFilterStatus: status }),
  setSelectedStepId: (stepId) => set({ selectedStepId: stepId }),
  setLectureGenerating: (generating) => set({ lectureGenerating: generating }),
  setLectureProgress: (progress) => set({ lectureProgress: progress }),
  set: (partial) => set(partial),

  generateRoute: async (params) => {
    const response = await learningAPI.generateRoute(params);
    // 兼容两种后端响应格式
    const body: any = response.data;
    const route =
      body?.data && typeof body.data === 'object' && 'id' in body.data
        ? body.data
        : body;
    set({ currentRoute: route });
    return route;
  },

  generateLecture: async (routeId, stepId, nodeId) => {
    set({ lectureGenerating: true, lectureProgress: { stage: '请求生成...', percent: 0 } });
    try {
      const response = await learningAPI.generateLecture({
        route_id: routeId,
        step_id: stepId,
        node_id: nodeId,
      });
      // 兼容两种后端响应格式
      const body: any = response.data;
      const lectureId =
        body?.data && typeof body.data === 'object' && 'lecture_id' in body.data
          ? body.data.lecture_id
          : body.lecture_id;
      return lectureId;
    } finally {
      // lectureGenerating 在WebSocket complete/error 消息中重置
    }
  },

  // === Sprint 6 actions ===
  setCurrentQASession: (session) => set({ currentQASession: session }),
  setQaMessages: (messages) => set({ qaMessages: messages }),
  addQaMessage: (msg) =>
    set((state) => ({ qaMessages: [...state.qaMessages, msg] })),
  appendStreamingToken: (token) =>
    set((state) => {
      const messages = [...state.qaMessages];
      const lastMsg = messages[messages.length - 1];
      if (lastMsg && lastMsg.id === 'streaming') {
        lastMsg.content += token;
      } else {
        messages.push({
          id: 'streaming',
          session_id: state.currentQASession?.id || '',
          role: 'assistant',
          content: token,
          metadata: {},
          created_at: new Date().toISOString(),
          isStreaming: true,
        });
      }
      return { qaMessages: messages };
    }),
  finalizeStreamingMessage: (msg) =>
    set((state) => {
      const messages = state.qaMessages.filter((m) => m.id !== 'streaming');
      messages.push({ ...msg, isStreaming: false });
      return { qaMessages: messages, isQASending: false };
    }),
  setIsQASending: (sending) => set({ isQASending: sending }),
  addDiagnosis: (diagnosis) =>
    set((state) => ({ diagnoses: [...state.diagnoses, diagnosis] })),
  clearDiagnoses: () => set({ diagnoses: [] }),

  createQASession: async (data) => {
    const response = await learningAPI.createQASession(data);
    // 兼容两种后端响应格式
    const body: any = response.data;
    const session =
      body?.data && typeof body.data === 'object' && 'id' in body.data
        ? body.data
        : body;
    set((state) => ({
      currentQASession: session,
      qaSessions: [...state.qaSessions, session],
    }));
    return session;
  },

  sendQAMessage: async (sessionId, content) => {
    const userMsg: DisplayMessage = {
      id: `temp-${Date.now()}`,
      session_id: sessionId,
      role: 'user',
      content,
      metadata: {},
      created_at: new Date().toISOString(),
      isStreaming: false,
    };
    get().addQaMessage(userMsg);
    set({ isQASending: true });
    await learningAPI.sendQAMessage(sessionId, content);
  },
}));
