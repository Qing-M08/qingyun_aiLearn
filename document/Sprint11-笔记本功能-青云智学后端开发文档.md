# Sprint 11 — 笔记本功能 — 青云智学后端开发文档

> 版本: 1.0 | 日期: 2026-07-16 | 优先级: P1  
> 前置依赖: Phase 1 ~ Phase 5 全部已完成

---

## 一、项目背景与目标

青云智学当前的笔记系统以单篇笔记为核心，支持 CRUD、标签、AI 整理、划词问 AI 等能力，但缺少将多篇笔记组织为一个知识集合的功能。用户在学习过程中自然形成的知识体系（如"机器学习"、"高等数学"等主题）无法在笔记层面进行分组管理。

Sprint 11 引入"笔记本"概念，允许用户将多篇笔记组建成一个笔记本，并提供笔记本内的目录管理和独立搜索能力。

### 核心目标

- 笔记本 CRUD，支持封面颜色与自定义摘要
- 笔记本与笔记多对多关系，支持手动拖拽排序
- 笔记本详情页：左侧目录 + 右侧 Markdown 预览/编辑
- 笔记本内独立搜索（与全局搜索隔离）
- 笔记本删除 = 解散分组，笔记保留

### 不在本 Sprint 范围

- 笔记本嵌套（子笔记本）
- 分享/协作
- 笔记本级 AI 能力（如 AI 生成目录摘要）

---

## 二、技术栈

沿用已有技术栈，本 Sprint 无新增技术依赖：

| 组件 | 技术选型 | 用途 |
|------|---------|------|
| Web 框架 | FastAPI | API 路由 |
| ORM | SQLAlchemy 2.0 (async) | 数据模型 |
| 数据库 | PostgreSQL 16 | 持久化 |
| 搜索引擎 | Meilisearch v1.8 | 笔记本内全文搜索 |
| 异步任务 | Celery + Redis | （本 Sprint 无新增异步任务） |
| 数据库迁移 | Alembic | Schema 变更 |

---

## 三、数据模型变更

### 3.1 新增模型：Notebook

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK, 默认 uuid4 | 主键 |
| user_id | UUID | FK → users.id, NOT NULL | 所属用户 |
| name | String(200) | NOT NULL | 笔记本名称 |
| summary | Text | NULLABLE | 用户自定义摘要 |
| cover_color | String(20) | NOT NULL, 默认 "#F59E0B" | 封面颜色（十六进制色值） |
| created_at | DateTime(timezone=True) | NOT NULL, 默认 now() | 创建时间 |
| updated_at | DateTime(timezone=True) | NOT NULL, 默认 now(), onupdate now() | 修改时间 |

索引：
- `ix_notebooks_user_id` — 按用户查询
- `ix_notebooks_user_updated` — (user_id, updated_at DESC) 支持按时间排序的列表查询

### 3.2 新增模型：NotebookNote（关联表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK, 默认 uuid4 | 主键 |
| notebook_id | UUID | FK → notebooks.id ON DELETE CASCADE, NOT NULL | 笔记本 |
| note_id | UUID | FK → notes.id ON DELETE CASCADE, NOT NULL | 笔记 |
| sort_order | Integer | NOT NULL, 默认 0 | 排序权重（升序排列） |
| created_at | DateTime(timezone=True) | NOT NULL, 默认 now() | 加入时间 |

约束与索引：
- `uq_notebook_note` — UNIQUE(notebook_id, note_id)，同一笔记本内笔记不重复
- `ix_notebook_notes_notebook_sort` — (notebook_id, sort_order) 支持按排序查询目录
- `ix_notebook_notes_note_id` — note_id 索引，支持"查询笔记属于哪些笔记本"

### 3.3 关系定义

```
Notebook:
  - notebook_notes → List[NotebookNote]  (cascade delete)
  - user → User (many-to-one)

NotebookNote:
  - notebook → Notebook (many-to-one)
  - note → Note (many-to-one)

Note:
  - notebook_entries → List[NotebookNote]  (反向关系，便于查询笔记所属笔记本)
```

### 3.4 Alembic 迁移

迁移文件名：`20260716_add_notebook_tables.py`

操作：
1. 创建 `notebooks` 表
2. 创建 `notebook_notes` 表
3. 创建上述索引与约束

---

## 四、API 接口设计

