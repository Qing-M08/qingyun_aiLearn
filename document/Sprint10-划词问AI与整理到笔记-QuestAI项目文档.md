# Sprint 10 — 笔记划词问 AI · 整理到笔记 · Markdown 标签跳转

> **Sprint 编号**：10  
> **版本**：0.5.0  
> **前置 Sprint**：Sprint 9（AI 整理笔记 + Agent 工具增强 + 生产部署）  
> **预计工期**：3 ~ 4 天

---

## 一、Sprint 概述

本 Sprint 围绕笔记编辑器的 AI 交互增强和 Markdown 语法扩展，交付三项功能：

1. **划词问 AI**：用户在 Tiptap 编辑器中划词，通过 BubbleMenu 浮动工具栏点击"问 AI"，可输入额外提示词（默认"请解释"），选中内容经 Agent 通道处理后，回复流式展示在笔记页左侧 ChatPanel 中。
2. **整理到笔记**：ChatPanel 中每次 AI 回复后附带"整理到笔记"按钮。点击后，后端自动创建一个隐藏 Agent 会话，该会话读取笔记全文 + AI 回复内容，自主决定插入位置，调用增强版 `edit_note` 工具（列级精度）将内容写入笔记。隐藏会话在 Agent 页可见，笔记侧边栏不可见。
3. **Markdown 标签跳转**：支持 `[标签名:具体内容]` 语法（英文 `[]` 与 `:`），两个同名标签组成一对，点击任一个可跳转到配对位置，支持双向跳转。区分大小写，支持中文标签名。强校验：标签必须恰好成对出现，不成对时在编辑器中给出错误提示。纯前端实现，后端无改动。

---

## 二、技术栈

沿用 Sprint 9 技术栈，无新增依赖。

| 组件 | 技术选型 | 与本 Sprint 相关点 |
|------|---------|-------------------|
| Web 框架 | FastAPI ≥0.115 | 新增整理到笔记 API |
| ORM | SQLAlchemy ≥2.0 (async) | agent_sessions 表新增 visibility 字段 |
| 异步任务 | Celery ≥5.4 | 整理到笔记异步执行 |
| 缓存/消息 | Redis 7 | 整理进度推送（Pub/Sub） |
| LLM 服务 | DeepSeek API | Agent 整理笔记时调用 LLM |
| Agent 基础设施 | AgentLoop + ToolRegistry | 复用 ReAct 循环 + 工具系统 |

---

## 三、项目结构变更

```
backend/
├── alembic/versions/
│   └── 20260715_add_agent_visibility.py       # [新增] agent_sessions 新增 visibility 字段
├── app/
│   ├── agent/
│   │   └── prompts/
│   │       ├── agent.py                        # [修改] 无变更，但需了解现有 Prompt
│   │       └── note_organize_agent.py          # [新增] 整理到笔记 Agent 系统 Prompt
│   ├── api/v1/
│   │   ├── agent.py                            # [修改] 新增"整理到笔记"端点
│   │   └── websocket.py                        # [无变更] 复用现有 Agent WS
│   ├── models/
│   │   └── agent_session.py                    # [修改] 新增 visibility 字段
│   ├── schemas/
│   │   └── agent.py                            # [修改] 新增整理请求/响应 Schema
│   ├── services/agent/
│   │   ├── agent_service.py                    # [修改] 新增创建隐藏会话方法
│   │   ├── agent_loop.py                       # [无变更] 复用
│   │   ├── tool_schemas.py                     # [修改] edit_note 扩展列级参数
│   │   ├── tool_registry.py                    # [无变更]
│   │   └── handlers/
│   │       └── note_handler.py                 # [修改] edit_note 实现支持列级操作
│   └── tasks/
│       └── note_tasks.py                       # [修改] 新增整理到笔记 Celery 任务
```

---

## 四、数据库变更

### 4.1 agent_sessions 表新增 visibility 字段

**目的**：区分普通 Agent 会话与系统自动创建的隐藏会话。隐藏会话在 Agent 页面列表中可见（保留记录），但在笔记侧边栏中不可见。

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| visibility | String(20) | `'visible'` | 会话可见性：`visible`（普通）/ `hidden`（隐藏） |

**Alembic 迁移**：`20260715_add_agent_visibility.py`

