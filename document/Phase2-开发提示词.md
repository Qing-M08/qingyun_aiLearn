# Phase 2 开发提示词

> 用途：将此提示词提供给AI编程助手，即可逐步完成Phase 2全部开发。
> 配合 `Phase2-核心功能完善-P1-青云智学后端开发文档.md` 使用。

---

## 系统角色设定

你是一位资深Python后端工程师，精通FastAPI + SQLAlchemy + Celery + PostgreSQL技术栈。你正在为「青云智学」在线教育平台开发Phase 2（Sprint 5-7）的三大核心功能：知识图谱驱动的学习路线、苏格拉底式智能答疑、SM-2间隔重复复习系统。

---

## 项目背景

### 技术栈
- **框架**: FastAPI (async)
- **ORM**: SQLAlchemy 2.0 (async, Mapped 类型声明式)
- **数据库**: PostgreSQL 16 + Apache AGE (图数据库扩展)
- **缓存/消息**: Redis (缓存 + Celery broker + pub/sub)
- **异步任务**: Celery + Celery Beat
- **LLM**: DeepSeek API (OpenAI兼容接口)
- **认证**: JWT (python-jose)
- **日志**: structlog
- **向量检索**: sentence-transformers (bge-m3)

### 项目目录结构（Phase 1已完成）
```
backend/app/
├── agent/              # Agent模块（Phase 3实现）
├── ai/
│   ├── prompts/        # Prompt模板
│   │   ├── lecture.py  # 讲义生成Prompt
│   │   └── summary.py  # 个性化摘要Prompt
│   ├── rag/            # RAG管道
│   │   ├── chunking.py
│   │   └── embedding.py
│   ├── web_search/     # 网络搜索
│   ├── llm_client.py   # LLM客户端（返回LLMResponse对象）
│   └── llm_router.py
├── api/v1/
│   ├── auth.py         # 认证路由
│   ├── learning.py     # 学习路由（Phase 1简化版，需升级）
│   ├── notes.py        # 笔记路由
│   ├── tags.py         # 标签路由
│   ├── users.py        # 用户路由
│   ├── websocket.py    # WebSocket端点
│   └── router.py       # 路由注册
├── core/
│   ├── exceptions.py   # 自定义异常（NotFoundException等）
│   ├── middleware.py
│   ├── security.py
│   └── utils.py
├── models/
│   ├── knowledge.py    # KnowledgeNode, KnowledgeEdge, UserKnowledgeMastery
│   ├── learning.py     # LearningRoute, LearningRouteStep, Lecture, LearningRecord, QASession, QAMessage
│   ├── review.py       # ReviewPlan
│   └── ...
├── schemas/
│   ├── common.py       # PaginatedResponse, MessageResponse
│   ├── note.py
│   └── user.py
├── services/
│   ├── learning_service.py  # Phase 1简化版（需升级）
│   └── ...
├── tasks/
│   ├── celery_app.py   # Celery配置
│   └── lecture_tasks.py # 讲义生成任务
├── config.py           # Settings (pydantic-settings)
├── database.py         # async engine + session
└── main.py
```

### 关键代码约定（必须遵循）

1. **ORM模型** — 使用 `Mapped` 类型 + `mapped_column`，字段命名snake_case：
   ```python
   class SomeModel(Base):
       __tablename__ = "some_models"
       id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
       metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)  # metadata字段映射
   ```

2. **LLM调用** — `get_llm_client()` 返回 `LLMClient` 单例，`chat()` 返回 `LLMResponse` 对象：
   ```python
   llm = get_llm_client()
   response = await llm.chat(messages=[...], temperature=0.7, max_tokens=4096)
   # response.content 是字符串, response.usage 是dict
   ```

3. **异常处理** — 使用自定义异常类：
   ```python
   from app.core.exceptions import NotFoundException, BadRequestException, ConflictException
   ```

4. **依赖注入** — 数据库和认证用户：
   ```python
   db: AsyncSession = Depends(get_db)
   current_user: User = Depends(get_current_user)
   ```

5. **Celery任务** — 使用 `run_async` 辅助函数运行异步代码：
   ```python
   def run_async(coro):
       loop = asyncio.new_event_loop()
       try:
           return loop.run_until_complete(coro)
       finally:
           loop.close()
   ```

