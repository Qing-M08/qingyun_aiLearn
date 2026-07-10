# 青云智学 前端技术架构文档

> 版本: 0.2.0 | 更新日期: 2026-07-10 | 维护者: 前端团队

---

## 一、项目概述

**青云智学** 是一款 AI 驱动的智能学习平台，支持个性化学习路线生成、AI 讲义讲解、智能问答、间隔重复复习等核心功能。前端基于 React SPA 架构，通过 Tauri 2.0 壳打包为桌面应用。

- **应用标识**: `com.qingyun.ailearn`
- **产品名称**: 青云智学
- **默认窗口**: 1280×800（最小 900×600）

---

## 二、技术栈总览

### 核心框架

| 类别 | 技术选型 | 版本 | 用途 |
|------|---------|------|------|
| 框架 | React | ^18.3 | UI 组件化渲染 |
| 构建工具 | Vite | ^6.3 | 开发服务器 & 生产构建 |
| 类型系统 | TypeScript | ^5.9 | 静态类型检查 |
| 语言标准 | ES2020 | — | 编译目标 |

### UI & 样式

| 类别 | 技术选型 | 版本 | 用途 |
|------|---------|------|------|
| 组件库 | Ant Design | ^5.29 | 通用 UI 组件（表单、表格、弹窗等） |
| 富文本编辑器 | Tiptap | ^3.27 | WYSIWYG Markdown 编辑器 |
| Markdown 渲染 | react-markdown | ^9.1 | 文档渲染 |
| 代码高亮 | lowlight | ^3.3 | Tiptap 代码块语法高亮 |
| 数学公式 | KaTeX | ^0.16 | LaTeX 公式渲染 |
| 数据可视化 | Recharts | ^2.15 | Dashboard 图表 |
| 流程图 | ReactFlow | ^11.11 | 学习路线图可视化 |
| 动效 | Framer Motion | ^11.18 | 过渡动画 |

### 状态管理 & 数据

| 类别 | 技术选型 | 版本 | 用途 |
|------|---------|------|------|
| 全局状态 | Zustand | ^5.0 | 跨组件状态管理 |
| 服务端状态 | TanStack React Query | ^5.101 | API 缓存 & 自动刷新 |
| 路由 | React Router DOM | ^6.30 | 客户端路由（BrowserRouter） |

### 网络通信

| 类别 | 技术选型 | 版本 | 用途 |
|------|---------|------|------|
| HTTP 客户端 | Axios | ^1.18 | RESTful API 调用 |
| WebSocket | 原生 WebSocket | — | 流式数据推送（讲义生成、QA 流式回复） |

### 桌面壳

| 类别 | 技术选型 | 版本 | 用途 |
|------|---------|------|------|
| 桌面框架 | Tauri | ^2.11 | 原生桌面窗口壳 |
| Rust 后端 | Serde | 1.0 | 本地存储序列化 |

### 工具链

| 类别 | 技术选型 | 版本 | 用途 |
|------|---------|------|------|
| Linter | ESLint | ^9.39 | 代码规范检查 |
| 格式化 | Prettier | ^3.9 | 代码格式化 |
| 日期处理 | dayjs | ^1.11 | 日期格式化 |
| 工具库 | Lodash | ^4.17 | 常用工具函数 |

---

## 三、项目目录结构

