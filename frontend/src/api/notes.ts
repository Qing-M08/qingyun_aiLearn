// api/notes.ts

import { apiClient } from './client';
import type { Note, NoteTag, Tag, TagSelection, BatchDeleteNotesRequest, BatchDeleteNotesResponse } from '../types/note';
import type { PaginatedResponse } from '../types/common';

export interface NoteListParams {
  page?: number;
  page_size?: number;
  subject?: string;
  tag_ids?: string;
  search?: string;
  sort_by?: 'created_at' | 'updated_at' | 'word_count';
  sort_order?: 'asc' | 'desc';
}

export const notesAPI = {
  list: (params?: NoteListParams) =>
    apiClient.get<PaginatedResponse<Note>>('/notes', { params }),

  get: (noteId: string) => apiClient.get<Note>(`/notes/${noteId}`),

  create: (data: Partial<Note>) => apiClient.post<Note>('/notes', data),

  update: (noteId: string, data: Partial<Note>) => apiClient.put<Note>(`/notes/${noteId}`, data),

  delete: (noteId: string) => apiClient.delete(`/notes/${noteId}`),

  batchDelete: (data: BatchDeleteNotesRequest) =>
    apiClient.post<BatchDeleteNotesResponse>('/notes/batch-delete', data),

  addTag: (noteId: string, data: TagSelection) =>
    apiClient.post<NoteTag>(`/notes/${noteId}/tags`, data),

  removeTag: (noteId: string, tagId: string) =>
    apiClient.delete(`/notes/${noteId}/tags/${tagId}`),

  getTagIndex: (tagId: string, params?: { page?: number; page_size?: number }) =>
    apiClient.get<PaginatedResponse<Note>>(`/notes/tags/${tagId}/index`, { params }),
};

export const tagsAPI = {
  list: () => apiClient.get<Tag[]>('/tags'),

  create: (data: { name: string; color?: string; description?: string }) =>
    apiClient.post<Tag>('/tags', data),
};