6. **路由前缀** — 各路由模块自带 `prefix` 和 `tags`，`router.py` 中不再重复添加前缀（注意：当前 `router.py` 在 include_router 时添加了 prefix，新路由需与此保持一致或调整）

---

## Phase 1 遗留技术债（本阶段解决）

- `learning_service.py` 的 `create_route` 是简化版（直接创建空路线），需升级为LLM+知识图谱驱动
- `learning.py` 路由使用内联Pydantic模型，需迁移到独立schema文件
- WebSocket连接管理器不支持按前缀广播
- 复习系统未实现

---

## 开发任务（按Sprint顺序执行）

### ⚡ Sprint 5：学习路线与知识图谱

#### 任务5.1：创建 Pydantic Schemas

**新建文件**: `app/schemas/knowledge.py`
- `KnowledgeNodeSchema` — 知识节点响应（id, subject, name, description, grade_level, difficulty, metadata, created_at, updated_at）
- `KnowledgeNodeCreate` — 创建请求（subject, name, description?, grade_level?, difficulty 1-5, metadata?）
- `KnowledgeNodeUpdate` — 更新请求（所有字段可选）
- `KnowledgeEdgeSchema` — 边响应（id, source_id, target_id, relation_type, weight, metadata, created_at）
- `KnowledgeEdgeCreate` — 创建请求（source_id, target_id, relation_type 正则校验 prerequisite|related|subtopic|parent, weight 0-10）
- `KnowledgeGraphResponse` — 图结构响应（node + prerequisites/dependents/related列表 + user_mastery）
- `LearningPathResponse` — 路径响应（path节点列表 + total_difficulty）
- `UserMasterySchema` — 掌握度响应
- `SubjectSchema` — 学科信息（name, display_name, node_count）
- `GraphNodeCypher`, `GraphEdgeCypher` — AGE图查询结果

**新建文件**: `app/schemas/learning.py`
- `LearningRouteCreate` — 路线创建请求（topic, goal?, available_hours?, current_level?, preferences?）
- `LearningRouteSchema` — 路线响应（含steps列表）
- `LearningRouteStepSchema` — 步骤响应
- `RouteStepComplete` — 步骤完成请求（duration_seconds?, notes?）
- `LectureGenerateRequest` — 讲义生成请求（route_id, step_id, node_id?, custom_instructions?）
- `LectureSchema` — 讲义响应
- `LectureGenerateResponse` — 讲义生成响应（lecture_id, status）
- `RouteGenerationLLMResponse`, `RouteStepLLM` — LLM返回的路线JSON结构

#### 任务5.2：创建 Apache AGE 图数据库封装层

**新建文件**: `app/services/graph_db.py`
- `GraphDB` 静态方法类，封装AGE Cypher查询
- `GRAPH_NAME = "knowledge_graph"`
- 核心方法：
  - `execute_cypher(db, cypher, params, columns)` — 执行读Cypher查询，SQL包装为 `SELECT * FROM cypher('graph_name', $$ ... $$) as (columns)`
  - `execute_cypher_write(db, cypher, params)` — 执行写Cypher
  - `ensure_graph_exists(db)` — 检查/创建图
  - `create_knowledge_node_in_graph(db, node_id, name, subject, ...)` — 在AGE中创建节点
  - `create_knowledge_edge_in_graph(db, source_id, target_id, relation_type, weight)` — 创建边，映射关系类型：prerequisite→PREREQUISITE_OF, related→RELATED_TO, subtopic→SUBTOPIC_OF, parent→BELONGS_TO
  - `get_prerequisites(db, node_id)` — 获取前置依赖
  - `get_dependents(db, node_id)` — 获取后续依赖
  - `get_related(db, node_id)` — 获取关联节点
  - `get_subtopics(db, node_id)` — 获取子知识点
  - `find_shortest_path(db, source_id, target_id)` — 最短路径
  - `get_nodes_by_subject(db, subject)` — 按学科查节点
  - `get_nodes_with_prerequisites(db, subject)` — 查节点及前置依赖（用于路线生成）
- `_parse_agtype_row(row)` — 解析AGE返回的agtype数据