```
forend/
├── index.html                    # HTML 入口
├── .env.development              # 开发环境变量
├── vite.config.ts                # Vite 构建配置
├── eslint.config.js              # ESLint 配置
├── tsconfig.json                 # TS 配置（引用多个子配置）
├── tsconfig.app.json             # 应用 TS 编译配置
├── tsconfig.node.json            # Node 端 TS 配置
├── src-tauri/                    # Tauri 桌面壳（Rust）
│   ├── tauri.conf.json           # Tauri 应用配置
│   ├── Cargo.toml                # Rust 依赖
│   └── src/
│       ├── lib.rs                # Tauri 插件注册
│       └── main.rs               # Rust 入口
└── src/                          # 前端源码
    ├── main.tsx                  # React 挂载入口
    ├── App.tsx                   # 根组件（路由 + 全局 Provider）
    ├── App.css                   # 全局样式（1681 行 CSS）
    ├── index.css                 # CSS 变量 & Reset
    ├── api/                      # API 调用层
    │   ├── client.ts             # Axios 实例 + 拦截器
    │   ├── auth.ts               # 认证 API
    │   ├── learning.ts           # 学习 API
    │   ├── notes.ts              # 笔记 API
    │   ├── review.ts             # 复习 API
    │   └── search.ts             # 搜索 API
    ├── types/                    # TypeScript 类型定义
    │   ├── auth.ts               # 认证类型
    │   ├── user.ts               # 用户类型
    │   ├── learning.ts           # 学习模块类型
    │   ├── note.ts               # 笔记类型
    │   ├── review.ts             # 复习类型
    │   ├── search.ts             # 搜索类型
    │   ├── common.ts             # 通用类型（分页、API 响应）
    │   └── websocket.ts          # WebSocket 消息类型
    ├── stores/                   # Zustand 状态管理
    │   ├── authStore.ts          # 认证状态
    │   ├── uiStore.ts            # UI 状态（侧栏、主题）
    │   ├── learningStore.ts      # 学习模块状态
    │   ├── noteStore.ts          # 笔记状态
    │   └── reviewStore.ts        # 复习状态
    ├── hooks/                    # 自定义 Hooks
    │   ├── useWebSocket.ts       # WebSocket 连接管理
    │   └── useNotificationWS.ts  # 通知 WebSocket
    ├── components/               # 可复用组件
    │   ├── chat/                 # 聊天/AI 对话
    │   │   ├── ChatPanel.tsx     # AI 对话面板
    │   │   ├── MessageBubble.tsx # 消息气泡
    │   │   └── StreamingText.tsx # 流式文本渲染
    │   ├── common/               # 通用组件
    │   │   ├── EmptyState.tsx    # 空状态
    │   │   ├── ErrorBoundary.tsx # 错误边界
    │   │   └── LoadingOverlay.tsx # 加载遮罩
    │   ├── editor/               # 编辑器
    │   │   ├── MarkdownEditor.tsx # Tiptap 编辑器
    │   │   ├── MarkdownPreview.tsx # Markdown 预览
    │   │   ├── EditorPreview.tsx # 编辑器预览
    │   │   └── TagToolbar.tsx    # 标签工具栏
    │   ├── learning/             # 学习相关
    │   │   ├── RouteTimeline.tsx # 路线时间轴
    │   │   ├── StepDetailPanel.tsx # 步骤详情面板
    │   │   └── StepNode.tsx      # 步骤节点
    │   └── review/               # 复习相关
    │       ├── ReviewCard.tsx    # 复习卡片
    │       ├── QuizCard.tsx      # 选择题卡片
    │       ├── MasteryBar.tsx    # 掌握度进度条
    │       └── ReviewStatsCards.tsx # 复习统计卡片
    ├── pages/                    # 页面组件
    │   ├── auth/                 # 认证页面
    │   │   ├── LoginPage.tsx
    │   │   └── RegisterPage.tsx
    │   ├── dashboard/            # 首页仪表盘
    │   │   └── DashboardPage.tsx
    │   ├── learning/             # 学习页面
    │   │   ├── LearningRoutesPage.tsx   # 路线列表
    │   │   ├── LearningRoutePage.tsx    # 路线详情
    │   │   ├── LecturePage.tsx          # AI 讲义
    │   │   ├── PersonalizedDocPage.tsx  # 个性化文档
    │   │   └── QAPage.tsx              # AI 问答
    │   ├── notes/                # 笔记页面
    │   │   ├── NotesListPage.tsx  # 笔记列表
    │   │   ├── NoteEditorPage.tsx # 笔记编辑器
    │   │   └── TagIndexPage.tsx   # 标签索引
    │   └── review/               # 复习页面
    │       ├── ReviewListPage.tsx    # 待复习列表
    │       └── ReviewSessionPage.tsx # 复习会话
    └── utils/                    # 工具函数
        ├── format.ts             # 格式化工具
        ├── markdown.ts           # Markdown 处理
        └── tauriNotification.ts # Tauri 通知
```

---

## 四、架构分层

```
┌─────────────────────────────────────────────────────┐
│                    页面层 (Pages)                      │
│  Login / Dashboard / Learning / Notes / Review       │
├─────────────────────────────────────────────────────┤
│                   组件层 (Components)                  │
│  Chat / Editor / Learning / Review / Common          │
├─────────────────────────────────────────────────────┤
│               状态管理层 (Stores + React Query)        │
│    Zustand Stores (5 个)    │   TanStack Query       │
├──────────────────────┬──────────────────────────────┤
│   HTTP (Axios)       │     WebSocket                │
│   api/               │     hooks/useWebSocket       │
├──────────────────────┴──────────────────────────────┤
│                    后端 API (/api/v1)                 │
│              Python FastAPI (127.0.0.1:8000)         │
└─────────────────────────────────────────────────────┘
```

