#!/bin/sh
# =============================================================================
# Nginx 启动脚本 — 纯 IP 部署
#
# 环境变量：
#   SERVER_IP = 服务器公网 IP
#   USE_HTTPS = true（启用自签名 HTTPS）| 不设置（HTTP only）
# =============================================================================

set -e

SERVER_IP="${SERVER_IP:-}"
USE_HTTPS="${USE_HTTPS:-false}"
SSL_DIR="/etc/nginx/ssl"
CONF_TEMPLATE="/etc/nginx/nginx.conf.template"
CONF_OUTPUT="/etc/nginx/nginx.conf"

echo "============================================"
echo "  青云智学 Nginx 启动"
echo "  SERVER_IP : ${SERVER_IP:-（未设置）}"
echo "  USE_HTTPS : ${USE_HTTPS}"
echo "============================================"

# --- 生成基础 HTTP 配置 ---
cp "$CONF_TEMPLATE" "$CONF_OUTPUT"

# --- HTTPS 模式：生成自签名证书 + 追加 HTTPS server 块 ---
if [ "$USE_HTTPS" = "true" ]; then
    echo ""
    echo ">>> 启用 HTTPS（自签名证书）"

    mkdir -p "$SSL_DIR"

    # 生成自签名证书（如果不存在）
    if [ ! -f "${SSL_DIR}/server.crt" ] || [ ! -f "${SSL_DIR}/server.key" ]; then
        echo ">>> 生成自签名 SSL 证书（有效期 10 年）..."
        openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
            -keyout "${SSL_DIR}/server.key" \
            -out "${SSL_DIR}/server.crt" \
            -subj "/C=CN/ST=Beijing/L=Beijing/O=QingYun/OU=IT/CN=qingyun-server" \
            2>/dev/null
        chmod 600 "${SSL_DIR}/server.key"
        echo ">>> 证书已生成: ${SSL_DIR}/server.crt"
        echo ""
        echo "  ⚠ 重要：前端 EXE 需要信任此自签名证书，否则 HTTPS 连接会失败。"
        echo "    将 server.crt 复制到客户端并导入受信任的根证书存储区。"
        echo "    或者前端代码中配置跳过证书验证（仅开发/内网环境）。"
    else
        echo ">>> 证书已存在，跳过生成"
    fi

    # 追加 HTTPS server 块
    cat >> "$CONF_OUTPUT" << 'NGINX_HTTPS_BLOCK'

# ============================
# HTTPS 服务（自签名证书）
# ============================
server {
    listen 443 ssl http2;
    server_name _;

    ssl_certificate     /etc/nginx/ssl/server.crt;
    ssl_certificate_key /etc/nginx/ssl/server.key;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;

    client_max_body_size 50m;

    # API
    location /api/ {
        proxy_pass http://qingyun_app;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 300s;
    }

    # WebSocket — Agent 对话
    location /api/v1/ws/agent/ {
        proxy_pass http://qingyun_app;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
        proxy_buffering off;
    }

    # WebSocket — 其他
    location /api/v1/ws/ {
        proxy_pass http://qingyun_app;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
        proxy_buffering off;
    }

    location /ws/ {
        proxy_pass http://qingyun_app;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
        proxy_buffering off;
    }

    location /health {
        proxy_pass http://qingyun_app;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        access_log off;
    }

    location / {
        proxy_pass http://qingyun_app;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 300s;
    }
}
NGINX_HTTPS_BLOCK

    echo ">>> HTTPS 配置已追加"
else
    echo ">>> HTTP 模式（无 HTTPS）"
fi

# --- 清理占位符 ---
sed -i '/HTTPS_PLACEHOLDER/d' "$CONF_OUTPUT"

echo ""
echo ">>> Nginx 配置已生成，启动中..."
echo ""

# 验证配置
nginx -t -c "$CONF_OUTPUT"

# 启动 Nginx
exec nginx -g "daemon off;" -c "$CONF_OUTPUT"
