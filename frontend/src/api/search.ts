// api/search.ts

import { apiClient } from './client';
import type { SearchResult } from '../types/search';

export const searchAPI = {
  search: (params: {
    q: string;
    type?: 'notes' | 'lectures' | 'knowledge' | 'all';
    subject?: string;
    page?: number;
    page_size?: number;
  }) => apiClient.get<{ results: SearchResult[]; total: number }>('/search', { params }),

  semanticSearch: (params: { q: string; type?: string; top_k?: number }) =>
    apiClient.get<SearchResult[]>('/search/semantic', { params }),
};
