# 笔记页面 AI 对话功能修复 — 进度总结

> 时间：2026-07-09  
> 状态：✅ 已完成 — 可正常发送消息并收到 AI 回复（HTTP fallback 模式）

---

## 一、问题演进与修复历程

### 第一轮：输入无响应，后端未收到请求

**现象**：笔记编辑器的 AI 面板可以输入文字，但发送后无任何反应，后端终端没有任何请求日志。

**根因**：`NoteEditorPage.tsx` 的 `handleSendMessage` 函数只操作本地 React 状态（`setChatMessages`），从未调用任何后端 API。整个 AI 聊天是一个空壳。

**修复**：
- 用成熟的 `ChatPanel` 组件替换内联空壳实现
- 添加 QA 会话自动创建逻辑（`learningAPI.createQASession`）
- 添加 `qaSessionError` 状态 + 重试按钮（避免永久 loading）
- 新增 `ChatPanel` / `MessageBubble` CSS 样式

---

### 第二轮：WebSocket 连接 Vite 开发服务器失败

**现象**：浏览器控制台报 `WebSocket connection to 'ws://localhost:5173/api/v1/ws/qa-stream/...' failed`

**根因**：`useWebSocket` 用 `window.location.host`（`localhost:5173`，Vite 开发服务器）构建 URL。虽然 `vite.config.ts` 配置了 `ws: true` 代理，但 Vite 的 WebSocket 代理不可靠。

**修复**：
- `useWebSocket.ts` 新增 `resolveWSBaseURL()` 三级解析策略
- 创建 `.env.development`，设置 `VITE_WS_TARGET=ws://127.0.0.1:8000` 直连后端

---

### 第三轮：connect → close 循环，发送按钮灰色

**现象**：WebSocket 连接到后端后又立即断开（connected → closed 循环），发送按钮因 `!isConnected` 判定而禁用，底部持续闪烁"连接断开，正在重连…"

**根因**：
1. 后端不接受 WebSocket 端点（连接即关）
2. `sendQAMessage` 的 HTTP 返回值已包含 `assistant_message`，但 ChatPanel 完全忽略它
3. 发送按钮 `disabled={!inputValue.trim() || !isConnected}` — WS 一断就灰

**修复**：
- ChatPanel `handleSend`：处理 `sendQAMessage` 返回值，从 `res.data` 提取 `assistant_message` 直接展示
- 发送按钮：`disabled` 移除 `!isConnected` 条件
- 状态栏：仅在重试 ≥3 次后显示，文案改为"流式连接不可用（仍可发送消息）"

---

## 二、修改文件清单

| 文件 | 修改类型 | 说明 |
|---|---|---|
| `src/pages/notes/NoteEditorPage.tsx` | 重构 | 用 ChatPanel 替换内联空壳 + QA 会话管理 + 错误/重试状态 |
| `src/components/chat/ChatPanel.tsx` | 增强 | HTTP fallback（assistant_message）+ 解除 WS 依赖 |
| `src/hooks/useWebSocket.ts` | 增强 | resolveWSBaseURL() 三级解析 + reconnectCount 导出 |
| `src/App.css` | 新增 | ChatPanel 布局样式 + MessageBubble BEM 样式（~140 行） |
| `.env.development` | 新建 | VITE_WS_TARGET=ws://127.0.0.1:8000 |

---

## 三、当前架构：双通道设计

```
用户发送消息
     │
     ▼
learningAPI.sendQAMessage(sessionId, content)  ← HTTP POST
     │
     ├── 成功 → 提取 assistant_message → 直接展示 ✅（当前工作路径）
     │
     └── 同时 WebSocket 尝试连接 ws://127.0.0.1:8000/api/v1/ws/qa-stream/:id
              │
              ├── 连接成功 → 流式接收 token → 逐字展示（未来启用）
              └── 连接失败 → 静默，HTTP fallback 已覆盖 ⚠️
```

**关键设计决策**：HTTP 和 WebSocket 互为冗余，任一可用即可正常对话。

---

## 四、待处理事项

| 事项 | 优先级 | 说明 |
|---|---|---|
| 后端确认 WebSocket 端点 | 中 | 后端 `/api/v1/ws/qa-stream/:id` 是否实现？对应路径是否正确？ |
| 流式回复体验 | 低 | WebSocket 可用后可实现 token 级逐字输出 |
| `tags` 变量未使用警告 | 低 | `NoteEditorPage.tsx` L61 的 `tags` 查询结果未消费 |

---

## 五、环境变量

```
# .env.development
VITE_WS_TARGET=ws://127.0.0.1:8000
```

修改此文件后需**重启 `npm run dev`** 生效。