### 4.1 笔记本 CRUD

#### POST /api/v1/notebooks — 创建笔记本

请求体：
```json
{
  "name": "机器学习笔记",
  "summary": "涵盖线性回归、分类、聚类等核心算法",
  "cover_color": "#3B82F6"
}
```

响应（201）：
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "name": "机器学习笔记",
  "summary": "涵盖线性回归、分类、聚类等核心算法",
  "cover_color": "#3B82F6",
  "note_count": 0,
  "created_at": "2026-07-16T10:00:00Z",
  "updated_at": "2026-07-16T10:00:00Z"
}
```

校验规则：
- name 长度 1~200 字符，不可为空
- summary 最大 1000 字符
- cover_color 格式校验（`^#[0-9A-Fa-f]{6}$`），不传则使用默认主题色 `#F59E0B`

#### GET /api/v1/notebooks — 笔记本列表

查询参数：
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| page | int | 1 | 页码 |
| page_size | int | 20 | 每页数量（上限 100） |
| sort_by | str | "updated_at" | 排序字段（updated_at / created_at / name） |
| sort_order | str | "desc" | 排序方向（asc / desc） |

响应（200）：
```json
{
  "items": [
    {
      "id": "uuid",
      "name": "机器学习笔记",
      "summary": "...",
      "cover_color": "#3B82F6",
      "note_count": 12,
      "created_at": "...",
      "updated_at": "..."
    }
  ],
  "total": 5,
  "page": 1,
  "page_size": 20
}
```

note_count 通过 LEFT JOIN + COUNT 聚合获取，避免 N+1 查询。

#### GET /api/v1/notebooks/{id} — 笔记本详情

响应（200）：与列表单项结构相同，额外包含 `latest_notes`（最近修改的 3 篇笔记摘要，用于网格卡片预览）。

```json
{
  "id": "uuid",
  "name": "机器学习笔记",
  "summary": "...",
  "cover_color": "#3B82F6",
  "note_count": 12,
  "latest_notes": [
    { "id": "uuid", "title": "线性回归", "word_count": 1200 },
    { "id": "uuid", "title": "决策树", "word_count": 800 },
    { "id": "uuid", "title": "SVM", "word_count": 1500 }
  ],
  "created_at": "...",
  "updated_at": "..."
}
```

#### PUT /api/v1/notebooks/{id} — 更新笔记本

请求体（部分更新）：
```json
{
  "name": "机器学习笔记（更新）",
  "summary": "新摘要",
  "cover_color": "#EF4444"
}
```

响应（200）：更新后的完整笔记本对象。

校验：至少传入一个字段；name 非空时长度 1~200。

#### DELETE /api/v1/notebooks/{id} — 删除笔记本

语义：解散分组。删除 Notebook 记录及所有 NotebookNote 关联记录，Note 记录全部保留。

响应（204）：无内容。

级联行为：
- `notebook_notes` 通过 ON DELETE CASCADE 自动清理
- 无需清理 Meilisearch 索引（笔记本内搜索基于 note_ids filter，不维护独立索引）

---

### 4.2 目录管理（笔记增删与排序）

#### GET /api/v1/notebooks/{id}/notes — 获取目录

查询参数：
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| page | int | 1 | 页码 |
| page_size | int | 50 | 每页数量（上限 200） |

响应（200）：
```json
{
  "items": [
    {
      "note_id": "uuid",
      "sort_order": 0,
      "title": "线性回归",
      "word_count": 1200,
      "subject": "数学",
      "tags": [
        { "id": "uuid", "name": "线性回归", "color": "#3B82F6" }
      ],
      "updated_at": "2026-07-15T08:00:00Z"
    }
  ],
  "total": 12,
  "page": 1,
  "page_size": 50
}
```

按 sort_order ASC 排序返回。每条记录包含笔记的基本信息和标签，供左侧目录直接渲染。

#### POST /api/v1/notebooks/{id}/notes — 添加笔记到笔记本

请求体：
```json
{
  "note_ids": ["uuid1", "uuid2", "uuid3"]
}
```

响应（200）：
```json
{
  "added": 3,
  "skipped": 0,
  "message": "已添加 3 篇笔记"
}
```

逻辑：
- 验证所有 note_ids 属于当前用户
- 已存在于笔记本中的笔记跳过（不报错），返回 skipped 计数
- 新笔记的 sort_order 从当前最大值 + 1 开始递增
- 更新笔记本的 updated_at