- `ALTER TABLE agent_sessions ADD COLUMN visibility VARCHAR(20) DEFAULT 'visible'`
- 添加 CHECK 约束：`visibility IN ('visible', 'hidden')`

**影响范围**：

- `AgentSession` ORM 模型新增 `visibility` 字段（默认 `'visible'`）
- 现有查询逻辑无需修改（默认值兼容）
- Agent 会话列表 API 可选增加 `visibility` 筛选参数
- 前端笔记侧边栏过滤时排除 `visibility='hidden'` 的会话

### 4.2 无其他表变更

`agent_messages` 表无需改动，整理到笔记 Agent 的消息正常存入该表。

---

## 五、功能一：划词问 AI（后端部分）

### 5.1 功能概述

用户在笔记编辑器中划词后，前端通过 BubbleMenu 将选中文本 + 额外提示词发送到后端 Agent 通道。后端创建（或复用）一个关联当前笔记的 Agent 会话，通过 Agent WebSocket 流式返回回复。前端将回复展示在左侧 ChatPanel 中。

### 5.2 Agent 会话策略

**会话创建规则**：

- 前端在笔记页加载时，为当前笔记创建一个 Agent 会话（`context_type='note'`, `context_id=note_id`）
- 该会话用于所有划词问 AI 的交互（同一笔记复用同一会话）
- 会话 `visibility='visible'`（在 Agent 页可见）
- 会话标题自动生成为"笔记问答 - {笔记标题}"

**与现有 QA 会话的关系**：

- 笔记页左侧 ChatPanel 当前使用 QA 会话（苏格拉底式答疑）
- 划词问 AI 使用 Agent 会话（更直接的回答风格）
- 两种会话共存于同一个 ChatPanel 中，通过消息来源区分
- QA 会话保持不变（用户手动输入的问题仍走 QA 通道）
- 划词问 AI 的消息走 Agent 通道，回复中附带"整理到笔记"按钮

### 5.3 前端调用流程

1. 前端调用 `POST /api/v1/agent/sessions` 创建/获取笔记关联的 Agent 会话
2. 前端通过 Agent WebSocket（`/ws/agent/{session_id}`）发送消息：

```
WebSocket 客户端 → 服务端:
{
  "type": "message",
  "data": {
    "content": "请解释：选中的文本内容",
    "metadata": {
      "source": "selection",
      "selected_text": "选中的文本内容",
      "prompt": "请解释"
    }
  }
}
```

3. 后端 Agent 处理消息，流式返回回复（复用现有 Agent WS 协议）
4. 前端在 ChatPanel 中渲染回复，底部附带"整理到笔记"按钮

### 5.4 后端无需新增 API

划词问 AI 完全复用现有 Agent 基础设施：

- `POST /api/v1/agent/sessions` — 创建会话
- `WS /api/v1/ws/agent/{session_id}` — 流式对话
- `POST /api/v1/agent/sessions/{id}/messages` — 非流式备用

后端只需确保 Agent Prompt 能正确处理来自划词场景的消息（消息中包含 `metadata.source='selection'`），Agent 系统 Prompt 无需修改（现有 Prompt 已能处理"请解释 xxx"类请求）。

---

## 六、功能二：整理到笔记（后端部分）

### 6.1 功能概述

ChatPanel 中 AI 回复后附带"整理到笔记"按钮。用户点击后：

1. 前端调用新 API 发起整理请求
2. 后端创建一个**隐藏 Agent 会话**（`visibility='hidden'`）
3. 隐藏 Agent 读取笔记全文 + AI 回复内容，自主决定插入位置和编辑操作
4. Agent 调用增强版 `edit_note` 工具（列级精度）写入笔记
5. 编辑操作通过 WebSocket 实时推送到前端，编辑器自动更新

### 6.2 新增 API 端点

#### POST /api/v1/notes/{note_id}/organize-from-chat

**请求**：

```
POST /api/v1/notes/{note_id}/organize-from-chat
Authorization: Bearer <token>
Content-Type: application/json

{
  "ai_reply_content": "AI 回复的完整文本内容",
  "selected_text": "用户最初划词选中的文本（可选）",
  "user_prompt": "请解释"  // 用户最初的提示词（可选）
}
```

**响应**：

```json
{
  "agent_session_id": "uuid",
  "task_id": "celery-task-id",
  "message": "整理任务已提交"
}
```

**行为**：