---

## 五、路由设计

### 路由表

| 路径 | 页面 | 权限 | 说明 |
|------|------|------|------|
| `/login` | LoginPage | 公开（已登录重定向到 /） | 登录页 |
| `/register` | RegisterPage | 公开 | 注册页 |
| `/` | DashboardPage | 需登录 | 首页仪表盘 |
| `/notes` | NotesListPage | 需登录 | 笔记列表 |
| `/notes/new` | NoteEditorPage | 需登录 | 新建笔记 |
| `/notes/:id` | NoteEditorPage | 需登录 | 编辑笔记 |
| `/notes/tags/:id` | TagIndexPage | 需登录 | 标签索引 |
| `/learning` | LearningRoutesPage | 需登录 | 学习路线列表 |
| `/learning/route/:id` | LearningRoutePage | 需登录 | 路线详情 |
| `/learning/lecture/:id` | LecturePage | 需登录 | AI 讲义 |
| `/learning/summary/:id` | PersonalizedDocPage | 需登录 | 个性化文档 |
| `/learning/qa/:id` | QAPage | 需登录 | AI 问答 |
| `/review` | ReviewListPage | 需登录 | 待复习列表 |
| `/review/:id` | ReviewSessionPage | 需登录 | 复习会话 |
| `*` | — | — | 重定向到 `/` |

### 路由守卫

```
AuthRedirect（已登录 → 重定向到 /）
  ├── /login
  └── /register

ProtectedRoute（未登录 → 重定向到 /login）
  └── MainLayout（侧栏 + 顶栏布局）
      ├── /                    → DashboardPage
      ├── /notes               → NotesListPage
      ├── /notes/new           → NoteEditorPage
      ├── /notes/:id           → NoteEditorPage
      ├── /notes/tags/:id      → TagIndexPage
      ├── /learning            → LearningRoutesPage
      ├── /learning/route/:id  → LearningRoutePage
      ├── /learning/lecture/:id → LecturePage
      ├── /learning/summary/:id → PersonalizedDocPage
      ├── /learning/qa/:id     → QAPage
      ├── /review              → ReviewListPage
      └── /review/:id          → ReviewSessionPage
```

### 全局 Provider 嵌套

```
StrictMode
  └── QueryClientProvider (TanStack Query)
      └── ConfigProvider (Ant Design 主题)
          └── BrowserRouter
              └── Routes
```

---

## 六、状态管理

### Zustand Stores

| Store | 文件 | 核心职责 |
|-------|------|---------|
| `useAuthStore` | `stores/authStore.ts` | 用户认证、Token 管理、Dev 模式、Tauri 离线存储 |
| `useUIStore` | `stores/uiStore.ts` | 侧栏折叠、主题切换、模态框状态 |
| `useLearningStore` | `stores/learningStore.ts` | 学习路线、讲义生成、QA 会话、流式消息 |
| `useNoteStore` | `stores/noteStore.ts` | 笔记 CRUD、标签管理 |
| `useReviewStore` | `stores/reviewStore.ts` | 复习计划、会话状态、统计 |

### 认证状态 (authStore)

```
authStore
├── user: User | null           # 用户信息
├── accessToken: string | null  # JWT 访问令牌
├── refreshToken: string | null # 刷新令牌
├── isAuthenticated: boolean    # 认证状态
├── isDevMode: boolean          # 开发者模式（假 token）
├── isLoading: boolean          # 加载态
├── login()                     # 邮箱密码登录
├── register()                  # 注册
├── devLogin()                  # 开发者一键登录
├── logout()                    # 登出
├── refreshTokenAction()        # Token 刷新
└── loadFromStorage()           # Tauri 离线恢复
```

### TanStack React Query

```ts
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,           // 失败重试 2 次
      staleTime: 5 * 60 * 1000, // 5 分钟内视为新鲜
    },
  },
});
```

---

## 七、网络通信

### 7.1 HTTP 客户端 (Axios)

