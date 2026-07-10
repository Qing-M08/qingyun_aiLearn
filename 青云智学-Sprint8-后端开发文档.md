# Sprint 8：讲义生成 → 自动创建笔记 — 后端开发文档

> 版本：1.0 | 日期：2026-07-09
> 依赖：Phase 1-2 已完成（ORM 模型、笔记服务、学习引擎、Celery 任务、WebSocket）
> 负责人：后端开发

---

## 一、需求概述

**原流程**：学习路线页选择步骤 → 生成讲义 → WebSocket 推送进度 → 跳转到 LecturePage(`/learning/lecture/:id`)查看。

**新流程**：学习路线页选择步骤 → 生成讲义 → 后端自动生成讲义 **并创建笔记** → WebSocket 推送完成（含 `note_id`）→ 前端跳转到笔记编辑页(`/notes/{noteId}`)。

**核心规则**：
- 笔记标题 = 讲义标题（默认 "讲义 - {知识节点名称}"）
- 笔记内容 = 讲义 Markdown 全文
- 自动标签 = 知识节点名称 + 学科中文名称（两者都打）
- 笔记创建失败不阻塞讲义生成（graceful degradation）
- 原 LecturePage 前端废弃，后端 Lecture API 保留

---

## 二、数据库变更

### 2.1 Lecture 模型新增字段

文件：`app/models/learning.py`

```python
# Lecture 模型新增：
note_id: Mapped[int | None] = mapped_column(
    ForeignKey("notes.id", ondelete="SET NULL"),
    nullable=True, index=True,
    comment="关联的笔记 ID（讲义生成后自动创建）"
)
note: Mapped["Note | None"] = relationship(
    "Note", foreign_keys=[note_id], lazy="selectin"
)
```

### 2.2 Alembic 迁移

生成迁移文件：

```bash
alembic revision --autogenerate -m "add note_id to lectures"
```

迁移内容预览：

```python
def upgrade():
    op.add_column('lectures', sa.Column(
        'note_id', sa.Integer(),
        sa.ForeignKey('notes.id', ondelete='SET NULL'),
        nullable=True
    ))
    op.create_index(op.f('ix_lectures_note_id'), 'lectures', ['note_id'])

def downgrade():
    op.drop_index(op.f('ix_lectures_note_id'), table_name='lectures')
    op.drop_column('lectures', 'note_id')
```

---

## 三、Schema 变更

### 3.1 LectureResponse 新增 note_id

文件：`app/schemas/learning.py`

```python
class LectureResponse(BaseModel):
    id: int
    route_id: int
    step_id: int
    title: str
    content: str
    status: str
    note_id: int | None = None   # 新增
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

### 3.2 WebSocket 完成消息格式

`complete` 类型消息新增 `note_id` 字段：

```json
{
  "type": "complete",
  "data": {
    "lecture": {
      "id": 1,
      "title": "讲义 - 二次函数",
      "content": "# 二次函数\n...",
      "status": "completed",
      "note_id": 42
    },
    "note_id": 42
  }
}
```

前端根据 `note_id` 跳转到 `/notes/42`。


---

## 四、服务层变更

### 4.1 LearningService 修改

文件：`app/services/learning_service.py`

在 `generate_lecture_content` 方法中，LLM 生成完成后追加笔记创建逻辑：

```python
async def generate_lecture_content(self, db, lecture_id: int) -> Lecture:
    lecture = await db.get(Lecture, lecture_id)
    step = await db.get(LearningRouteStep, lecture.step_id)
    node = await db.get(KnowledgeNode, step.knowledge_node_id)

    # ... 原有 LLM 生成逻辑保持不变 ...
    lecture.content = llm_response.content
    lecture.status = "completed"

    # === 新增：自动创建笔记 ===
    try:
        note = await self._create_note_from_lecture(db, lecture, step, node)
        lecture.note_id = note.id
        logger.info("Note auto-created for lecture",
                     lecture_id=lecture.id, note_id=note.id)
    except Exception as e:
        logger.warning("Failed to create note for lecture",
                       lecture_id=lecture.id, error=str(e))
        # 笔记创建失败不阻塞讲义生成

    await db.commit()
    await db.refresh(lecture)
    return lecture
```

### 4.2 新增 _create_note_from_lecture 方法

```python
async def _create_note_from_lecture(
    self, db, lecture: Lecture, step: LearningRouteStep, node: KnowledgeNode
) -> Note:
    '''从讲义创建笔记，并打上知识节点+学科标签'''
    # 获取路线所属用户
    route = await db.get(LearningRoute, lecture.route_id)
    user_id = route.user_id

    # 笔记标题 = 讲义标题
    title = lecture.title or f"讲义 - {node.name}"

    # 创建笔记（调用 NoteService）
    note = await NoteService.create_note(
        db=db,
        title=title,
        content=lecture.content,
        user_id=user_id
    )

    # 自动标签：知识节点名称 + 学科中文名
    tag_names = [node.name]
    if node.subject:
        subject_display = SUBJECT_DISPLAY_NAMES.get(node.subject, node.subject)
        tag_names.append(subject_display)

    for tag_name in tag_names:
        tag = await NoteService.get_or_create_tag(db, tag_name, user_id=user_id)
        await NoteService.add_tag_to_note(db, note.id, tag.id)

    return note
