# Phase 4 Sprint 9 — 前端开发规格

> 对应后端文档: Phase4-Sprint9-笔记AI增强-P1-青云智学后端开发文档.md  
> 后端 API 基础路径: `http://{host}:8000/api/v1`  
> WebSocket 基础路径: `ws://{host}:8000`

---

## 1. 概览

本阶段前端需对接两项新能力：

| 功能 | 交互方式 | 后端链路 |
|------|---------|---------|
| AI 整理笔记 | 笔记列表多选 → 弹窗输入提示词 → 进度条 → 跳转成果笔记 | HTTP POST → Celery → WS 进度推送 |
| AI 修改笔记 | Agent 对话中触发 → 编辑器实时更新 → Ctrl+Z 可撤销 | Agent WebSocket → edit_note 工具 → 通知 WS 推送 |

---

## 2. 新增 API 端点

### 2.1 POST /api/v1/notes/organize — AI 整理笔记

**请求**:
```typescript
interface OrganizeNotesRequest {
  note_ids: string[];   // 1~20 篇笔记 ID
  prompt: string;       // 额外提示词，最长 2000 字符，可为空
}
```

**响应**:
```typescript
interface OrganizeNotesResponse {
  task_id: string;      // Celery 任务 ID，用于 WS 监听进度
  message: string;      // "笔记整理任务已提交，共 N 篇笔记"
}
```

**错误码**:
| 状态码 | 说明 |
|--------|------|
| 400 | 笔记数量超出 1~20 范围 / 笔记不存在或不属于当前用户 |
| 401 | 未登录 |

---

## 3. WebSocket 端点

### 3.1 WS /ws/organize-progress/{task_id} — 整理进度推送 (新增)

**连接地址**: `ws://{host}:8000/ws/organize-progress/{task_id}?token={access_token}`

**消息格式**（服务端 → 客户端）:
```typescript
interface OrganizeProgress {
  stage: "preparing" | "generating" | "complete" | "error";
  percent: number;        // 0 ~ 100
  message: string;        // 人类可读的阶段描述
  note_id?: string;       // 成果笔记 ID（仅 complete）
  title?: string;         // 笔记标题（仅 complete）
  word_count?: number;    // 字数（仅 complete）
  source_count?: number;  // 源笔记数（仅 complete）
  error?: string;         // 错误信息（仅 error）
}
```

**进度阶段**:
```
preparing (10%)  →  generating (30%)  →  complete (100%)
                                      →  error (失败)
```

**生命周期**: 连接 → 订阅 Redis 频道 → 逐条接收进度消息 → 收到 `complete`/`error` 后自动关闭。

### 3.2 WS /api/v1/ws/notifications — 新增 note_edit 消息类型 (扩展现有)

在现有通知 WebSocket 上，新增以下消息类型：

```typescript
// 当编辑发生在当前已打开的笔记时
interface NoteEditNotification {
  type: "note_edit";
  data: {
    note_id: string;
    operation: "insert" | "replace" | "delete";
    start_line: number;     // 1-based
    end_line: number | null;
    content: string;        // insert/replace 的新内容
    new_content: string;    // 编辑后的完整笔记内容
    title: string;
    word_count: number;
  };
}
```

---

## 4. 数据模型变更

### 4.1 Note 模型新增字段

```typescript
interface Note {
  // ... 现有字段保持不变 ...
  origin_type: "user" | "ai_organized";  // 来源类型
  source_note_ids: string[] | null;       // AI 整理时的源笔记 ID 列表
}
```

- `origin_type = "ai_organized"` 标识由 AI 整理生成的笔记
- `source_note_ids` 记录整理时引用的原始笔记，可用于溯源展示

---

## 5. 功能实现指引

### 5.1 AI 整理笔记 — 完整交互流程

```
笔记列表页
  │
  ├─ 进入多选模式
  │    └─ 选中 2~20 篇笔记
  │       └─ 出现「AI 整理」按钮 (与「批量删除」并列)
  │
  ├─ 点击「AI 整理」
  │    └─ 弹出 OrganizeModal
  │         ├─ TextArea: 输入整理方式 (可选，placeholder 见下)
  │         ├─ 按钮: [取消] [开始整理]
  │         │
  │         └─ 点击「开始整理」
  │              ├─ POST /api/v1/notes/organize → 获得 task_id
  │              ├─ 连接 WS /ws/organize-progress/{task_id}
  │              ├─ 显示进度条 + 阶段文字
  │              │   preparing  → "正在准备笔记内容..."
  │              │   generating → "AI 正在整理 N 篇笔记..."
  │              │   complete   → "整理完成！"
  │              │   error      → 显示错误 + [重试] 按钮
  │              │
  │              └─ 完成时
  │                   ├─ 显示 [查看成果笔记] 按钮
  │                   └─ 点击 → router.push(`/notes/${note_id}`)
  │
  └─ 异常处理
       ├─ 用户关闭弹窗 → 断开 WS（任务继续后台执行）
       └─ WS 断连 → 提示"连接中断，请刷新查看结果"
```

**整理方式 placeholder**:
```
请描述整理方式，如：
· 合并为一篇结构化笔记
· 提取核心要点生成摘要
· 对比分析各笔记异同
· 基于笔记内容进行知识扩展
```

### 5.2 useOrganizeProgress Hook