**API 基地址**: `VITE_API_BASE_URL` 或默认 `/api/v1`（开发环境经 Vite 代理到 `http://127.0.0.1:8000`）

**请求拦截器**:
1. 自动附加 `Authorization: Bearer <token>`

**响应拦截器**:
1. 401 错误 → 自动尝试刷新 Token
2. 刷新失败 → 清除登录状态，跳转登录页
3. 开发者模式 → 跳过 Token 刷新（假 token 不被后端识别）

**超时配置**: 30 秒

### 7.2 WebSocket 连接

**连接策略**: 优先直连后端（绕过 Vite 代理，因 WS 代理不可靠）

**地址解析优先级**:
1. `VITE_WS_TARGET` 环境变量 → `ws://127.0.0.1:8000`
2. 从 `VITE_API_BASE_URL` 推导
3. 回退到 `window.location`（依赖 Vite 代理）

**特性**:
- 自动重连（指数退避，最多 5 次，最大延迟 30s）
- 心跳保活（30s 间隔发送 `ping`，接收 `pong`）
- Token 认证（通过 URL query 传递）
- Ref 模式避免闭包陈旧值

**消息类型 (WSMessage)**:

```ts
type WSMessage =
  | { type: 'progress'; data: { stage: string; percent: number } }     // 生成进度
  | { type: 'complete'; data: { lecture: Lecture } }                   // 讲义生成完成
  | { type: 'token'; data: { content: string } }                       // 流式 Token
  | { type: 'done'; data: { message: QAMessage } }                     // 流式完成
  | { type: 'diagnosis'; data: DiagnosisResult }                       // AI 诊断
  | { type: 'error'; data: { message: string } }                       // 错误
  | { type: 'review_reminder'; data: { plan: ReviewPlan } }            // 复习提醒
  | { type: 'task_complete'; data: { task_type: string; result: unknown } } // 任务完成
```

---

## 八、模块详解

### 8.1 认证模块

**页面**: `LoginPage`, `RegisterPage`

**流程**:
1. 用户输入凭证 → `authStore.login()` → `authAPI.login()`
2. 后端返回 `{ user, access_token, refresh_token }` → 存入 store
3. Tauri 环境自动持久化到本地存储
4. 开发者模式: `devLogin()` 使用假 token 跳过后端验证
5. App 启动: `loadFromStorage()` 从 Tauri 本地存储恢复登录态

**API 响应兼容**: Store 层统一处理 `{ data: {...} }` 和 `{...}` 两种格式

### 8.2 笔记模块

**页面**: `NotesListPage`, `NoteEditorPage`, `TagIndexPage`

#### 8.2.1 编辑器三模式架构 (`NoteEditorPage`)

笔记编辑器支持三种视图模式，用户通过顶部工具栏切换：

| 模式 | 标识 | 渲染引擎 | 说明 |
|------|------|---------|------|
| 所见即所得 | `wysiwyg` | Tiptap (`MarkdownEditor`) | 富文本编辑，实时渲染 Markdown 语法 |
| 源码 | `edit` | `<textarea>` | 原始 Markdown 文本编辑 |
| 预览 | `preview` | `react-markdown` (`MarkdownPreview`) | 只读 Markdown 渲染（含 KaTeX 公式） |

```
┌──────────────────────────────────────────────────────────┐
│                      Menubar                             │
│  [←返回] [标题输入] [同步状态图标] [wysiwyg|源码|预览] [保存] │
├─────────────────────┬────────────────────────────────────┤
│   AI 问答面板       │         编辑器主体                  │
│   (ChatPanel)       │   ┌──────────────────────────┐     │
│   ~40% 宽度          │   │  模式切换按钮组            │     │
│                    │   ├──────────────────────────┤     │
│   - 上下文标签      │   │                          │     │
│   - 消息列表        │   │  wysiwyg: Tiptap 编辑器   │     │
│   - 输入区域        │   │  edit:    Markdown 源码   │     │
│                    │   │  preview: 渲染预览         │     │
│                    │   │                          │     │
│                    │   ├──────────────────────────┤     │
│                    │   │  状态栏（字数 · 同步状态）  │     │
│                    │   └──────────────────────────┘     │
├─────────────────────┴────────────────────────────────────┤
│              离线提示条（仅 localStorage 模式显示）         │
└──────────────────────────────────────────────────────────┘
         ↕ 可拖拽分隔线
```

