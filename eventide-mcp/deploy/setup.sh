#!/usr/bin/env bash
# VPS 一键部署脚本（Ubuntu/Debian）
# 用法：sudo bash setup.sh --domain eventide.alexmem.xyz --api-key 你的密钥

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

echo "==> 配置 nginx（先用 HTTP，certbot 会自动升级 HTTPS）"
cat > /etc/nginx/sites-available/eventide-mcp <<NGINX
server {
    listen 80;
    server_name ${DOMAIN};

    proxy_buffering off;
    proxy_cache off;

    location / {
        proxy_pass         http://127.0.0.1:8765;
        proxy_http_version 1.1;
        proxy_set_header   Connection "";
        proxy_set_header   Host \$host;
        proxy_set_header   X-Real-IP \$remote_addr;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
NGINX

ln -sf /etc/nginx/sites-available/eventide-mcp /etc/nginx/sites-enabled/eventide-mcp
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo "==> 申请 Let's Encrypt 证书（自动配置 HTTPS）"
certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos -m "admin@${DOMAIN}"

# certbot 升级为 HTTPS 后，补上 SSE 必需的长连接头
sed -i '/proxy_pass/a\        proxy_read_timeout 3600s;\n        proxy_send_timeout 3600s;' \
  /etc/nginx/sites-available/eventide-mcp 2>/dev/null || true
nginx -t && systemctl reload nginx

echo ""
echo "✓ 部署完成！"
echo "  SSE 端点:  https://${DOMAIN}/sse"
echo "  API Key:   ${API_KEY}"
echo ""
echo "在 Claude.ai Settings → Connectors → Add custom connector 填入上面两项即可。"