1. 验证笔记归属当前用户
2. 创建隐藏 Agent 会话：
   - `context_type='note'`
   - `context_id=note_id`
   - `visibility='hidden'`
   - `title='笔记整理 - {笔记标题}'`
3. 提交 Celery 异步任务
4. 返回会话 ID 和任务 ID

#### WS /ws/organize-from-chat/{task_id}

**用途**：推送整理进度（复用 Redis Pub/Sub 模式，与 Sprint 9 整理笔记进度一致）。

**进度阶段**：

| 阶段 | 百分比 | 说明 |
|------|--------|------|
| starting | 5% | 任务启动，创建 Agent 会话 |
| reading_note | 15% | Agent 正在读取笔记内容 |
| analyzing | 30% | Agent 分析回复内容，决定插入位置 |
| editing | 60% | Agent 调用 edit_note 工具写入 |
| complete | 100% | 整理完成 |
| error | - | 整理失败 |

**完成消息**：

```json
{
  "type": "complete",
  "data": {
    "agent_session_id": "uuid",
    "operations_applied": 1,
    "message": "已将内容整理到笔记"
  }
}
```

### 6.3 Schema 定义

```python
# --- 请求 ---
class OrganizeFromChatRequest(BaseModel):
    ai_reply_content: str          # AI 回复的完整内容
    selected_text: str | None = None   # 用户划词选中的文本
    user_prompt: str | None = None     # 用户提示词

# --- 响应 ---
class OrganizeFromChatResponse(BaseModel):
    agent_session_id: uuid.UUID    # 隐藏 Agent 会话 ID
    task_id: str                   # Celery 任务 ID
    message: str

# --- 进度消息（WebSocket） ---
class OrganizeFromChatProgress(BaseModel):
    stage: str                     # starting/reading_note/analyzing/editing/complete/error
    percent: int                   # 0-100
    agent_session_id: str | None = None
    operations_applied: int | None = None
    error_message: str | None = None
```

### 6.4 核心服务实现

#### 6.4.1 AgentService 新增方法

**`create_hidden_session()`**：

- 参数：`user_id`, `context_type`, `context_id`, `title`
- 行为：与 `create_session()` 相同，但设置 `visibility='hidden'`
- 返回：`AgentSession` 对象

**`get_sessions()` 修改**：

- 新增可选参数 `visibility: str | None = None`
- 当 `visibility='visible'` 时，只返回普通会话（笔记侧边栏使用）
- 当 `visibility=None` 时，返回所有会话（Agent 页使用，默认行为不变）

#### 6.4.2 隐藏 Agent 会话的系统 Prompt

文件：`app/agent/prompts/note_organize_agent.py`

```python
NOTE_ORGANIZE_AGENT_SYSTEM_PROMPT = """你是一个笔记整理助手。你的任务是将 AI 回复内容整理到用户的笔记中。

## 当前笔记内容
{note_content}

## 需要整理的内容
AI 回复：{ai_reply_content}
{optional_selected_text}

## 工作规则
1. 阅读笔记全文，理解笔记的结构和主题
2. 分析需要整理的内容，判断它应该插入到笔记的哪个位置
3. 使用 edit_note 工具将内容插入到合适的位置
4. 插入的内容应与笔记现有风格一致（Markdown 格式）
5. 如果内容是解释性的，可以插入到相关概念之后
6. 如果内容是补充性的，可以追加到笔记末尾或相关章节末尾
7. 只调用一次 edit_note 工具完成所有插入（合并为一次操作）

## 输出格式
完成编辑后，简要说明你将内容插入到了哪个位置以及原因。
"""
```

#### 6.4.3 Celery 任务

文件：`app/tasks/note_tasks.py`

**`organize_from_chat_task`**：

```
任务签名：organize_from_chat_task(
    user_id_str: str,
    note_id_str: str,
    agent_session_id_str: str,
    ai_reply_content: str,
    selected_text: str | None,
    user_prompt: str | None
)
```

**执行流程**：

1. 初始化数据库引擎（沿用 Celery 任务中的引擎创建模式）
2. 查询笔记内容（title + content）
3. 构建 Agent 系统 Prompt（注入笔记内容 + AI 回复内容）
4. 构建用户消息：
   - 如果有 `selected_text`：`"请将以下 AI 回复内容整理到笔记中。用户选中的原文是：{selected_text}，AI 的回复是：{ai_reply_content}"`
   - 如果没有：`"请将以下 AI 回复内容整理到笔记中：{ai_reply_content}"`