```

### 4.3 SUBJECT_DISPLAY_NAMES 常量

确认 `knowledge_service.py` 中已有的学科映射表可复用：

```python
# 已在 knowledge_service.py 中定义，可直接导入
SUBJECT_DISPLAY_NAMES = {
    "math": "数学",
    "physics": "物理",
    "chemistry": "化学",
    "biology": "生物",
    "computer_science": "计算机科学",
    "english": "英语",
    "chinese": "语文",
    "history": "历史",
    "geography": "地理",
    "economics": "经济学",
}
```

在 `learning_service.py` 顶部导入：

```python
from app.services.knowledge_service import SUBJECT_DISPLAY_NAMES
```


---

## 五、Celery 任务变更

### 5.1 generate_lecture_content_task

文件：`app/tasks/learning_tasks.py`

任务本身不需要修改——它只调用 `LearningService.generate_lecture_content`，笔记创建逻辑已在服务层完成。

但需确保 WebSocket `complete` 消息携带 `note_id`：

```python
@celery_app.task(bind=True, max_retries=2)
def generate_lecture_content_task(self, lecture_id: int):
    # ... 原有逻辑 ...
    # 完成后通过 WebSocket 发送 complete 消息
    # 新增 note_id 字段
    await manager.send_json(
        f"lecture_{lecture_id}",
        {
            "type": "complete",
            "data": {
                "lecture": lecture_schema.model_dump(lecture),
                "note_id": lecture.note_id   # 新增
            }
        }
    )
```

---

## 六、WebSocket 消息格式变更

### 6.1 完整消息对比

**变更前**：
```json
{
  "type": "complete",
  "data": {
    "lecture": { "id": 1, "title": "...", "content": "...", "status": "completed" }
  }
}
```

**变更后**：
```json
{
  "type": "complete",
  "data": {
    "lecture": { "id": 1, "title": "...", "content": "...", "status": "completed", "note_id": 42 },
    "note_id": 42
  }
}
```

### 6.2 其他消息类型不变

`progress`、`error` 类型保持不变。

---

## 七、API 端点变更

### 7.1 变化的端点

| 方法 | 路径 | 变更说明 |
|------|------|----------|
| POST | `/api/v1/learning/lectures/generate` | 无变化，但响应中的 Lecture 对象新增 `note_id` 字段 |
| GET | `/api/v1/learning/lectures/{id}` | 响应中新增 `note_id` 字段 |

### 7.2 无需新增 API

笔记创建是后端自动完成的，不需要新的 API 端点。前端通过 WebSocket `complete` 消息中的 `note_id` 获取笔记 ID，然后跳转到笔记编辑页。

---

## 八、验收标准

### 8.1 功能验收

- [ ] 生成讲义后，数据库 `lectures` 表中 `note_id` 字段被正确填充
- [ ] 自动创建的笔记标题 = 讲义标题
- [ ] 自动创建的笔记内容 = 讲义 Markdown 全文
- [ ] 笔记自动拥有两个标签：知识节点名称 + 学科中文名
- [ ] WebSocket `complete` 消息包含 `note_id` 字段
- [ ] GET `/api/v1/learning/lectures/{id}` 响应包含 `note_id` 字段

### 8.2 异常场景

- [ ] 笔记创建失败时，讲义生成仍然成功（`note_id` 为 null）
- [ ] 笔记创建失败时，日志记录 warning 级别错误
- [ ] 标签已存在时复用（get_or_create_tag），不重复创建

### 8.3 数据库验收

- [ ] Alembic 迁移成功执行
- [ ] `lectures.note_id` 索引已创建
- [ ] 外键约束 `ondelete="SET NULL"` 生效（删除笔记后 lecture.note_id 自动置空）

---

## 九、影响范围与风险

### 9.1 影响文件清单

| 文件 | 变更类型 |
|------|----------|
| `app/models/learning.py` | 新增 `note_id` 字段 + relationship |
| `app/schemas/learning.py` | `LectureResponse` 新增 `note_id` |
| `app/services/learning_service.py` | 新增 `_create_note_from_lecture` 方法，修改 `generate_lecture_content` |
| `app/tasks/learning_tasks.py` | WebSocket complete 消息新增 `note_id` |
| `alembic/versions/` | 新增迁移文件 |

### 9.2 风险点

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| 笔记创建失败影响讲义生成 | 低 | try-except 包裹，失败只记日志 |
| 标签名称冲突 | 低 | get_or_create_tag 复用已有标签 |
| 迁移与现有数据冲突 | 低 | 新增字段 nullable=True，不影响现有数据 |

---

## 十、实施顺序建议

1. 执行 Alembic 迁移，添加 `note_id` 字段
2. 修改 `Lecture` ORM 模型，新增 `note_id` + relationship
3. 修改 `LectureResponse` Schema
4. 在 `LearningService` 中实现 `_create_note_from_lecture` 方法
5. 修改 `generate_lecture_content` 调用新方法
6. 修改 Celery 任务中 WebSocket complete 消息格式
7. 本地测试验收