```typescript
// hooks/useOrganizeProgress.ts

function useOrganizeProgress(taskId: string | null) {
  const [progress, setProgress] = useState<OrganizeProgress | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    if (!taskId) return;

    const token = getAccessToken();
    const ws = new WebSocket(
      `ws://${API_HOST}/ws/organize-progress/${taskId}?token=${token}`
    );

    ws.onopen = () => setIsConnected(true);
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setProgress(data);
      if (data.stage === "complete" || data.stage === "error") {
        ws.close();
      }
    };
    ws.onclose = () => setIsConnected(false);

    return () => ws.close();
  }, [taskId]);

  return { progress, isConnected };
}
```

### 5.3 AI 修改笔记 — 前端集成

当用户在 Agent 对话中请求修改笔记时，`edit_note` 工具会被调用，编辑结果通过 `/ws/notifications` 推送到前端：

```
用户在 Agent 对话框输入:
  "帮我把笔记第 3 行改为 xxx"
        │
        ▼
Agent 调用 edit_note(note_id, operation="replace", start_line=3, ...)
        │
        ▼
后端修改数据库 → WS 推送 note_edit 到 /ws/notifications
        │
        ▼
前端 useNotificationWS 收到 note_edit 消息
        │
        ├─ note_id 匹配当前打开的笔记？
        │    YES → 执行以下操作
        │    NO  → 忽略
        │
        ├─ 1. editor.commands.setContent(data.new_content)
        ├─ 2. 更新 noteStore 中的 content 和 word_count
        ├─ 3. Toast: "AI 已修改此笔记（Ctrl+Z 可撤销）"
        └─ 4. sync_status ← "ai_modified"
```

**useNotificationWS 扩展**:
```typescript
// 在现有消息处理中新增:
case "note_edit":
  const editData = message.data;
  const currentNoteId = useNoteStore.getState().currentNote?.id;
  if (editData.note_id === currentNoteId) {
    useNoteStore.getState().applyAiEdit(editData);
    toast.info("AI 已修改此笔记（Ctrl+Z 可撤销）");
  }
  break;
```

**noteStore.applyAiEdit**:
```typescript
applyAiEdit: (editData: NoteEditNotification["data"]) => {
  set((state) => ({
    currentNote: state.currentNote
      ? {
          ...state.currentNote,
          content: editData.new_content,
          word_count: editData.word_count,
        }
      : null,
    syncStatus: "ai_modified",
  }));
}
```

**NoteEditorPage 集成**:
```typescript
// 监听 noteStore 变化，当 syncStatus === "ai_modified" 时:
useEffect(() => {
  if (syncStatus === "ai_modified" && editor && currentNote) {
    editor.commands.setContent(currentNote.content);
    setSyncStatus("saved");
  }
}, [syncStatus]);
```

### 5.4 ToolCallDisplay — edit_note 展示卡片

在 Agent 工具调用展示组件中新增 edit_note 的专属卡片：

```
┌─────────────────────────────────────────┐
│  ✏️  编辑笔记「{note_title}」             │
│  ─────────────────────────────────────  │
│  insert:  在第 {start_line} 行前插入     │
│  replace: 替换第 {start_line}~{end_line} 行 │
│  delete:  删除第 {start_line}~{end_line} 行 │
│  ─────────────────────────────────────  │
│  内容预览: {content_preview}             │
│  ✅ 修改成功                             │
└─────────────────────────────────────────┘
```

---

## 6. API 调用封装

```typescript
// api/notes.ts — 新增方法

/** AI 整理笔记 */
organizeNotes: (data: OrganizeNotesRequest) =>
  api.post<OrganizeNotesResponse>("/notes/organize", data),
```

无需额外封装 WebSocket（由 Hook 处理）和通知 WS（复用现有）。

---

## 7. 验收检查清单

### AI 整理笔记
- [ ] 笔记列表多选模式下「AI 整理」按钮可见
- [ ] 选中 0 篇时按钮禁用
- [ ] 选中 21 篇时提示"最多选择 20 篇"
- [ ] 弹窗中输入整理方式，提交后显示进度条
- [ ] 进度条正确显示 10% → 30% → 100%
- [ ] 完成后自动提示跳转成果笔记
- [ ] 成果笔记在列表中显示，带有 `ai_organized` 标识
- [ ] 关闭弹窗后任务继续后台执行（不报错）
- [ ] 网络异常时显示合理错误提示

### AI 修改笔记
- [ ] Agent 对话中请求修改笔记，能正确触发 `edit_note`
- [ ] 当前打开的笔记收到 `note_edit` 消息后实时更新
- [ ] Ctrl+Z 可撤销 AI 修改
- [ ] 修改后字数正确更新
- [ ] 非当前笔记的 `note_edit` 消息不干扰编辑器
- [ ] ToolCallDisplay 正确展示 edit_note 调用详情

---

## 8. 附录: TypeScript 类型汇总

```typescript
// === 请求/响应类型 ===

interface OrganizeNotesRequest {
  note_ids: string[];
  prompt: string;
}

interface OrganizeNotesResponse {
  task_id: string;
  message: string;
}

// === WebSocket 消息类型 ===

interface OrganizeProgress {
  stage: "preparing" | "generating" | "complete" | "error";
  percent: number;
  message: string;
  note_id?: string;
  title?: string;
  word_count?: number;
  source_count?: number;
  error?: string;
}

interface NoteEditNotification {
  type: "note_edit";
  data: {
    note_id: string;
    operation: "insert" | "replace" | "delete";
    start_line: number;
    end_line: number | null;
    content: string;
    new_content: string;
    title: string;
    word_count: number;
  };
}

// === 数据模型扩展 ===

interface Note {
  // ... 现有字段 ...
  origin_type: "user" | "ai_organized";
  source_note_ids: string[] | null;
}
```