#### 任务5.3：创建知识图谱服务

**新建文件**: `app/services/knowledge_service.py`
- `KnowledgeService` 静态方法类
- 节点CRUD：`create_node`（创建后同步到AGE图，AGE失败不阻塞）, `get_node`, `list_nodes`（支持subject/grade_level/search筛选+分页）, `update_node`
- 边CRUD：`create_edge`（创建后同步到AGE图）
- 图查询：`get_node_graph`（从AGE查前置/后续/关联节点，降级到关系表查询，含用户掌握度）
- 路径查询：`get_learning_path`（调用GraphDB.find_shortest_path）
- 学科列表：`get_subjects`（含中文display_name映射）
- 掌握度管理：`get_or_create_mastery`, `update_mastery_score`（指数移动平均：正确 mastery += (1-mastery)*0.3, 错误 mastery *= 0.7）
- 初始数据导入：`import_initial_data`

#### 任务5.4：升级学习引擎服务

**升级文件**: `app/services/learning_service.py`（完全重写）
- `create_route` — 创建路线记录(status="generating") → 异步触发Celery任务 `generate_learning_route`
- `generate_route_with_llm` — 由Celery任务调用：
  1. 获取用户已掌握知识点（mastery_score > 0.5）
  2. 推断学科（`_infer_subject` 关键词匹配）
  3. 从知识图谱获取节点及前置依赖（AGE失败降级到关系表）
  4. 构建Prompt（使用 `ROUTE_GENERATION_PROMPT`）
  5. 调用LLM
  6. 解析JSON响应（`_parse_route_response`，支持从markdown代码块提取）
  7. 更新路线记录 + 创建步骤
  8. WebSocket推送完成通知
- `get_route`, `get_user_routes` — 查询路线
- `complete_step` — 标记步骤完成：
  - 记录学习活动（LearningRecord）
  - 更新知识掌握度
  - 根据表现动态调整：用时/预估>2 → `_adjust_for_struggling`（添加补充练习步骤）；<0.5 → `_adjust_for_excelling`（合并后续步骤）
- `create_lecture` — 创建讲义 + 触发异步生成
- `generate_lecture_content` — 由Celery调用：获取知识节点上下文 → RAG检索 → 构建Prompt → LLM生成 → WebSocket推送进度
- `as_tools()` — Agent工具接口

#### 任务5.5：创建Prompt模板

**新建文件**: `app/ai/prompts/route.py`
- `ROUTE_GENERATION_PROMPT` — 学习路线生成Prompt，包含学生信息（水平、已掌握知识点、目标、可用时间）、学习主题、可用知识点（含前置依赖），要求输出JSON格式（title, description, estimated_total_hours, steps数组）

#### 任务5.6：创建Celery异步任务

**新建文件**: `app/tasks/learning_tasks.py`（注意：当前已有 `tasks/lecture_tasks.py`，这是新文件）
- `generate_learning_route` — 异步生成学习路线，调用 `LearningService.generate_route_with_llm`
- `generate_lecture_task` — 异步生成讲义（升级版，支持node_id和custom_instructions参数）

#### 任务5.7：创建知识图谱API路由

**新建文件**: `app/api/v1/knowledge.py`
- `GET /knowledge/subjects` — 获取学科列表
- `GET /knowledge/nodes` — 查询知识节点（分页+筛选）
- `POST /knowledge/nodes` — 创建知识节点
- `GET /knowledge/nodes/{node_id}/graph` — 获取节点图结构
- `GET /knowledge/nodes/{node_id}/path?target_id=xxx` — 获取学习路径
- `POST /knowledge/edges` — 创建知识边

#### 任务5.8：升级学习路由

**升级文件**: `app/api/v1/learning.py`
- 使用 `app/schemas/learning.py` 中的Schema替换内联模型
- `POST /routes` — 使用 `LearningRouteCreate` Schema，返回 `LearningRouteSchema`
- `GET /routes` — 新增列表接口
- `GET /routes/{route_id}` — 使用 `LearningRouteSchema`
- `PATCH /routes/{route_id}/steps/{step_id}/complete` — 新增步骤完成接口（触发路线动态调整）
- `POST /lectures/generate` — 使用新 `LectureGenerateRequest`
- `GET /lectures/{lecture_id}` — 使用 `LectureSchema`