#### 8.2.2 离线持久化机制

浏览器 localStorage 离线容灾方案：

- **存储键**: `qingyun_note_{noteId}`（新建笔记使用 `qingyun_note_new`）
- **自动保存**: 内容变化后 2 秒防抖自动写入 localStorage
- **同步状态机**:

```
saved ──(内容变更)──→ unsaved ──(2s 自动保存)──→ local
  ↑                                               │
  └──────────(手动保存成功，清除 local)──────────────┘

local ──(手动保存成功)──→ saved
local ──(手动保存失败)──→ local（保留本地副本）
```

| 状态 | 图标 | 含义 |
|------|------|------|
| `saved` | 🟢 CloudOutlined | 已同步到服务器 |
| `local` | 🟡 CloudSyncOutlined | 保存到本地，待同步 |
| `unsaved` | ⚪ 未保存 | 内存中有未持久化的修改 |

- **网络监听**: `window.addEventListener('online'/'offline')` 检测连接状态，离线时自动降级为本地存储
- **恢复策略**:
  - 页面加载优先从 API 获取笔记
  - API 失败时回退 localStorage 读取
  - 新建笔记时检查是否有未同步的本地草稿

#### 8.2.3 AI 问答集成

笔记编辑器左侧集成 AI 问答面板：

- **会话创建**: 笔记加载完成后自动调用 `learningAPI.createQASession()`
- **上下文绑定**: 笔记标题作为 `contextInfo.lectureTitle` 传递给 `ChatPanel`
- **状态处理**:
  - 新建笔记 (`id === 'new'`): 提示"保存笔记后即可使用 AI 问答"
  - 会话创建失败: 显示错误提示和重试按钮
  - 会话就绪: 渲染完整对话界面
- **防重复**: `sessionInitialized` ref 确保每个笔记仅创建一次 QA 会话

#### 8.2.4 Tiptap 编辑器关键配置 (`MarkdownEditor`)

**扩展列表**:
- `@tiptap/starter-kit` — 基础编辑能力（标题、列表、加粗、斜体、引用等）
- `@tiptap/extension-code-block-lowlight` — 代码块语法高亮（lowlight v3：`createLowlight(common)`）
- `@tiptap/extension-highlight` — 文本高亮标记
- `@tiptap/markdown` — Markdown ↔ JSON 双向转换

**关键配置**:

```ts
const editor = useEditor({
  // ⚠️ 必须显式设置 contentType: 'markdown'，否则 markdown 字符串以纯文本渲染
  contentType: contentJson ? undefined : (content ? 'markdown' : undefined),
  content: contentJson || content,

  // 自定义粘贴处理：自动解析粘贴的 markdown 语法
  editorProps: {
    handlePaste: (view, event) => {
      // 检测粘贴文本是否包含 markdown 语法特征（#标题、列表、代码等）
      // 是 → 用 markdownManager.parse() 解析后 insertContent
      // 否 → 走默认粘贴行为（纯文本）
    },
  },

  onUpdate: ({ editor }) => {
    // ⚠️ getMarkdown() 挂载在 editor 实例上，非 editor.storage.markdown
    const md = (editor as any).getMarkdown?.();
    debouncedOnChange(md, editor.getJSON());
  },
});
```

**外部内容同步**: 使用 `isInternalChange` ref 区分变更来源，通过 `useEffect([content])` 同步外部 prop 变更，避免反馈循环。

**已知陷阱**:

| 陷阱 | 症状 | 正确做法 |
|------|------|---------|
| 未设 `contentType: 'markdown'` | `## 标题` 显示为纯文本，换行错误 | 传入 markdown 字符串时必须显式声明 |
| `editor.storage.markdown.getMarkdown()` | `is not a function` 运行时错误 | 使用 `(editor as any).getMarkdown?.()` |
| `content` prop 变更不同步 | API 加载内容后编辑器空白 | `useEffect` + `isInternalChange` ref 同步 |
| lowlight 直接传 `common` | 代码块高亮报错 | v3.x 必须用 `createLowlight(common)` |
| 粘贴 markdown 不解析 | 粘贴 `## 标题` 显示为纯文本 | `handlePaste` 中调用 `markdownManager.parse()` |

**API 响应兼容**: 支持裸数组、`{ items, total }` 分页、`{ data: { items, total } }` 三种格式

### 8.3 学习模块