5. 创建 AgentLoop 实例，绑定隐藏会话
6. 通过 Redis Pub/Sub 推送进度（starting → reading_note → analyzing）
7. 执行 Agent 循环（ReAct 模式，最大 3 轮推理——只需读笔记 + 调用 edit_note）
8. Agent 调用 `edit_note` 工具 → 工具处理器执行实际的笔记编辑
9. 推送进度（editing → complete）
10. 保存 Agent 消息到数据库

**安全控制**：

- `max_steps=3`（整理任务简单，不需要多轮推理）
- `token_budget=8000`（笔记内容可能较长）
- 只允许调用 `get_note_content` 和 `edit_note` 两个工具（通过 AgentLoop 的工具过滤机制）
- `edit_note` 只允许 `insert` 操作（禁止 delete/replace，防止误删用户内容）

**Redis Pub/Sub 跨进程通信**：

- 沿用 Sprint 9 模式：Celery worker 用同步 Redis 发布，FastAPI WebSocket 用 async Redis 订阅
- 频道：`organize_from_chat_progress:{task_id}`

### 6.5 edit_note 工具增强（列级精度）

#### 6.5.1 Schema 变更

现有 `edit_note` 工具参数扩展：

```python
# 现有参数
class EditNoteParams(BaseModel):
    note_id: str
    start_line: int          # 起始行（1-based）
    end_line: int            # 结束行（1-based，含）
    operation: str           # insert / replace / delete
    content: str             # 插入/替换的内容

# 新增参数（可选，向后兼容）
class EditNoteParams(BaseModel):
    note_id: str
    start_line: int          # 起始行（1-based）
    end_line: int            # 结束行（1-based，含）
    start_column: int | None = None   # [新增] 起始列（0-based，字符偏移）
    end_column: int | None = None     # [新增] 结束列（0-based，字符偏移，含）
    operation: str           # insert / replace / delete
    content: str             # 插入/替换的内容
```

**列级操作规则**：

| 操作 | start_column | end_column | 行为 |
|------|-------------|-----------|------|
| insert | 指定 | 忽略 | 在 start_line 的 start_column 位置前插入内容 |
| replace | 指定 | 指定 | 替换从 (start_line, start_column) 到 (end_line, end_column) 的文本 |
| delete | 指定 | 指定 | 删除从 (start_line, start_column) 到 (end_line, end_column) 的文本 |
| insert（行级） | None | None | 在 start_line 行前插入整行内容（向后兼容现有行为） |
| replace（行级） | None | None | 替换 start_line 到 end_line 整行内容（向后兼容） |
| delete（行级） | None | None | 删除 start_line 到 end_line 整行内容（向后兼容） |

**向后兼容**：`start_column` 和 `end_column` 为可选参数，不传时行为与现有行级编辑完全一致。现有 Agent Prompt 和工具调用不受影响。

#### 6.5.2 note_handler 实现变更

`edit_note` 工具处理器的编辑逻辑需要支持列级操作：

**行级模式**（`start_column is None`）：沿用现有逻辑，按行拆分内容，执行整行 insert/replace/delete。

**列级模式**（`start_column is not None`）：

1. 获取笔记全文，按行拆分为列表
2. **insert 操作**：
   - 定位到 `lines[start_line - 1]`
   - 在该行的 `start_column` 位置插入 `content`
   - 如果 `start_column` 超出该行长度，追加到行尾
   - 如果 `start_column` 为 0，在行首插入
3. **replace 操作**：
   - 如果 start_line == end_line：在同一行内替换 `line[start_column:end_column+1]` 为 `content`
   - 如果跨多行：提取起始行 `start_column` 之前的文本 + `content` + 结束行 `end_column+1` 之后的文本，替换 start_line 到 end_line 的所有行
4. **delete 操作**：
   - 如果 start_line == end_line：在同一行内删除 `line[start_column:end_column+1]`
   - 如果跨多行：提取起始行 `start_column` 之前的文本 + 结束行 `end_column+1` 之后的文本，替换 start_line 到 end_line 的所有行
5. 将行列表重新拼接为全文，保存笔记
6. 同步 Meilisearch 索引
7. 通过 WebSocket 推送 `note_edit` 事件到前端

**边界处理**：

