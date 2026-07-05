#!/usr/bin/env bash
# VPS 一键部署脚本（Ubuntu/Debian）
# 用法：sudo bash setup.sh --domain mcp.你的域名.com --api-key 你的密钥

set -euo pipefail

DOMAIN=""
API_KEY=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --domain) DOMAIN="$2"; shift 2 ;;
    --api-key) API_KEY="$2"; shift 2 ;;
    *) echo "未知参数: $1"; exit 1 ;;
  esac
done

[[ -z "$DOMAIN" ]] && { echo "请指定 --domain"; exit 1; }
[[ -z "$API_KEY" ]] && { echo "请指定 --api-key"; exit 1; }

echo "==> 安装系统依赖"
apt-get update -qq
apt-get install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx git

echo "==> 创建用户和目录"
id -u eventide &>/dev/null || useradd -r -s /bin/false -m -d /opt/eventide-mcp eventide
mkdir -p /opt/eventide-mcp
chown eventide:eventide /opt/eventide-mcp

echo "==> 安装 eventide-mcp"
python3 -m venv /opt/eventide-mcp/.venv
/opt/eventide-mcp/.venv/bin/pip install -q \
  "git+https://github.com/kipfritsch8-sketch/Alex.git#subdirectory=eventide-mcp"

echo "==> 写入环境变量"
cat > /etc/eventide-mcp.env <<EOF
EVENTIDE_API_KEY=${API_KEY}
EOF
chmod 600 /etc/eventide-mcp.env

echo "==> 安装 systemd service"
cp "$(dirname "$0")/eventide-mcp.service" /etc/systemd/system/eventide-mcp.service
systemctl daemon-reload
systemctl enable --now eventide-mcp

echo "==> 配置 nginx"
sed "s/mcp.你的域名.com/${DOMAIN}/g" "$(dirname "$0")/nginx.conf" \
  > /etc/nginx/sites-available/eventide-mcp
ln -sf /etc/nginx/sites-available/eventide-mcp /etc/nginx/sites-enabled/eventide-mcp
nginx -t && systemctl reload nginx

echo "==> 申请 Let's Encrypt 证书"
certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos -m "admin@${DOMAIN}"

echo ""
echo "✓ 部署完成！"
echo "  SSE 端点: https://${DOMAIN}/sse"
echo "  Claude Desktop 配置中 api_key 填: ${API_KEY}"
