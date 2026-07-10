// types/search.ts

export interface SearchResult {
  id: string;
  type: 'note' | 'lecture' | 'knowledge';
  title: string;
  content_preview: string;
  subject: string | null;
  score: number;
  tag_names?: string[];
  created_at: string;
}
