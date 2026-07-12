# ========== 构建阶段 ==========
FROM python:3.11-slim AS builder

WORKDIR /app

# 安装构建所需的系统依赖（使用国内 Debian 镜像源加速）
RUN sed -i "s@http://deb.debian.org@https://mirrors.aliyun.com@g" /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制 pyproject.toml 和预下载的 wheel 包
COPY pyproject.toml .
COPY wheels/ /wheels/

# 从本地 wheel 安装全部依赖（零网络，几秒完成）
RUN pip install --no-cache-dir --no-index \
        --find-links=/wheels/ \
        --prefix=/install . && \
    # 清理测试文件、缓存
    find /install -type d -name "tests" -exec rm -rf {} + 2>/dev/null; \
    find /install -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null; \
    find /install -name "*.pyc" -delete 2>/dev/null; \
    find /install -name "*.pyo" -delete 2>/dev/null; \
    rm -rf /root/.cache/pip /wheels/

# ========== 生产阶段 ==========
FROM python:3.11-slim AS production

# 安装运行时系统依赖（使用国内 Debian 镜像源加速）
RUN sed -i "s@http://deb.debian.org@https://mirrors.aliyun.com@g" /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 创建非 root 用户（安全加固）
RUN groupadd -r qingyun && useradd -r -g qingyun -d /app -s /sbin/nologin qingyun

WORKDIR /app

# 从构建阶段复制已安装的包
COPY --from=builder /install /usr/local

# 兜底清理：移除任何可能残留的 CUDA/nvidia 目录
RUN find /usr/local -type d \( -name "nvidia" -o -name "cu13" -o -name "cuda" \) \
        -exec rm -rf {} + 2>/dev/null

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