#### DELETE /api/v1/notebooks/{id}/notes/{note_id} — 从笔记本移除笔记

响应（204）：无内容。

仅删除 NotebookNote 关联记录，Note 记录保留。

#### PUT /api/v1/notebooks/{id}/notes/reorder — 批量更新排序

请求体：
```json
{
  "order": ["uuid1", "uuid3", "uuid2"]
}
```

响应（200）：
```json
{
  "message": "排序已更新",
  "updated": 3
}
```

逻辑：
- `order` 数组包含笔记本内所有笔记的 ID，按期望顺序排列
- 校验：数组长度必须等于笔记本内笔记总数；数组元素必须与当前笔记本内的 note_ids 完全一致
- 按数组索引更新 sort_order（index 0 → sort_order 0, index 1 → sort_order 1, ...）
- 使用批量 UPDATE 减少数据库往返

---

### 4.3 笔记本内搜索

#### GET /api/v1/notebooks/{id}/search — 笔记本内搜索

查询参数：
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| q | str | （必填） | 搜索关键词 |
| page | int | 1 | 页码 |
| page_size | int | 20 | 每页数量 |

响应（200）：
```json
{
  "items": [
    {
      "note_id": "uuid",
      "title": "线性回归",
      "highlight_title": "线性<em>回归</em>",
      "highlight_content": "...最小二乘法进行线性<em>回归</em>拟合...",
      "word_count": 1200,
      "tags": [...],
      "updated_at": "..."
    }
  ],
  "total": 3,
  "page": 1,
  "page_size": 20,
  "query": "回归"
}
```

实现流程：
1. 查询 `notebook_notes` 表获取当前笔记本的所有 note_ids（一次性查出，内存中持有）
2. 若 note_ids 为空，直接返回空结果
3. 调用 Meilisearch notes 索引搜索，filter 条件为 `id IN [note_ids]`
4. 组装返回结果，包含高亮片段

Meilisearch 调用细节：
- 索引：notes（复用现有索引，无需新建）
- filter 表达式：`id IN ['uuid1', 'uuid2', ...]`
- attributesToHighlight：`["title", "content"]`
- highlightPreTag / highlightPostTag：`<em>` / `</em>`
- limit / offset 用于分页

---

## 五、核心服务实现

### 5.1 NotebookService

服务类：`app/services/notebook_service.py`

#### 方法清单

| 方法 | 说明 | 关键逻辑 |
|------|------|---------|
| `create_notebook(db, user_id, schema)` | 创建笔记本 | 校验 name 唯一性（同一用户下不强制唯一，允许同名）；直接创建 |
| `list_notebooks(db, user_id, page, page_size, sort_by, sort_order)` | 笔记本列表 | LEFT JOIN notebook_notes GROUP BY notebook_id 获取 note_count；支持排序 |
| `get_notebook(db, notebook_id, user_id)` | 笔记本详情 | 查询笔记本 + note_count + latest_notes（最近 3 篇） |
| `update_notebook(db, notebook_id, user_id, schema)` | 更新笔记本 | 部分更新；至少一个字段非空 |
| `delete_notebook(db, notebook_id, user_id)` | 删除笔记本 | 级联删除 notebook_notes；笔记保留 |
| `get_notebook_notes(db, notebook_id, user_id, page, page_size)` | 获取目录 | 按 sort_order 排序；JOIN notes + note_tags + tags 获取完整信息 |
| `add_notes_to_notebook(db, notebook_id, user_id, note_ids)` | 添加笔记 | 验证笔记归属；跳过已存在的；sort_order 从 max+1 递增 |
| `remove_note_from_notebook(db, notebook_id, user_id, note_id)` | 移除笔记 | 删除关联记录 |
| `reorder_notebook_notes(db, notebook_id, user_id, ordered_ids)` | 批量排序 | 校验完整性；批量 UPDATE sort_order |
| `search_in_notebook(db, notebook_id, user_id, query, page, page_size)` | 笔记本内搜索 | 先查 note_ids → Meilisearch filter 搜索 |

#### 关键实现细节

**list_notebooks 的 note_count 聚合**：

