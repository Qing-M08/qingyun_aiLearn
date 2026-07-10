// stores/uiStore.ts

import { create } from 'zustand';

interface UIState {
  sidebarCollapsed: boolean;
  theme: 'light' | 'dark';
  activeModal: string | null;
  toggleSidebar: () => void;
  setTheme: (theme: 'light' | 'dark') => void;
  openModal: (modalId: string) => void;
  closeModal: () => void;
}

export const useUIStore = create<UIState>((set) => ({
  sidebarCollapsed: false,
  theme: 'light',
  activeModal: null,

  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),

  setTheme: (theme: 'light' | 'dark') => {
    set({ theme });
    document.documentElement.setAttribute('data-theme', theme);
  },

  openModal: (modalId: string) => set({ activeModal: modalId }),

  closeModal: () => set({ activeModal: null }),
}));