#### 任务5.9：升级WebSocket

**升级文件**: `app/api/v1/websocket.py`
- `ConnectionManager` 升级：
  - `send_json` 增加异常处理（发送失败自动disconnect）
  - 新增 `broadcast_to_prefix(prefix, data)` — 向匹配前缀的所有连接广播
- 升级 `/ws/lecture-progress/{lecture_id}` — 注册到manager，支持Redis pub/sub
- 新增端点（Sprint 6/7会用到，此处预留结构）

#### 任务5.10：更新路由注册

**升级文件**: `app/api/v1/router.py`
- 新增 `from app.api.v1 import knowledge`
- `api_router.include_router(knowledge.router)` — 知识图谱路由

#### Sprint 5 验收标准
- [ ] GET /api/v1/knowledge/subjects 返回学科列表
- [ ] GET /api/v1/knowledge/nodes?subject=math 返回节点列表（分页）
- [ ] POST /api/v1/knowledge/nodes 创建节点并同步到AGE图
- [ ] GET /api/v1/knowledge/nodes/{id}/graph 返回图结构
- [ ] GET /api/v1/knowledge/nodes/{id}/path?target_id=xxx 返回最短路径
- [ ] POST /api/v1/learning/routes 创建路线后Celery异步生成步骤
- [ ] PATCH .../steps/{id}/complete 标记完成+动态调整
- [ ] POST /api/v1/learning/lectures/generate 异步生成讲义
- [ ] WebSocket推送讲义进度

---

### ⚡ Sprint 6：智能答疑

#### 任务6.1：创建 Pydantic Schemas

**新建文件**: `app/schemas/qa.py`
- `QASessionCreate` — 创建请求（lecture_id?, node_id?, topic?）
- `QASessionSchema` — 会话响应
- `QAMessageCreate` — 消息请求（content 1-5000字）
- `QAMessageSchema` — 消息响应（id, session_id, role, content, metadata, created_at）
- `QAMessagePair` — 发送消息响应（user_message + assistant_message）
- `DiagnosticQuestion` — 诊断性问题（type choice|short_answer, question, options?, correct_answer, explanation, target_concept, difficulty）
- `DiagnosticQuestionsResponse` — 诊断问题列表
- `QASessionListResponse` — 会话列表

#### 任务6.2：创建Prompt模板

**新建文件**: `app/ai/prompts/qa.py`
- `QA_SYSTEM_PROMPT` — 苏格拉底式答疑系统Prompt：
  - 不直接给答案，通过提问引导
  - 使用类比和生活例子
  - 回答正确→肯定+更深问题；回答错误→新引导问题
  - 每次回复200字以内
  - 变量：{node_name}, {lecture_summary}, {mastery_score}

**新建文件**: `app/ai/prompts/diagnosis.py`
- `DIAGNOSIS_PROMPT` — 诊断性问题生成Prompt：
  - 生成3-5个诊断性问题
  - 覆盖不同认知层次（记忆、理解、应用、分析）
  - 输出JSON格式（questions数组）
  - 变量：{lecture_summary}, {node_name}, {mastery_score}

#### 任务6.3：创建智能答疑服务

**新建文件**: `app/services/qa_service.py`
- `QAService` 静态方法类
- 会话管理：`create_session`, `get_session`（含messages关系加载）, `list_sessions`（分页）, `close_session`
- 消息处理（苏格拉底式）：`handle_message`
  1. 保存用户消息
  2. 构建上下文（`_build_context`：获取知识节点名称、掌握度、讲义摘要 → 填充QA_SYSTEM_PROMPT）
  3. 构建消息列表（system + 最近10轮历史）
  4. 调用LLM
  5. 保存AI回复
  6. 分析用户回答质量更新掌握度（`_analyze_and_update_mastery`：LLM评分0-1 → 更新mastery_score）
- 流式消息：`handle_message_stream` — 通过WebSocket逐token推送
  - `llm.chat_stream()` 需返回异步生成器（每个token一个字符串）
  - 推送类型：token（逐token）、done（完成）、diagnosis（掌握度变化）
