// hooks/useNotificationWS.ts

import { useCallback } from 'react';
import { useWebSocket } from './useWebSocket';
import { message } from 'antd';
import type { ReviewPlan } from '../types/review';

export function useNotificationWS(isAuthenticated: boolean) {
  const handleNotification = useCallback(
    (wsMsg: { type: string; data: unknown }) => {
      switch (wsMsg.type) {
        case 'review_reminder': {
          const data = wsMsg.data as { plan: ReviewPlan };
          message.info({
            content: `复习提醒：${data.plan.node?.name || '知识点'}的复习时间到了！`,
            duration: 10,
            key: `review-${data.plan.id}`,
          });

          // Tauri环境下发送系统通知
          if ((window as unknown as { __TAURI__?: boolean }).__TAURI__) {
            import('@tauri-apps/api/core').then(({ invoke }) => {
              invoke('send_notification', {
                title: '复习提醒',
                body: `${data.plan.node?.name || '知识点'}的复习时间到了！`,
              });
            }).catch(() => {
              // Tauri API不可用，忽略
            });
          }
          break;
        }
        case 'task_complete': {
          const data = wsMsg.data as { task_type: string; result: unknown };
          message.success(`任务完成：${data.task_type}`);
          break;
        }
      }
    },
    []
  );

  const { isConnected } = useWebSocket({
    url: isAuthenticated ? '/api/v1/ws/notifications' : null,
    onMessage: handleNotification,
    reconnect: true,
    heartbeatInterval: 30000,
  });

  return { isConnected };
}
