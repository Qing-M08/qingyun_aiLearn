// stores/authStore.ts

import { create } from 'zustand';
import { authAPI } from '../api/auth';
import type { User } from '../types/user';

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  isDevMode: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, username: string, password: string) => Promise<void>;
  devLogin: () => void;
  logout: () => void;
  refreshTokenAction: () => Promise<void>;
  loadFromStorage: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  accessToken: null,
  refreshToken: null,
  isAuthenticated: false,
  isLoading: false,
  isDevMode: false,

  login: async (email: string, password: string) => {
    set({ isLoading: true });
    try {
      const response = await authAPI.login({ email, password });
      // 兼容两种后端响应格式
      const body: any = response.data;
      const { user, access_token, refresh_token } =
        body?.data && typeof body.data === 'object' && 'user' in body.data
          ? body.data
          : body;
      set({
        user,
        accessToken: access_token,
        refreshToken: refresh_token,
        isAuthenticated: true,
        isLoading: false,
        isDevMode: false,
      });
      if ((window as any).__TAURI__) {
        await (window as any).__TAURI__.invoke('save_offline_data', {
          key: 'auth',
          data: JSON.stringify({ user, access_token, refresh_token }),
        });
      }
    } catch (error) {
      set({ isLoading: false });
      throw error;
    }
  },

  register: async (email: string, username: string, password: string) => {
    set({ isLoading: true });
    try {
      const response = await authAPI.register({ email, username, password });
      // 兼容两种后端响应格式
      const body: any = response.data;
      const { user, access_token, refresh_token } =
        body?.data && typeof body.data === 'object' && 'user' in body.data
          ? body.data
          : body;
      set({
        user,
        accessToken: access_token,
        refreshToken: refresh_token,
        isAuthenticated: true,
        isLoading: false,
      });
    } catch (error) {
      set({ isLoading: false });
      throw error;
    }
  },

  devLogin: () => {
    const devUser: User = {
      id: 'dev-001',
      email: 'dev@qingyun.com',
      username: '开发者',
      role: 'student',
      avatar_url: null,
      is_active: true,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    set({
      user: devUser,
      accessToken: 'dev-token',
      refreshToken: 'dev-refresh',
      isAuthenticated: true,
      isLoading: false,
      isDevMode: true,
    });
  },

  logout: () => {
    const { refreshToken } = get();
    if (refreshToken) {
      authAPI.logout(refreshToken).catch(console.error);
    }
    set({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      isDevMode: false,
    });
    if ((window as any).__TAURI__) {
      (window as any).__TAURI__.invoke('save_offline_data', { key: 'auth', data: '' });
    }
  },

  refreshTokenAction: async () => {
    const { refreshToken, isDevMode } = get();
    // dev 模式下使用的是假 token，后端不认，跳过刷新避免被踢出
    if (isDevMode) {
      console.warn('[DevMode] 跳过 token 刷新（dev token 无法被后端验证）');
      return;
    }
    if (!refreshToken) {
      get().logout();
      return;
    }
    try {
      const response = await authAPI.refresh(refreshToken);
      // 兼容两种后端响应格式
      const body: any = response.data;
      const accessToken =
        body?.data && typeof body.data === 'object' && 'access_token' in body.data
          ? body.data.access_token
          : body.access_token;
      set({ accessToken });
    } catch (error) {
      get().logout();
      throw error;
    }
  },

  loadFromStorage: async () => {
    if ((window as any).__TAURI__) {
      try {
        const data = await (window as any).__TAURI__.invoke('get_offline_data', { key: 'auth' });
        if (data) {
          const { user, access_token, refresh_token } = JSON.parse(data as string);
          set({
            user,
            accessToken: access_token,
            refreshToken: refresh_token,
            isAuthenticated: true,
          });
        }
      } catch (error) {
        console.error('Failed to load auth from storage:', error);
      }
    }
  },
}));
