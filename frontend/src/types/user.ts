// types/user.ts

export interface User {
  id: string;
  email: string;
  username: string;
  role: 'student' | 'admin';
  avatar_url: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface UserProfile {
  id: string;
  user_id: string;
  cognitive_style: 'visual' | 'auditory' | 'kinesthetic';
  preferred_study_time: 'morning' | 'afternoon' | 'evening' | null;
  avg_session_duration: string | null;
  total_study_hours: number;
  streak_days: number;
  last_active_at: string | null;
  metadata: Record<string, unknown>;
}

export interface MasterySummary {
  total_nodes: number;
  mastered: number;
  learning: number;
  not_started: number;
  weakest_nodes: Array<{ node_id: string; name: string; mastery_score: number }>;
  strongest_nodes: Array<{ node_id: string; name: string; mastery_score: number }>;
}