**页面**: `LearningRoutesPage`, `LearningRoutePage`, `LecturePage`, `QAPage`, `PersonalizedDocPage`

**核心流程**:

```
用户输入主题 → 生成路线 (generateRoute)
  → WebSocket 进度推送 (progress)
    → 路线步骤 (RouteStep[])
      → 选择步骤 → 生成讲义 (generateLecture)
        → WebSocket 进度推送 (progress)
          → 讲义内容 (complete)
            → AI 问答 (createQASession → sendQAMessage)
              → WebSocket 流式回复 (token → done)
                → AI 诊断 (diagnosis)
```

**路线视图模式**: `timeline` | `graph` | `list`

**步骤状态**: `pending` | `in_progress` | `completed`

### 8.4 复习模块

**页面**: `ReviewListPage`, `ReviewSessionPage`

**复习内容类型**:
- `flashcard` — 闪卡（正面问题 / 背面答案 / 提示）
- `quiz` — 选择题（题目 / 选项 / 正确答案 / 解析）
- `explanation` — 讲解（标题 / 内容 / 要点）

**会话状态机**:
```
initSession → 加载内容 → 展示 → 作答 → 自评 → completeCurrentPlan
                                                      ↓
                                            advanceToNextPlan → 加载内容 → ...
```

**掌握度分布**:
```
not_started → learning → familiar → mastered
```

### 8.5 Dashboard 模块

**页面**: `DashboardPage`

**内容**:
- 欢迎区（用户名、日期）
- 统计卡片（学习天数、笔记数、待复习数）
- 学习进度环形图（Recharts）
- 最近笔记列表
- 待复习列表
- 可用学习路线
- 快捷操作（新建笔记、生成路线）

---

## 九、样式体系

### 9.1 设计令牌 (CSS Variables)

项目使用 CSS 自定义属性实现设计令牌系统，支持亮色/暗色主题切换。

**主题切换**: 通过 `data-theme="dark"` 属性覆盖 CSS 变量值

**核心颜色**:
- 主色: `#F59E0B`（琥珀色/金色）
- 文字: 三级层次 (`primary` / `secondary` / `tertiary`)
- 背景: 四级层次 (`app` / `page` / `card` / `elevated`)

**字体**:
- 正文: `-apple-system, "Noto Sans SC", "PingFang SC", "Microsoft YaHei"`
- 等宽: `"JetBrains Mono", "Fira Code", "SF Mono", Menlo`

### 9.2 布局尺寸

| 变量 | 值 | 说明 |
|------|-----|------|
| `--sidebar-w` | 220px | 侧栏展开宽度 |
| `--sidebar-collapsed` | 56px | 侧栏折叠宽度 |
| `--topbar-h` | 52px | 顶栏高度 |

### 9.3 样式组织

- `index.css` — CSS 变量定义 / Reset / 布局基础
- `App.css` — 所有业务样式（按区块 BEM 组织，1681 行）
- Ant Design 主题: 通过 `ConfigProvider` 注入 `colorPrimary` 等 token

---

## 十、构建与部署

### 10.1 开发环境

```bash
# 安装依赖
npm install

# 启动 Vite 开发服务器（端口 5173）
npm run dev

# 代码检查
npm run lint

# 构建生产版本
npm run build

# 预览生产构建
npm run preview
```

### 10.2 Vite 配置

- **代理**: `/api/v1` → `http://127.0.0.1:8000`（支持 WebSocket）
- **WebSocket**: 通过 `VITE_WS_TARGET` 直连后端，绕过代理
- **插件**: `@vitejs/plugin-react`

### 10.3 Tauri 构建

```bash
# 安装 Tauri CLI
npm install -g @tauri-apps/cli

# 开发模式（启动 Vite + Tauri 窗口）
cargo tauri dev

# 生产构建
cargo tauri build
```

**Tauri 能力**: 离线数据存储 (`save_offline_data` / `get_offline_data`)

### 10.4 TypeScript 编译

- 目标: ES2020
- 模块: ESNext (bundler 模式)
- JSX: `react-jsx`
- 严格模式: 启用（含 `noUnusedLocals`, `noUnusedParameters`）
- 类型检查: `tsc -b` 作为构建前置步骤

---

## 十一、关键设计决策

### 11.1 API 响应格式兼容层

后端存在多种响应格式，Store 层统一处理：

