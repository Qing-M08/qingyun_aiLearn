// utils/tauriNotification.ts

/**
 * 发送系统通知
 * 在Tauri环境下调用Rust层的send_notification命令
 * 非Tauri环境下降级为浏览器Notification API
 */
export async function sendSystemNotification(
  title: string,
  body: string,
  options?: { tag?: string; requireInteraction?: boolean }
): Promise<void> {
  if ((window as unknown as { __TAURI__?: boolean }).__TAURI__) {
    try {
      const { invoke } = await import('@tauri-apps/api/core');
      await invoke('send_notification', { title, body });
    } catch (error) {
      console.warn('Tauri通知发送失败，降级为浏览器通知', error);
      sendBrowserNotification(title, body, options);
    }
  } else {
    sendBrowserNotification(title, body, options);
  }
}

/**
 * 浏览器Notification API降级方案
 */
function sendBrowserNotification(
  title: string,
  body: string,
  options?: { tag?: string; requireInteraction?: boolean }
): void {
  if (!('Notification' in window)) {
    console.warn('浏览器不支持Notification API');
    return;
  }

  if (Notification.permission === 'granted') {
    new Notification(title, {
      body,
      tag: options?.tag,
      requireInteraction: options?.requireInteraction,
    });
  } else if (Notification.permission !== 'denied') {
    Notification.requestPermission().then((permission) => {
      if (permission === 'granted') {
        new Notification(title, {
          body,
          tag: options?.tag,
          requireInteraction: options?.requireInteraction,
        });
      }
    });
  }
}

/**
 * 注册Tauri事件监听（复习提醒点击后跳转）
 */
export async function registerReviewReminderListener(
  onReminder: (planId: string) => void
): Promise<() => void> {
  if (!(window as unknown as { __TAURI__?: boolean }).__TAURI__) {
    return () => {};
  }

  const { listen } = await import('@tauri-apps/api/event');
  const unlisten = await listen<string>('review-reminder-click', (event) => {
    onReminder(event.payload);
  });

  return unlisten;
}