- 诊断性问题：`generate_diagnostic_questions` — 基于讲义+掌握度生成
- 消息历史：`get_messages`（支持before游标分页）
- Agent工具：`create_qa_session`

#### 任务6.4：升级LLM客户端（添加流式支持）

**升级文件**: `app/ai/llm_client.py`
- 新增 `chat_stream` 异步生成器方法：
  ```python
  async def chat_stream(self, messages, temperature, max_tokens) -> AsyncGenerator[str, None]:
      # 使用OpenAI stream=True，逐chunk yield content
  ```

#### 任务6.5：创建答疑API路由

**新建文件**: `app/api/v1/qa.py`
- `POST /learning/qa/sessions` — 创建答疑会话
- `GET /learning/qa/sessions` — 会话列表
- `POST /learning/qa/sessions/{session_id}/messages` — 发送消息（非流式）
- `GET /learning/qa/sessions/{session_id}/messages` — 历史消息
- `POST /learning/qa/diagnostic-questions?lecture_id=xxx` — 生成诊断性问题

#### 任务6.6：升级WebSocket（答疑流端点）

**升级文件**: `app/api/v1/websocket.py`
- 新增 `/ws/qa-stream/{session_id}`：
  - 验证token
  - 注册到manager（client_id = `qa_{session_id}`）
  - 接收消息（type="message"）→ 调用 `QAService.handle_message_stream`
  - 支持ping/pong心跳

#### 任务6.7：更新路由注册

**升级文件**: `app/api/v1/router.py`
- 新增 `from app.api.v1 import qa`
- `api_router.include_router(qa.router)`

#### Sprint 6 验收标准
- [ ] POST /api/v1/learning/qa/sessions 创建答疑会话
- [ ] POST .../messages 发送消息获取苏格拉底式回复
- [ ] AI回复体现引导风格（不直接给答案）
- [ ] GET .../messages 获取历史消息（分页）
- [ ] POST /diagnostic-questions 生成诊断性问题
- [ ] WebSocket /ws/qa-stream/{id} 流式输出
- [ ] 答疑中自动分析回答质量并更新掌握度
- [ ] 掌握度变化通过WebSocket推送

---

### ⚡ Sprint 7：复习系统

#### 任务7.1：创建 Pydantic Schemas

**新建文件**: `app/schemas/review.py`
- `ReviewPlanSchema` — 复习计划响应（含node_name, node_subject可选字段）
- `ReviewCompleteRequest` — 完成请求（performance 0-1?, notes?）
- `ReviewContentRequest` — 内容生成请求（node_id, review_type? flashcard|quiz|explanation）
- `ReviewContentResponse` — 内容响应（content, type, node_name）
- `ReviewStatsResponse` — 统计响应（today_due, this_week_completed, overdue_count, mastery_distribution）
- `ReviewPlanListResponse` — 列表响应

#### 任务7.2：创建Prompt模板

**新建文件**: `app/ai/prompts/review.py`
- `REVIEW_GENERATION_PROMPT` — 复习内容生成Prompt：
  - 变量：{node_name}, {mastery_score}, {review_count}, {last_performance}, {review_strategy}
  - 根据复习类型输出：flashcard(3-5张闪卡), quiz(3-5道题), explanation(重新讲解+练习)

#### 任务7.3：创建复习服务

**新建文件**: `app/services/review_service.py`
- `ReviewService` 静态方法类
- SM-2算法：
  - `calculate_next_review(mastery, quality_rating)` — 核心算法：
    - quality >= 3: interval递增（0→1→6→round(interval*ef)），ef更新
    - quality < 3: interval重置为1，ef降低0.2（最低1.3）
  - `quality_from_performance(performance)` — 0-1分数转0-5质量评分
- 复习计划管理：
  - `schedule_review` — 创建/更新复习计划
  - `get_review_plans` — 列表（含节点名称批量查询，支持status/日期范围筛选+分页）
  - `complete_review` — 完成复习：标记completed → SM-2计算 → 更新掌握度 → 自动创建下次计划
- 复习统计：`get_review_stats`（今日到期、本周完成、逾期数、掌握度分布）
- 复习内容生成：`generate_review_content`
  - 根据掌握度自动选择类型：>0.7→flashcard, 0.4-0.7→quiz, <0.4→explanation
  - 调用LLM生成
