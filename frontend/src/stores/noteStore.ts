// stores/noteStore.ts

import { create } from 'zustand';
import { notesAPI, tagsAPI } from '../api/notes';
import type { NoteListParams } from '../api/notes';
import type { Note, Tag, BatchDeleteNotesResponse } from '../types/note';

interface NoteState {
  notes: Note[];
  currentNote: Note | null;
  tags: Tag[];
  isLoading: boolean;
  fetchNotes: (params?: NoteListParams) => Promise<void>;
  fetchNote: (id: string) => Promise<void>;
  createNote: (data: Partial<Note>) => Promise<Note>;
  updateNote: (id: string, data: Partial<Note>) => Promise<Note>;
  deleteNote: (id: string) => Promise<void>;
  batchDeleteNotes: (ids: string[]) => Promise<BatchDeleteNotesResponse>;
  fetchTags: () => Promise<void>;
}

export const useNoteStore = create<NoteState>((set, get) => ({
  notes: [],
  currentNote: null,
  tags: [],
  isLoading: false,

  fetchNotes: async (params?: NoteListParams) => {
    set({ isLoading: true });
    try {
      const response = await notesAPI.list(params);
      // 兼容三种后端响应格式：裸数组、PaginatedResponse 或 ApiResponse 包装
      const body: any = response.data;
      let items: any[] = [];
      if (Array.isArray(body)) {
        items = body;
      } else if (body?.items) {
        items = body.items;
      } else if (body?.data?.items) {
        items = body.data.items;
      }
      set({ notes: items, isLoading: false });
    } catch (error) {
      set({ isLoading: false });
      throw error;
    }
  },

  fetchNote: async (id: string) => {
    set({ isLoading: true });
    try {
      const response = await notesAPI.get(id);
      // 兼容两种后端响应格式
      const body: any = response.data;
      set({ currentNote: body?.data?.id ? body.data : body, isLoading: false });
    } catch (error) {
      set({ isLoading: false });
      throw error;
    }
  },

  createNote: async (data: Partial<Note>) => {
    const response = await notesAPI.create(data);
    // 兼容两种后端响应格式
    const body: any = response.data;
    const note =
      body?.data && typeof body.data === 'object' && 'id' in body.data
        ? body.data
        : body;
    set({ notes: [...get().notes, note] });
    return note;
  },

  updateNote: async (id: string, data: Partial<Note>) => {
    const response = await notesAPI.update(id, data);
    // 兼容两种后端响应格式
    const body: any = response.data;
    const note =
      body?.data && typeof body.data === 'object' && 'id' in body.data
        ? body.data
        : body;
    set({
      notes: get().notes.map((n) => (n.id === id ? note : n)),
      currentNote: get().currentNote?.id === id ? note : get().currentNote,
    });
    return note;
  },

  deleteNote: async (id: string) => {
    await notesAPI.delete(id);
    set({ notes: get().notes.filter((n) => n.id !== id) });
  },

  batchDeleteNotes: async (ids: string[]) => {
    const response = await notesAPI.batchDelete({ ids });
    const body: any = response.data;
    const result: BatchDeleteNotesResponse =
      body?.data && typeof body.data === 'object' && 'deleted_count' in body.data
        ? body.data
        : body;
    const failedSet = new Set(result.failed_ids ?? []);
    set({ notes: get().notes.filter((n) => !failedSet.has(n.id)) });
    return result;
  },

  fetchTags: async () => {
    try {
      const response = await tagsAPI.list();
      // 兼容两种后端响应格式
      const body: any = response.data;
      const tags = Array.isArray(body) ? body : (body?.data ?? []);
      set({ tags });
    } catch (error) {
      console.error('Failed to fetch tags:', error);
    }
  },
}));