| 格式 | 示例 | 处理方式 |
|------|------|---------|
| 直接对象 | `{ id, title, ... }` | 直接使用 |
| ApiResponse 包装 | `{ data: { id, title, ... } }` | 解包 `data` |
| 裸数组 | `[...]` | 转为 `{ items, total }` |
| PaginatedResponse | `{ items, total, page, page_size }` | 直接使用 |
| 嵌套 ApiResponse | `{ data: { items, total } }` | 解包 `data` |

### 11.2 开发者模式

- 通过 `devLogin()` 一键登录，使用假 token (`dev-token`)
- WebSocket/API 401 时跳过 Token 刷新，避免无限循环
- 仅限开发环境使用

### 11.3 WebSocket 直连策略

Vite 开发服务器的 WebSocket 代理不可靠，因此 WebSocket 连接绕过代理直连后端：
- 通过环境变量 `VITE_WS_TARGET` 指定地址
- 自动从 `VITE_API_BASE_URL` 推导 ws/wss 协议
- 心跳机制保持连接活跃

### 11.4 流式消息处理

- WebSocket 接收 `token` 类型消息，追加到流式消息内容
- `done` 类型消息将流式消息固化为完整消息
- 使用 Store 状态管理流式消息列表

---

## 十二、类型系统

### 核心类型定义位置

| 文件 | 类型 |
|------|------|
| `types/user.ts` | `User`, `UserProfile`, `MasterySummary` |
| `types/auth.ts` | `LoginRequest`, `RegisterRequest`, `AuthResponse` |
| `types/learning.ts` | `LearningRoute`, `RouteStep`, `Lecture`, `QASession`, `QAMessage`, `DisplayMessage`, `DiagnosisResult` |
| `types/note.ts` | `Note`, `NoteTag`, `Tag`, `TagSelection` |
| `types/review.ts` | `ReviewPlan`, `ReviewStats`, `ReviewSessionState`, `FlashcardContent`, `QuizContent`, `ExplanationContent` |
| `types/common.ts` | `PaginatedResponse<T>`, `ApiResponse<T>`, `ApiError` |
| `types/websocket.ts` | `WSMessage`（联合类型） |
| `types/search.ts` | `SearchResult` |

---

## 十三、开发规范

### 命名约定

- **组件文件**: PascalCase（`ChatPanel.tsx`）
- **工具文件**: camelCase（`useWebSocket.ts`）
- **样式类名**: BEM + kebab-case（`.chat-panel__messages`）
- **Zustand Store**: `useXxxStore`
- **API 模块**: `xxxAPI`
- **类型文件**: 与对应模块同名（`learning.ts`）

### 文件组织原则

- API 层：按业务域拆分 (`auth`, `learning`, `notes`, `review`, `search`)
- Store 层：每个业务域一个 store
- 组件：按功能域分目录 (`chat/`, `editor/`, `learning/`, `review/`, `common/`)
- 页面：按路由域分目录 (`auth/`, `dashboard/`, `learning/`, `notes/`, `review/`)

### 错误处理

- 全局: `ErrorBoundary` 组件捕获渲染崩溃
- API: Axios 拦截器处理 401 自动刷新
- 业务: Store 层 try-catch 处理 API 错误

---

## 附录 A: 依赖清单

### 生产依赖

```
react, react-dom              # UI 框架
antd                          # UI 组件库
@tanstack/react-query         # 服务端状态管理
zustand                       # 客户端状态管理
react-router-dom              # 路由
axios                         # HTTP 客户端
dayjs                         # 日期处理
lodash                        # 工具库
framer-motion                 # 动效
recharts                      # 图表
reactflow                     # 流程图
react-markdown, remark-gfm    # Markdown 渲染
katex                         # LaTeX 公式
@tiptap/react, @tiptap/starter-kit, @tiptap/markdown, @tiptap/extension-code-block-lowlight, @tiptap/extension-highlight  # 富文本编辑器
lowlight                      # 代码语法高亮
@tauri-apps/api               # Tauri 桌面 API
```

### 开发依赖

```
vite, @vitejs/plugin-react    # 构建工具
typescript                    # 类型系统
eslint, @eslint/js, typescript-eslint, eslint-plugin-react-hooks, eslint-plugin-react-refresh  # 代码检查
prettier                      # 代码格式化
@tauri-apps/cli               # Tauri CLI
@types/react, @types/react-dom, @types/lodash, @types/katex  # 类型声明
```