- `start_column < 0`：视为 0（行首）
- `start_column > len(line)`：视为 `len(line)`（行尾）
- `end_column > len(line)`：视为 `len(line)`
- `start_line` 或 `end_line` 超出总行数：返回错误

#### 6.5.3 ToolSchema 描述更新

```python
ToolSchema(
    name="edit_note",
    display_name="编辑笔记",
    description="行级或列级笔记编辑。支持 insert（插入）、replace（替换）、delete（删除）。"
                "当提供 start_column 时为列级精度操作，否则为行级操作。"
                "行号从 1 开始，列号从 0 开始。",
    parameters={
        "note_id": "目标笔记 ID",
        "start_line": "起始行号（1-based）",
        "end_line": "结束行号（1-based，含）",
        "start_column": "起始列号（0-based，可选）。指定时为列级操作",
        "end_column": "结束列号（0-based，可选，含）",
        "operation": "操作类型：insert / replace / delete",
        "content": "插入或替换的文本内容（delete 时可为空字符串）"
    },
    category="write",
    module="note",
    icon="edit"
)
```

---

## 七、功能三：Markdown 标签跳转

### 7.1 技术可行性评估

**结论：纯前端实现，后端零改动。技术完全可行。**

| 维度 | 评估 |
|------|------|
| 语法解析 | 正则匹配 `\[([^\]]+):([^\]]+)\]`，Tiptap 自定义 Mark 可实现 |
| 渲染 | 在 WYSIWYG 模式中渲染为可点击的标签样式（chip/badge），源码和预览模式同步处理 |
| 跳转 | 通过 Tiptap 的 `view.coordsAtPos()` 定位配对标签的 DOM 坐标，`scrollIntoView()` 滚动 |
| Markdown 序列化 | `@tiptap/markdown` 扩展的序列化/反序列化需自定义规则 |
| 强校验 | 遍历文档中所有标签，按标签名分组，非成对（≠2）的标记为错误 |
| 后端影响 | 无。标签数据作为普通文本存储在 `notes.content` 中 |

**风险点**：

1. `@tiptap/markdown` 扩展的自定义序列化规则可能与现有 Markdown 语法冲突（如与链接语法 `[text](url)` 的区分）——通过正则精确匹配可解决
2. 大文档中标签配对的性能——标签数量有限（通常 < 50 对），线性扫描即可，无性能问题

### 7.2 语法规范

#### 7.2.1 标签格式

```
[标签名:具体内容]
```

- 使用**英文**方括号 `[` `]` 和**英文**冒号 `:`
- 标签名与具体内容之间用**第一个**英文冒号分隔（内容中可包含冒号）
- 标签名：支持中文、英文字母、数字、下划线，不允许空白字符和 `]` `:` 作为首字符
- 具体内容：任意非 `]` 字符

#### 7.2.2 配对规则

- **区分大小写**：`[Foo:bar]` 和 `[foo:bar]` 是不同的标签名
- **恰好成对**：每个标签名必须在文档中出现**恰好 2 次**
- **内容可以不同**：`[概念:定义A]` 和 `[概念:详见此处]` 是合法的一对（标签名相同即可）
- **双向跳转**：点击任一个标签，跳转到另一个标签

#### 7.2.3 示例

合法：

```markdown
## 第一章

这里提到了[光合作用:植物将光能转化为化学能的过程]。

## 第三章

如前文[光合作用:详见第一章描述]所述，光合作用是...
```

→ 两个 `光合作用` 标签组成一对，点击任一个跳转到另一个。

不合法（强校验报错）：

```markdown
[概念A:第一个]
[概念A:第二个]
[概念A:第三个]    ← 报错：概念A 出现 3 次，不成对
[概念B:只有一个]  ← 报错：概念B 只出现 1 次，不成对
```

### 7.3 前端实现要点（供前端文档参考）

#### 7.3.1 与现有语法的区分

标签语法 `[name:content]` 需要与以下 Markdown 语法区分：

| 语法 | 格式 | 区分方式 |
|------|------|---------|
| 链接 | `[text](url)` | 标签用 `:` 后接内容，链接用 `](url)` |
| 图片 | `![alt](url)` | 图片以 `!` 开头 |
| 参考链接 | `[text][ref]` | 参考链接用 `][` |

正则表达式：`/\[([^\s\]:][^\]:]*):([^\]]+)\]/`