```
SELECT notebooks.*, COUNT(notebook_notes.id) AS note_count
FROM notebooks
LEFT JOIN notebook_notes ON notebooks.id = notebook_notes.notebook_id
WHERE notebooks.user_id = :user_id
GROUP BY notebooks.id
ORDER BY notebooks.updated_at DESC
```

使用 SQLAlchemy 的 `func.count()` + `outerjoin()` 实现，避免 N+1。

**get_notebook 的 latest_notes**：

```
SELECT notes.id, notes.title, notes.word_count
FROM notes
JOIN notebook_notes ON notes.id = notebook_notes.note_id
WHERE notebook_notes.notebook_id = :notebook_id
ORDER BY notes.updated_at DESC
LIMIT 3
```

**reorder_notebook_notes 的批量更新**：

使用 `executemany` 或 SQLAlchemy 的 `bulk_update_mappings` 一次性更新所有 sort_order，减少数据库往返。对于几十篇笔记的规模，单条事务内完成。

**search_in_notebook 的两步查询**：

```
步骤 1: SELECT note_id FROM notebook_notes WHERE notebook_id = :notebook_id
步骤 2: meilisearch.notes.search(query, filter="id IN [note_ids]", ...)
```

若笔记本内笔记数量 > 500（极端场景），可分批 filter 或降级为数据库 ILIKE 搜索。

### 5.2 权限校验

所有 NotebookService 方法接收 `user_id` 参数，在操作前验证笔记本归属：

```
notebook = await db.get(Notebook, notebook_id)
if not notebook or notebook.user_id != user_id:
    raise HTTPException(404, "笔记本不存在")
```

添加笔记时同样验证笔记归属：

```
notes = await db.execute(
    select(Note).where(Note.id.in_(note_ids), Note.user_id == user_id)
)
if len(notes.all()) != len(note_ids):
    raise HTTPException(403, "部分笔记不属于当前用户")
```

---

## 六、Pydantic Schema

### 6.1 请求 Schema

```python
class NotebookCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    summary: str | None = Field(None, max_length=1000)
    cover_color: str = Field("#F59E0B", pattern=r"^#[0-9A-Fa-f]{6}$")

class NotebookUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    summary: str | None = Field(None, max_length=1000)
    cover_color: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")

class AddNotesRequest(BaseModel):
    note_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=100)

class ReorderNotesRequest(BaseModel):
    order: list[uuid.UUID] = Field(..., min_length=1)
```

### 6.2 响应 Schema

```python
class NotebookBrief(BaseModel):
    """笔记本列表项 / 网格卡片"""
    id: uuid.UUID
    name: str
    summary: str | None
    cover_color: str
    note_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class NotebookDetail(NotebookBrief):
    """笔记本详情（含最近笔记预览）"""
    latest_notes: list[NotePreview]

class NotePreview(BaseModel):
    id: uuid.UUID
    title: str
    word_count: int

class NotebookNoteItem(BaseModel):
    """目录中的笔记项"""
    note_id: uuid.UUID
    sort_order: int
    title: str
    word_count: int
    subject: str | None
    tags: list[TagBrief]
    updated_at: datetime

class TagBrief(BaseModel):
    id: uuid.UUID
    name: str
    color: str | None

class AddNotesResponse(BaseModel):
    added: int
    skipped: int
    message: str

class ReorderResponse(BaseModel):
    message: str
    updated: int

class NotebookSearchResult(BaseModel):
    """笔记本内搜索结果"""
    note_id: uuid.UUID
    title: str
    highlight_title: str | None
    highlight_content: str | None
    word_count: int
    tags: list[TagBrief]
    updated_at: datetime

class NotebookSearchResponse(BaseModel):
    items: list[NotebookSearchResult]
    total: int
    page: int
    page_size: int
    query: str
```

---

## 七、路由注册

### 7.1 路由文件

新增 `app/api/v1/notebooks.py`，注册到 `router.py`：

```python
# router.py 新增
from app.api.v1.notebooks import router as notebooks_router
api_router.include_router(notebooks_router, prefix="/notebooks", tags=["notebooks"])
```

### 7.2 路由清单

