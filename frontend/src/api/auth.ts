// api/auth.ts

import { apiClient } from './client';
import type { AuthResponse, LoginRequest, RegisterRequest } from '../types/auth';

export const authAPI = {
  register: (data: RegisterRequest) => apiClient.post<AuthResponse>('/auth/register', data),

  login: (data: LoginRequest) => apiClient.post<AuthResponse>('/auth/login', data),

  refresh: (refreshToken: string) =>
    apiClient.post<{ access_token: string }>('/auth/refresh', { refresh_token: refreshToken }),

  logout: (refreshToken: string) => apiClient.post('/auth/logout', { refresh_token: refreshToken }),
};