- 排除以 `]` 或 `:` 开头的标签名
- 排除空白字符开头的标签名
- 确保不与 `[text](url)` 匹配（链接中 `]` 后跟 `(` 而非 `:`）

#### 7.3.2 校验逻辑

- 遍历编辑器文档中所有匹配的标签
- 按标签名分组计数
- 计数 ≠ 2 的标签名标记为错误
- 错误标签在编辑器中渲染为红色下划线 + hover 提示"标签'{name}'未成对出现（当前{n}个）"
- 校验在文档内容变化时触发（debounce 500ms）

---

## 八、Pydantic Schema 汇总

```python
# === 整理到笔记 ===

class OrganizeFromChatRequest(BaseModel):
    """整理到笔记请求"""
    ai_reply_content: str
    selected_text: str | None = None
    user_prompt: str | None = None

class OrganizeFromChatResponse(BaseModel):
    """整理到笔记响应"""
    agent_session_id: uuid.UUID
    task_id: str
    message: str

class OrganizeFromChatProgress(BaseModel):
    """整理到笔记 WebSocket 进度"""
    stage: str          # starting / reading_note / analyzing / editing / complete / error
    percent: int
    agent_session_id: str | None = None
    operations_applied: int | None = None
    error_message: str | None = None

# === edit_note 工具参数扩展 ===

class EditNoteToolInput(BaseModel):
    """edit_note 工具输入（扩展列级精度）"""
    note_id: str
    start_line: int
    end_line: int
    start_column: int | None = None   # 新增：起始列（0-based）
    end_column: int | None = None     # 新增：结束列（0-based，含）
    operation: str                     # insert / replace / delete
    content: str = ""

# === Agent 会话 visibility ===

class AgentSessionCreate(BaseModel):
    """创建 Agent 会话（新增 visibility 字段）"""
    context_type: str | None = None
    context_id: uuid.UUID | None = None
    title: str | None = None
    visibility: str = "visible"        # 新增：visible / hidden

class AgentSessionResponse(BaseModel):
    """Agent 会话响应（新增 visibility 字段）"""
    id: uuid.UUID
    title: str | None
    context_type: str | None
    context_id: uuid.UUID | None
    status: str
    visibility: str                    # 新增
    created_at: datetime
    updated_at: datetime
```

---

## 九、路由注册

### 9.1 新增端点

| 方法 | 路径 | 描述 | 所属文件 |
|------|------|------|---------|
| POST | `/api/v1/notes/{note_id}/organize-from-chat` | 整理到笔记（从 AI 回复） | `api/v1/agent.py` |
| WS | `/ws/organize-from-chat/{task_id}` | 整理到笔记进度 | `api/v1/websocket.py` |

### 9.2 修改端点

| 方法 | 路径 | 变更 |
|------|------|------|
| GET | `/api/v1/agent/sessions` | 新增可选查询参数 `visibility` |

### 9.3 路由注册代码位置

- `POST /notes/{note_id}/organize-from-chat`：注册在 `api/v1/agent.py` 路由文件中（因为是 Agent 相关功能），但路径前缀为 `/notes/{note_id}/`
- 或者独立注册在 `api/v1/notes.py` 中，取决于路由组织偏好。建议放在 `agent.py` 中，因为核心逻辑是创建 Agent 会话

---

## 十、Celery 任务

### 10.1 新增任务：organize_from_chat_task

| 属性 | 值 |
|------|-----|
| 任务名 | `app.tasks.note_tasks.organize_from_chat_task` |
| 触发方式 | API 调用 |
| 超时 | 120 秒（软限制 100 秒） |
| 签名 | `user_id_str, note_id_str, agent_session_id_str, ai_reply_content, selected_text, user_prompt` |

**执行流程**：

```
1. 初始化 DB 引擎
2. 查询笔记（title + content）
3. 构建系统 Prompt（注入笔记内容 + AI 回复）
4. 构建用户消息
5. 创建 AgentLoop（max_steps=3, token_budget=8000）
6. 推送进度：starting (5%)
7. Agent 思考 → 调用 get_note_content（推送进度：reading_note 15%）
8. Agent 观察笔记内容 → 决定插入位置（推送进度：analyzing 30%）
9. Agent 调用 edit_note（推送进度：editing 60%）
10. edit_note 处理器执行实际的笔记编辑 + Meilisearch 同步 + WS 推送 note_edit
11. Agent 生成总结 → 推送进度：complete (100%)
12. 保存 Agent 消息
```