| 方法 | 路径 | 处理函数 | 说明 |
|------|------|---------|------|
| POST | /notebooks | create_notebook | 创建笔记本 |
| GET | /notebooks | list_notebooks | 笔记本列表 |
| GET | /notebooks/{id} | get_notebook | 笔记本详情 |
| PUT | /notebooks/{id} | update_notebook | 更新笔记本 |
| DELETE | /notebooks/{id} | delete_notebook | 删除笔记本 |
| GET | /notebooks/{id}/notes | get_notebook_notes | 获取目录 |
| POST | /notebooks/{id}/notes | add_notes | 添加笔记 |
| DELETE | /notebooks/{id}/notes/{note_id} | remove_note | 移除笔记 |
| PUT | /notebooks/{id}/notes/reorder | reorder_notes | 批量排序 |
| GET | /notebooks/{id}/search | search_notebook | 笔记本内搜索 |

所有路由均需认证（`Depends(get_current_user)`）。

---

## 八、Meilisearch 集成

### 8.1 无需新增索引

笔记本内搜索复用现有 `notes` 索引，通过 `id IN [...]` filter 限定搜索范围。不需要为 notebook 创建独立索引或在 notes 索引中增加 notebook 相关字段。

### 8.2 搜索调用方式

在 `search_service.py` 中新增方法：

```python
async def search_notes_by_ids(
    query: str,
    note_ids: list[str],
    offset: int = 0,
    limit: int = 20,
) -> dict:
    """在指定笔记 ID 范围内搜索"""
    filter_expr = f"id IN [{','.join(repr(str(nid)) for nid in note_ids)}]"
    result = await meili_client.index("notes").search(query, {
        "filter": filter_expr,
        "offset": offset,
        "limit": limit,
        "attributesToHighlight": ["title", "content"],
        "highlightPreTag": "<em>",
        "highlightPostTag": "</em>",
    })
    return result
```

### 8.3 降级策略

若 Meilisearch 不可用，降级为数据库 ILIKE 搜索：

```python
async def search_notes_by_ids_fallback(
    db: AsyncSession,
    query: str,
    note_ids: list[uuid.UUID],
    offset: int,
    limit: int,
) -> list[Note]:
    """数据库降级搜索"""
    return await db.execute(
        select(Note)
        .where(Note.id.in_(note_ids))
        .where(
            or_(
                Note.title.ilike(f"%{query}%"),
                Note.content.ilike(f"%{query}%"),
            )
        )
        .offset(offset)
        .limit(limit)
    )
```

---

## 九、验收标准

### 9.1 笔记本 CRUD

- [ ] 可创建笔记本，指定名称、摘要、封面颜色
- [ ] name 为空或超长时返回 422
- [ ] cover_color 格式错误时返回 422
- [ ] 列表接口返回 note_count 正确
- [ ] 列表支持按 updated_at / created_at / name 排序
- [ ] 详情接口返回 latest_notes（最近 3 篇）
- [ ] 更新笔记本仅修改传入字段，未传字段不变
- [ ] 删除笔记本后，notebook_notes 关联记录被清理，notes 记录保留
- [ ] 只能操作自己的笔记本，操作他人笔记本返回 404

### 9.2 目录管理

- [ ] 目录按 sort_order 升序返回
- [ ] 目录项包含笔记标题、字数、学科、标签、修改时间
- [ ] 添加笔记时验证笔记归属，非本人笔记返回 403
- [ ] 添加已存在的笔记时跳过，不报错，skipped 计数正确
- [ ] 新添加的笔记 sort_order 从当前最大值 + 1 开始
- [ ] 移除笔记仅删除关联，笔记本身保留
- [ ] 排序接口校验 order 数组完整性（长度一致、元素一致）
- [ ] 排序后查询结果与 order 数组顺序一致

### 9.3 笔记本内搜索

- [ ] 搜索仅返回当前笔记本内的笔记
- [ ] 搜索结果包含高亮片段（title + content）
- [ ] 搜索支持分页
- [ ] 笔记本为空时返回空结果，不报错
- [ ] Meilisearch 不可用时降级为数据库 ILIKE 搜索
- [ ] 搜索关键词为空时返回 422

### 9.4 数据完整性

- [ ] 同一笔记本内不能重复添加同一笔记（UNIQUE 约束）
- [ ] 笔记被删除时，notebook_notes 关联记录自动清理（ON DELETE CASCADE）
- [ ] 笔记本删除后，关联的 notebook_notes 全部清理
- [ ] Alembic 迁移可正确执行（upgrade + downgrade）

---

## 十、非功能要求

### 10.1 性能

