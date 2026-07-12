# ========== 构建阶段 ==========
FROM python:3.11-slim AS builder

WORKDIR /app

# 安装构建所需的系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件，利用 Docker 缓存层
COPY pyproject.toml .

# 安装 Python 依赖到 /install 目录（不包含 dev 依赖）
RUN pip install --no-cache-dir --prefix=/install .

# ========== 生产阶段 ==========
FROM python:3.11-slim AS production

# 安装运行时系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 创建非 root 用户（安全加固）
RUN groupadd -r qingyun && useradd -r -g qingyun -d /app -s /sbin/nologin qingyun

WORKDIR /app

# 从构建阶段复制已安装的包
COPY --from=builder /install /usr/local

# 复制应用代码
COPY --chown=qingyun:qingyun . .

# 创建必要的目录并设置权限
RUN mkdir -p /app/logs && chown -R qingyun:qingyun /app

# 切换到非 root 用户
USER qingyun

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 暴露端口
EXPOSE 8000

# 使用 exec 形式确保信号正确传递
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
