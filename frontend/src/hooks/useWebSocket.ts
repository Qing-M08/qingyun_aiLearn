// hooks/useWebSocket.ts

import { useEffect, useRef, useCallback, useState } from 'react';
import { useAuthStore } from '../stores/authStore';
import type { WSMessage } from '../types/websocket';

/** 解析 WebSocket 基地址（ws://host:port），优先直连后端，绕过 Vite 代理 */
function resolveWSBaseURL(): string {
  // 1. 优先使用 VITE_WS_TARGET 指定的 WebSocket 地址
  const wsTarget = import.meta.env.VITE_WS_TARGET;
  if (wsTarget) return wsTarget;

  // 2. 从 VITE_API_BASE_URL 提取（当 HTTP API 也直连后端时）
  const apiBase = import.meta.env.VITE_API_BASE_URL;
  if (apiBase && (apiBase.startsWith('http://') || apiBase.startsWith('https://'))) {
    const url = new URL(apiBase);
    const wsProtocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${wsProtocol}//${url.host}`;
  }

  // 3. 回退到 window.location（依赖 Vite 代理，但 WS 代理可能不可用）
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}`;
}

interface UseWebSocketOptions {
  url: string | null;
  onMessage: (message: WSMessage) => void;
  onError?: (error: Event) => void;
  onClose?: () => void;
  onOpen?: () => void;
  reconnect?: boolean;
  heartbeatInterval?: number;
}

export const useWebSocket = ({
  url,
  onMessage,
  onError,
  onClose,
  onOpen,
  reconnect = true,
  heartbeatInterval = 30000,
}: UseWebSocketOptions) => {
  const [isConnected, setIsConnected] = useState(false);
  const [reconnectCount, setReconnectCount] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);
  const heartbeatRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectCountRef = useRef(0);
  const maxReconnectDelay = 30000;

  // 使用 ref 存储所有可能变化的配置，避免 useCallback 依赖不稳定
  const onMessageRef = useRef(onMessage);
  const onErrorRef = useRef(onError);
  const onCloseRef = useRef(onClose);
  const onOpenRef = useRef(onOpen);
  const urlRef = useRef(url);
  const reconnectRef = useRef(reconnect);
  const heartbeatIntervalRef = useRef(heartbeatInterval);

  // 每次渲染同步最新值到 ref
  useEffect(() => {
    onMessageRef.current = onMessage;
    onErrorRef.current = onError;
    onCloseRef.current = onClose;
    onOpenRef.current = onOpen;
    urlRef.current = url;
    reconnectRef.current = reconnect;
    heartbeatIntervalRef.current = heartbeatInterval;
  });

  const startHeartbeat = useCallback(() => {
    if (heartbeatRef.current) clearInterval(heartbeatRef.current);
    heartbeatRef.current = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send('ping');
      }
    }, heartbeatIntervalRef.current);
  }, []);

  const stopHeartbeat = useCallback(() => {
    if (heartbeatRef.current) {
      clearInterval(heartbeatRef.current);
      heartbeatRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    const currentUrl = urlRef.current;
    if (!currentUrl) return;

    // 关闭旧连接
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    const token = useAuthStore.getState().accessToken;
    // 从 VITE_API_BASE_URL 解析 WebSocket 基地址，绕过 Vite 代理直连后端
    const wsBase = resolveWSBaseURL();
    const wsUrl = `${wsBase}${currentUrl}?token=${token}`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('WebSocket connected:', currentUrl);
      setIsConnected(true);
      setReconnectCount(0);
      reconnectCountRef.current = 0;
      startHeartbeat();
      onOpenRef.current?.();
    };

    ws.onmessage = (event) => {
      if (event.data === 'pong') return;
      try {
        const message: WSMessage = JSON.parse(event.data);
        console.log('[useWebSocket] received:', message.type, message.data);
        onMessageRef.current(message);
      } catch (err) {
        console.warn('[useWebSocket] 非JSON消息或解析失败:', event.data, err);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      onErrorRef.current?.(error);
    };

    ws.onclose = () => {
      console.log('WebSocket closed:', currentUrl);
      setIsConnected(false);
      stopHeartbeat();
      onCloseRef.current?.();

      if (reconnectRef.current && reconnectCountRef.current < 5) {
        const delay = Math.min(1000 * Math.pow(2, reconnectCountRef.current), maxReconnectDelay);
        reconnectTimeoutRef.current = setTimeout(() => {
          reconnectCountRef.current++;
          setReconnectCount((c) => c + 1);
          connect();
        }, delay);
      }
    };
  }, [startHeartbeat, stopHeartbeat]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    stopHeartbeat();
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsConnected(false);
  }, [stopHeartbeat]);

  // 发送消息
  const send = useCallback((data: string | object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      const payload = typeof data === 'string' ? data : JSON.stringify(data);
      wsRef.current.send(payload);
    }
  }, []);

  // 仅 URL 字符串值变化时才重连（url 为原始类型，值相等则不会触发）
  useEffect(() => {
    if (url) {
      connect();
    } else {
      disconnect();
    }
    return () => {
      disconnect();
    };
  }, [url, connect, disconnect]);

  return { isConnected, reconnectCount, send, disconnect };
};
