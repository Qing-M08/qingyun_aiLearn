# 青云智学 (QingYun ZhiXue)

> AI 驱动的全流程学习辅助软件

青云智学是一款面向个人学习者的智能学习助手，覆盖**笔记管理 → AI 讲义生成 → 智能答疑 → 间隔复习 → 知识图谱**的完整学习闭环。

## 核心功能

| 模块 | 说明 |
|------|------|
| 📝 **笔记管理** | 富文本笔记 CRUD，标签系统，全文搜索 |
| 📖 **AI 讲义生成** | 基于笔记内容，自动生成结构化学习讲义 |
| 💬 **智能答疑** | RAG 增强的上下文问答，支持 WebSocket 流式输出 |
| 🔁 **间隔复习** | 基于遗忘曲线的智能复习调度 |
| 🧠 **AI Agent** | 多轮对话 Agent，支持工具调用（搜索/笔记/答疑/复习） |
| 🌐 **网络检索** | Trafilatura 网页抓取 + LLM 摘要，拓宽学习资料边界 |
| 👤 **用户画像** | 双层记忆系统（习惯画像 + 知识画像），个性化学习推荐 |
| 📚 **知识管理** | 知识条目管理，关联笔记，构建个人知识库 |
| 🔍 **混合搜索** | Meilisearch 全文搜索 + pgvector 语义搜索 |

## 技术栈

### 后端

| 类别 | 技术 |
|------|------|
| **Web 框架** | FastAPI（异步模式） |
| **ORM** | SQLAlchemy 2.0 + asyncpg |
| **数据库** | PostgreSQL 16 + pgvector（向量存储） |
| **缓存/队列** | Redis 7 + Celery |
| **搜索引擎** | Meilisearch |
| **LLM** | DeepSeek / Qwen / Anthropic / OpenAI（可切换） |
| **嵌入模型** | BGE 系列（sentence-transformers） |
| **认证** | JWT（python-jose）+ bcrypt |
| **日志** | structlog |
| **Web 抓取** | Trafilatura（Apache 2.0） |

### 基础设施

| 组件 | 说明 |
|------|------|
| **容器化** | Docker Compose 一键部署 |
| **反向代理** | Nginx（支持 HTTPS 自签名证书） |
| **数据库迁移** | Alembic |
| **任务队列** | Celery Worker + Celery Beat |

## 项目结构

```
qingyun_aiLearn/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 应用入口
│   │   ├── config.py            # 配置管理（支持 Docker secrets）
│   │   ├── database.py          # 数据库连接
│   │   ├── api/v1/              # REST API 路由
│   │   │   ├── auth.py          # 认证接口
│   │   │   ├── notes.py         # 笔记接口
│   │   │   ├── learning.py      # 学习/讲义接口
│   │   │   ├── qa.py            # 智能答疑接口
│   │   │   ├── review.py        # 复习接口
│   │   │   ├── agent.py         # AI Agent 接口
│   │   │   ├── search.py        # 搜索接口
│   │   │   ├── knowledge.py     # 知识管理接口
│   │   │   └── websocket.py     # WebSocket 端点
│   │   ├── models/              # SQLAlchemy ORM 模型
│   │   ├── schemas/             # Pydantic 数据模型
│   │   ├── services/            # 业务逻辑层
│   │   │   ├── agent/           # Agent 编排、工具注册
│   │   │   └── memory/          # 用户记忆系统
│   │   ├── ai/                  # AI 相关
│   │   │   ├── llm_client.py    # LLM 客户端适配
│   │   │   ├── llm_router.py    # LLM 路由
│   │   │   ├── prompts/         # 提示词模板
│   │   │   ├── rag/             # RAG 分块/嵌入
│   │   │   └── web_search/      # 网络检索
│   │   ├── tasks/               # Celery 异步任务
│   │   └── core/                # 核心工具（安全/中间件/异常）
│   ├── alembic/                 # 数据库迁移
│   ├── nginx/                   # Nginx 配置
│   ├── tests/                   # 测试
│   ├── secrets/                 # 敏感配置（模板）
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── docker-compose.yml
└── document/                    # 开发文档
```

## 快速开始

### 环境要求

- Docker & Docker Compose
- Python 3.11+（本地开发）

### 1. 准备密钥

```bash
cd backend

# 创建 secrets 目录并生成随机密钥
mkdir -p secrets
openssl rand -hex 32 > secrets/secret_key.txt
openssl rand -hex 32 > secrets/jwt_secret_key.txt
openssl rand -hex 16 > secrets/postgres_password.txt
openssl rand -hex 16 > secrets/redis_password.txt
openssl rand -hex 16 > secrets/meilisearch_master_key.txt

# 填入你的 LLM API Key
echo "your-deepseek-api-key" > secrets/deepseek_api_key.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 按需编辑 .env（默认配置即可用于 Docker 部署）
```

### 3. 启动服务

```bash
# 启动全部基础设施 + 应用
docker compose up -d

# 执行数据库迁移（首次启动）
docker compose --profile migration up alembic

# 查看服务状态
docker compose ps
```

### 4. 访问

| 服务 | 地址 |
|------|------|
| API | `http://localhost:8000` |
| Swagger 文档 | `http://localhost:8000/docs` |
| 健康检查 | `http://localhost:8000/health` |
| Meilisearch | `http://localhost:7700` |

### 本地开发

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 启动基础设施（仅数据库/缓存/搜索）
docker compose up -d postgres redis meilisearch

# 启动开发服务器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 代码检查
ruff check app/
mypy app/
```

## API 概览

| 路径前缀 | 说明 |
|----------|------|
| `POST /api/v1/auth/register` | 用户注册 |
| `POST /api/v1/auth/login` | 用户登录 |
| `GET/POST /api/v1/notes` | 笔记管理 |
| `GET/POST /api/v1/notes/{id}/lectures` | 讲义生成 |
| `POST /api/v1/qa/ask` | 智能答疑 |
| `GET /api/v1/review/today` | 今日复习任务 |
| `POST /api/v1/agent/chat` | Agent 对话 |
| `GET /api/v1/search/?q=关键词` | 混合搜索 |
| `GET /api/v1/knowledge` | 知识管理 |
| `WS /ws/organize-progress/{task_id}` | 笔记整理进度推送 |

## 许可协议

本项目基于 [MIT License](LICENSE) 开源。

---

> 本项目借助 AI 编程助手辅助开发，所有设计决策和代码审核由人类主导完成。
