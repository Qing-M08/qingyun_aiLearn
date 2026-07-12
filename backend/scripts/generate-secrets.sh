#!/bin/bash
# =============================================================================
# 青云智学 - 生产环境密钥生成脚本
# 
# 用法：
#   bash scripts/generate-secrets.sh              # 生成所有密钥
#   bash scripts/generate-secrets.sh --dry-run    # 预览（不写入文件）
# =============================================================================

set -euo pipefail

SECRETS_DIR="$(cd "$(dirname "$0")/../secrets" && pwd)"
DRY_RUN=false

if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=true
    echo "=== 预览模式：不会写入任何文件 ==="
    echo ""
fi

generate_secret() {
    local name="$1"
    local length="${2:-64}"
    local value

    # 使用 openssl 生成随机十六进制字符串，然后 base64 编码
    value=$(openssl rand -hex "$length" | head -c "$length")

    if $DRY_RUN; then
        echo "  [DRY-RUN] ${name}.txt => ${value:0:16}...(截断)"
        return
    fi

    echo -n "$value" > "${SECRETS_DIR}/${name}.txt"
    chmod 600 "${SECRETS_DIR}/${name}.txt"
    echo "  ✓ 已生成: ${name}.txt"
}

echo "=== 青云智学密钥生成器 ==="
echo "输出目录: ${SECRETS_DIR}"
echo ""

# 应用密钥（64字符）
generate_secret "secret_key" 64
generate_secret "jwt_secret_key" 64

# 数据库密码（32字符）
generate_secret "postgres_password" 32

# Redis 密码（32字符）
generate_secret "redis_password" 32

# Meilisearch 主密钥（32字符）
generate_secret "meilisearch_master_key" 32

# LLM API Keys（如不填写真实值，后续需手动替换）
echo ""
echo "--- 以下 API Key 需手动填入真实值 ---"
for key_file in deepseek_api_key bing_search_api_key oss_access_key oss_secret_key; do
    if ! $DRY_RUN; then
        if [[ ! -f "${SECRETS_DIR}/${key_file}.txt" ]]; then
            echo "# 请替换为真实的 ${key_file}" > "${SECRETS_DIR}/${key_file}.txt"
            chmod 600 "${SECRETS_DIR}/${key_file}.txt"
            echo "  ⚠ 已创建占位: ${key_file}.txt（请手动填入真实值）"
        else
            echo "  - ${key_file}.txt 已存在，跳过"
        fi
    fi
done

echo ""
echo "=== 完成 ==="
echo "下一步："
echo "  1. 编辑 secrets/deepseek_api_key.txt 等文件，填入真实 API Key"
echo "  2. 复制 .env.production 为 .env"
echo "  3. 执行: docker compose up -d --build"