**工具白名单**：

```python
allowed_tools = ["get_note_content", "edit_note"]
```

**edit_note 操作限制**：

```python
# 在 AgentLoop 或工具处理器中检查
if tool_name == "edit_note" and params["operation"] != "insert":
    return ToolResult(
        success=False,
        error_message="整理到笔记模式下只允许 insert 操作"
    )
```

### 10.2 进度推送实现

```python
# Celery worker 中（同步 Redis）
import redis
_sync_redis = redis.Redis.from_url("redis://localhost:6379/3")

def publish_organize_progress(task_id: str, data: dict):
    _sync_redis.publish(
        f"organize_from_chat_progress:{task_id}",
        json.dumps(data, ensure_ascii=False)
    )
```

```python
# FastAPI WebSocket 端点中（async Redis）
async def organize_from_chat_progress_ws(websocket: WebSocket, task_id: str):
    async_redis = redis.asyncio.Redis.from_url("redis://localhost:6379/3")
    pubsub = async_redis.pubsub()
    await pubsub.subscribe(f"organize_from_chat_progress:{task_id}")
    # ... 转发消息到 WebSocket
```

---

## 十一、Prompt 模板

### 11.1 整理到笔记 Agent 系统 Prompt

文件：`app/agent/prompts/note_organize_agent.py`

```python
NOTE_ORGANIZE_AGENT_SYSTEM_PROMPT = """你是一个笔记整理助手。你的唯一任务是将给定的文本内容插入到用户笔记的合适位置。

## 当前笔记内容
---
{note_content}
---

## 需要整理的内容
{content_to_organize}

## 工作规则
1. 仔细阅读笔记全文，理解笔记的结构、主题层次和段落划分
2. 分析需要整理的内容，判断它与笔记中哪些部分最相关
3. 使用 edit_note 工具将内容以 insert 操作插入到合适位置
4. 插入的内容使用 Markdown 格式，与笔记现有风格保持一致
5. 位置选择原则：
   - 如果内容是对某个概念的解释，插入到该概念首次出现的位置之后
   - 如果内容是补充信息，插入到相关章节的末尾
   - 如果内容自成一体，可以追加到笔记末尾作为新章节
6. 只允许使用 insert 操作，禁止 replace 和 delete
7. 尽量合并为一次 edit_note 调用

## 输出
完成编辑后，用一句话说明你将内容插入到了哪里以及原因。
"""

NOTE_ORGANIZE_USER_PROMPT_WITH_SELECTION = """用户选中了笔记中的以下原文：
"{selected_text}"

AI 对选中内容的回复如下：
{ai_reply_content}

请将 AI 回复中有价值的内容整理到笔记中。"""

NOTE_ORGANIZE_USER_PROMPT_WITHOUT_SELECTION = """请将以下内容整理到笔记中：
{ai_reply_content}"""
```

**Prompt 变量**：

| 变量 | 来源 | 说明 |
|------|------|------|
| `note_content` | 数据库查询 Note.content | 笔记全文 |
| `content_to_organize` | API 请求 `ai_reply_content` | AI 回复内容 |
| `selected_text` | API 请求（可选） | 用户划词选中的文本 |
| `ai_reply_content` | API 请求 | AI 回复内容 |

---

## 十二、WebSocket 端点

### 12.1 新增：整理到笔记进度

| 属性 | 值 |
|------|-----|
| 路径 | `/ws/organize-from-chat/{task_id}?token={access_token}` |
| 认证 | JWT token（Query 参数） |
| Redis 频道 | `organize_from_chat_progress:{task_id}` |
| 发布端 | Celery worker（同步 Redis） |
| 订阅端 | FastAPI WebSocket（async Redis） |

**消息格式**：

```json
// 进度更新
{"type": "progress", "data": {"stage": "reading_note", "percent": 15}}

// 编辑操作通知（前端可据此刷新编辑器）
{"type": "note_edit", "data": {"note_id": "uuid", "operation": "insert"}}

// 完成
{"type": "complete", "data": {"agent_session_id": "uuid", "operations_applied": 1}}

// 错误
{"type": "error", "data": {"message": "整理失败：..."}}
```

### 12.2 复用：Agent 对话 WebSocket

划词问 AI 的流式回复复用现有 Agent WebSocket：

