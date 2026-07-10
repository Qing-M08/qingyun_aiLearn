// types/review.ts

export interface ReviewPlan {
  id: string;
  user_id: string;
  node_id: string;
  node?: {
    name: string;
    review_count?: number;
  };
  plan_date: string;
  scheduled_at?: string;
  completed_at?: string;
  status: 'pending' | 'completed' | 'skipped';
  priority: number;
  review_type: 'spaced' | 'exam' | 'custom';
  content: string | null;
  performance: number | null;
  created_at: string;
  updated_at: string;
}

export interface ReviewStats {
  today_due: number;
  this_week_completed: number;
  overdue_count: number;
  total_pending: number;
  mastery_distribution: MasteryDistribution;
}

// === Sprint 7 新增：复习内容类型 ===

/** 复习内容生成请求类型 */
export type ReviewContentType = 'flashcard' | 'quiz' | 'explanation';

/** 闪卡复习内容 */
export interface FlashcardContent {
  front: string;
  back: string;
  hint?: string;
}

/** 选择题复习内容 */
export interface QuizContent {
  question: string;
  options: QuizOption[];
  correctIndex: number;
  explanation: string;
}

export interface QuizOption {
  label: string;
  content: string;
}

/** 讲解复习内容 */
export interface ExplanationContent {
  title: string;
  content: string;
  keyPoints: string[];
}

/** 复习会话状态 */
export interface ReviewSessionState {
  currentPlanIndex: number;
  plans: ReviewPlan[];
  currentContent: FlashcardContent | QuizContent | ExplanationContent | null;
  isLoading: boolean;
  isFlipped: boolean;
  selectedOption: number | null;
  selfRating: number | null;
}

/** 复习完成提交数据 */
export interface ReviewCompleteData {
  performance?: number;
  notes?: string;
}

/** 掌握度分布数据（用于图表） */
export interface MasteryDistribution {
  not_started: number;
  learning: number;
  familiar: number;
  mastered: number;
}