- 笔记本列表查询（含 note_count 聚合）：P95 < 50ms
- 目录查询（50 篇以内）：P95 < 30ms
- 笔记本内搜索（Meilisearch）：P95 < 100ms
- 批量排序（100 篇以内）：P95 < 50ms

### 10.2 安全

- 所有接口需认证，校验 user_id 归属
- 输入校验使用 Pydantic Field 约束（长度、格式）
- 防止越权：操作他人笔记本/笔记返回 404（不暴露资源存在性）

### 10.3 兼容性

- 不影响现有笔记 CRUD、标签、AI 整理、划词问 AI 等功能
- Note 模型新增的 `notebook_entries` 反向关系不影响现有查询
- Meilisearch 无索引变更，不影响全局搜索

---

## 十一、前端对接要点（供前端文档参考）

### 11.1 页面路由变更

| 路径 | 变更 | 说明 |
|------|------|------|
| `/notes` | 改造 | 网格视图：笔记本卡片 + 散落笔记卡片共存 |
| `/notebooks/:id` | 新增 | 笔记本详情页（左目录 + 右预览/编辑） |
| `/notes/new` | 不变 | 新建笔记页（笔记本内/独立新建均跳转此处） |
| `/notes/:id` | 不变 | 笔记编辑页（双击目录项跳转） |

### 11.2 网格卡片数据结构

笔记本卡片使用 `NotebookBrief` 结构（含 note_count、cover_color、summary）。散落笔记卡片使用现有 `Note` 结构。前端需区分两种卡片类型渲染。

### 11.3 详情页交互映射

| 交互 | 调用 API |
|------|---------|
| 加载目录 | `GET /notebooks/{id}/notes` |
| 单击目录项 | 前端本地切换右侧预览内容（不调 API，目录已含足够信息） |
| 双击目录项 | 前端路由跳转到 `/notes/{note_id}` |
| 进入编辑模式 | 前端本地切换（启用拖拽） |
| 拖拽排序完成 | `PUT /notebooks/{id}/notes/reorder` |
| 搜索框输入 | `GET /notebooks/{id}/search?q=xxx` |
| 添加笔记 | `POST /notebooks/{id}/notes` |
| 移除笔记 | `DELETE /notebooks/{id}/notes/{note_id}` |

### 11.4 新建笔记归属

新建笔记时若从笔记本详情页触发，前端在创建成功后自动调用 `POST /notebooks/{id}/notes` 将新笔记加入当前笔记本。

---

## 十二、文件变更清单

### 后端新增文件

| 文件 | 说明 |
|------|------|
| `app/models/notebook.py` | Notebook + NotebookNote ORM 模型 |
| `app/services/notebook_service.py` | 笔记本业务逻辑 |
| `app/schemas/notebook.py` | Pydantic Schema |
| `app/api/v1/notebooks.py` | API 路由 |
| `alembic/versions/20260716_add_notebook_tables.py` | 数据库迁移 |

### 后端修改文件

| 文件 | 变更 |
|------|------|
| `app/models/note.py` | 新增 `notebook_entries` 反向关系 |
| `app/api/v1/router.py` | 注册 notebooks 路由 |
| `app/services/search_service.py` | 新增 `search_notes_by_ids` 方法 |
| `app/main.py` | 无需修改（Meilisearch 无索引变更） |

### 前端新增文件（供前端文档参考）

| 文件 | 说明 |
|------|------|
| `src/api/notebook.ts` | 笔记本 API 调用 |
| `src/types/notebook.ts` | 笔记本类型定义 |
| `src/stores/notebookStore.ts` | 笔记本状态管理 |
| `src/pages/notebooks/NotebookDetailPage.tsx` | 笔记本详情页 |
| `src/components/notebook/NotebookCard.tsx` | 网格卡片组件 |
| `src/components/notebook/NotebookSidebar.tsx` | 左侧目录组件 |
| `src/components/notebook/NotebookSearch.tsx` | 笔记本内搜索组件 |

### 前端修改文件（供前端文档参考）

| 文件 | 变更 |
|------|------|
| `src/pages/notes/NotesListPage.tsx` | 改造为网格视图（笔记本 + 散落笔记） |
| `src/App.tsx` | 新增 `/notebooks/:id` 路由 |
| `src/stores/noteStore.ts` | 可能需要适配笔记本上下文 |
