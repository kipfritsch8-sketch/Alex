# Eventide MCP 服务器

把 [Eventide](https://github.com/chuli1122/Eventide) 身体状态系统包装成 MCP 服务器（Streamable HTTP），可作为 claude.ai 的自定义 Connector 接入。

## 工具列表

| 工具 | 作用 |
|---|---|
| `body_tick` | 推进状态到当前时间，返回隐藏状态卡（每次会话开始调一次） |
| `body_status` | 查看原始数值，不推进时间 |
| `body_reset` | 重置状态，可指定起始周期 |
| `body_start_event` | 手动触发短时事件（18 类） |
| `body_enter_cycle` | 强制切换周期 |
| `settlement_prompt` | 生成互动结算 prompt |
| `settlement_apply` | 应用结算结果 JSON |
| `dream_check` | 尝试触发梦境（受深夜窗口/沉默/冷却限制），返回梦境生成指引 |
| `dream_apply_tags` | 应用梦后标签，把梦的影响结算回身体 |
| `trigger_word_set` | 设置称呼触发词表 |
| `trigger_check` | 检测消息是否命中触发词 |

状态保存在服务器上的 `eventide_state.json`，跨会话持续。

## VPS 部署

以 Debian/Ubuntu + Caddy 为例，假设域名为 `eventide.example.com`：

```bash
# 1. 放代码
sudo mkdir -p /opt/eventide-mcp
sudo cp server.py requirements.txt /opt/eventide-mcp/
cd /opt/eventide-mcp

# 2. 虚拟环境 + 依赖
sudo python3 -m venv venv
sudo venv/bin/pip install -r requirements.txt
sudo chown -R www-data:www-data /opt/eventide-mcp

# 3. systemd 服务
sudo cp eventide-mcp.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now eventide-mcp
```

Caddy 反代（自动 HTTPS），在 `/etc/caddy/Caddyfile` 加：

```
eventide.example.com {
    reverse_proxy 127.0.0.1:8901
}
```

然后 `sudo systemctl reload caddy`。域名的 A 记录要指到 VPS IP。

用 Nginx 的话反代到 `127.0.0.1:8901` 即可，但要自己配 certbot 证书，且注意为 SSE 关闭缓冲：`proxy_buffering off; proxy_read_timeout 3600s;`。

验证：

```bash
curl -s -X POST https://eventide.example.com/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"t","version":"1"}}}'
```

返回 `serverInfo: Eventide` 即成功。

## 接入 claude.ai Connectors

claude.ai → Settings → Connectors → Add custom connector，URL 填：

```
https://eventide.example.com/mcp
```

无需 OAuth，直接添加即可。注意：这样任何知道 URL 的人都能调你的状态接口，建议路径加一段随机串（如把 Caddy 里的反代改成 `handle_path /mcp-<随机串>/*`），或在 Caddy 层加 basic auth 以外的头校验。