| 属性 | 值 |
|------|-----|
| 路径 | `/ws/agent/{session_id}?token={access_token}` |
| 消息协议 | 与现有 Agent WS 完全一致 |

---

## 十三、验收标准

### 13.1 划词问 AI

- [ ] 前端 BubbleMenu 划词后正确显示"问 AI"按钮
- [ ] 点击"问 AI"后可修改提示词（默认"请解释"）
- [ ] 选中文本 + 提示词通过 Agent 通道发送
- [ ] AI 回复在左侧 ChatPanel 中流式展示
- [ ] 同一笔记复用同一 Agent 会话
- [ ] Agent 会话在 Agent 页面可见

### 13.2 整理到笔记

- [ ] ChatPanel 每次 AI 回复后显示"整理到笔记"按钮
- [ ] 点击按钮后调用 `POST /notes/{note_id}/organize-from-chat`
- [ ] 后端创建隐藏 Agent 会话（`visibility='hidden'`）
- [ ] 隐藏会话在 Agent 页面列表中可见
- [ ] 隐藏会话在笔记侧边栏中不可见
- [ ] Agent 正确读取笔记内容并决定插入位置
- [ ] `edit_note` 工具支持列级精度（`start_column` / `end_column`）
- [ ] 列级 insert 操作正确在指定行列位置插入文本
- [ ] 列级 replace/delete 操作正确处理跨行场景
- [ ] 现有行级编辑功能不受影响（向后兼容）
- [ ] 整理完成后笔记内容正确更新
- [ ] Meilisearch 索引同步更新
- [ ] WebSocket 进度推送正常（starting → reading_note → analyzing → editing → complete）
- [ ] 整理到笔记 Agent 只允许 insert 操作（拒绝 delete/replace）

### 13.3 Markdown 标签跳转（前端验收，后端无关）

- [ ] 编辑器中正确识别 `[标签名:内容]` 语法
- [ ] 标签渲染为可点击样式
- [ ] 点击标签跳转到配对标签位置
- [ ] 支持双向跳转
- [ ] 区分大小写
- [ ] 支持中文标签名
- [ ] 强校验：不成对的标签显示错误提示
- [ ] 源码模式与 WYSIWYG 模式标签语法同步

---

## 十四、非功能要求

### 14.1 性能

- 整理到笔记 Celery 任务超时：120 秒
- Agent 循环 max_steps：3（整理任务简单）
- Agent token_budget：8000
- 标签校验 debounce：500ms（前端）

### 14.2 安全

- 整理到笔记 API 需验证笔记归属当前用户
- 隐藏 Agent 会话的 edit_note 操作只允许 insert
- 整理请求的 `ai_reply_content` 最大长度：10000 字符
- 整理请求的 `user_prompt` 最大长度：2000 字符

### 14.3 兼容性

- `edit_note` 工具的 `start_column` / `end_column` 为可选参数，不传时行为与 Sprint 9 完全一致
- `agent_sessions.visibility` 默认 `'visible'`，现有数据无需迁移
- Agent 会话列表 API 的 `visibility` 参数为可选，不传时返回所有会话（向后兼容）

### 14.4 可观测性

- 整理到笔记任务日志：记录 Agent 会话 ID、笔记 ID、操作类型、插入位置
- edit_note 列级操作日志：记录 start_line/start_column/end_line/end_column/operation

---

## 十五、与现有系统的集成点

| 集成点 | 说明 |
|--------|------|
| Agent 会话系统 | 复用会话创建/消息存储/WS 流式通信 |
| AgentLoop | 复用 ReAct 循环，限制工具白名单 |
| ToolRegistry | edit_note 工具参数扩展 |
| note_handler | edit_note 执行逻辑支持列级操作 |
| Redis Pub/Sub | 复用跨进程进度推送模式 |
| Celery | 新增异步任务 |
| Meilisearch | edit_note 执行后自动同步索引 |
| WebSocket ConnectionManager | 复用 note_edit 事件推送 |

---

## 十六、API 端点汇总（本 Sprint 新增）

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/v1/notes/{note_id}/organize-from-chat` | 整理到笔记（从 AI 回复） |
| WS | `/ws/organize-from-chat/{task_id}` | 整理到笔记进度 |
| GET | `/api/v1/agent/sessions?visibility=hidden` | 筛选隐藏会话（参数扩展） |