- 到期检查：`check_due_reviews` — Celery Beat调用
- Agent工具：`get_review_plans`, `generate_review_content`

#### 任务7.4：创建Celery任务 + 配置Beat

**新建文件**: `app/tasks/review_tasks.py`
- `check_review_reminders` — 定时检查到期复习计划，通过WebSocket推送提醒

**升级文件**: `app/tasks/celery_app.py`
- 添加 `beat_schedule` 配置：
  ```python
  celery_app.conf.beat_schedule = {
      "check-review-reminders": {
          "task": "app.tasks.review_tasks.check_review_reminders",
          "schedule": 300.0,  # 每5分钟
      },
  }
  ```

#### 任务7.5：创建复习API路由

**新建文件**: `app/api/v1/review.py`
- `GET /review/plans` — 复习计划列表（筛选+分页）
- `POST /review/plans/{plan_id}/complete` — 完成复习（SM-2重算）
- `POST /review/generate-content` — 生成复习内容
- `GET /review/stats` — 复习统计

#### 任务7.6：升级WebSocket（通知端点）

**升级文件**: `app/api/v1/websocket.py`
- 升级 `/ws/notifications` — 使用 `user_{user_id}` 作为client_id，支持按用户推送复习提醒

#### 任务7.7：更新路由注册

**升级文件**: `app/api/v1/router.py`
- 新增 `from app.api.v1 import review`
- `api_router.include_router(review.router)`

#### Sprint 7 验收标准
- [ ] GET /api/v1/review/plans 返回复习计划列表
- [ ] POST .../complete 完成复习，SM-2正确计算下次时间
- [ ] SM-2: quality>=3间隔递增，<3重置为1天
- [ ] 完成后自动创建下次复习计划
- [ ] POST /generate-content 根据掌握度选择复习形式
- [ ] GET /stats 返回统计数据
- [ ] Celery Beat每5分钟检查到期复习
- [ ] WebSocket推送复习提醒

---

## Phase 2 整体验收（端到端流程）

1. **知识图谱驱动学习路线**：创建路线 → Celery异步LLM+图谱生成步骤 → WebSocket推送 → 查看路线详情
2. **路线动态调整**：完成步骤 → 表现不佳加练习 → 表现优秀合并步骤
3. **讲义生成升级**：触发生成 → RAG+图谱上下文 → LLM生成 → WebSocket进度
4. **苏格拉底式答疑**：创建会话 → 发送问题 → AI引导式回复 → 流式WebSocket → 更新知识画像
5. **诊断性问题**：基于讲义生成 → 选择+简答混合 → 不同认知层次
6. **SM-2复习系统**：到期提醒 → 完成复习 → SM-2计算 → 生成复习内容
7. **知识图谱API**：学科列表 → 节点查询 → 图结构 → 学习路径
8. **Agent工具**：所有服务暴露的工具接口可调用

---

## 技术约束与注意事项

1. **LLM返回值**：`llm.chat()` 返回 `LLMResponse` 对象，用 `response.content` 获取文本内容（文档中部分代码直接用 `response` 作为字符串，需适配）
2. **metadata字段**：ORM中映射为 `metadata_` → 数据库列名 `metadata`
3. **AGE图同步**：知识节点/边创建时同步写入AGE图，AGE失败不阻塞主流程（仅warning日志）
4. **WebSocket连接管理器**：需升级为支持 `broadcast_to_prefix` 和异常安全的 `send_json`
5. **Celery任务中的DB会话**：使用 `async_session_factory()` 创建独立会话，任务内手动 `commit`
6. **路由前缀一致性**：当前 `router.py` 在 `include_router` 时添加 prefix，新路由模块如果自带 prefix 则不需要在 router.py 重复添加。请根据文档中各路由的 `APIRouter(prefix=...)` 设置来决定
7. **chat_stream方法**：Sprint 6需要LLM客户端支持流式输出（异步生成器），需在 `llm_client.py` 中新增

---

## 详细代码参考

完整的代码实现请参考 `Phase2-核心功能完善-P1-青云智学后端开发文档.md`，其中包含每个文件的完整代码。按Sprint顺序逐个文件实现即可。
