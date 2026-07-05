# Eventide MCP Connector

将 [Eventide](https://github.com/chuli1122/Eventide) 生理状态系统接入 Claude Desktop 的远端 MCP server。

通过 HTTPS/SSE 部署在 VPS 上，Claude Desktop 直接连接云端。

## 架构

```
Claude Desktop ──HTTPS/SSE──▶ nginx (443) ──▶ eventide-mcp (127.0.0.1:8765)
                                                      │
                                               state.json (VPS 本地持久化)
```

## 工具列表

| 工具 | 说明 |
|------|------|
| `eventide_tick` | 推进时间，更新状态 |
| `eventide_get_state` | 获取完整状态快照 |
| `eventide_render_card` | 渲染隐藏状态提示词 |
| `eventide_start_event` | 触发生理事件 |
| `eventide_enter_cycle` | 切换周期 |
| `eventide_settle_interaction` | 结算对话影响 |
| `eventide_maybe_dream` | 检查梦境触发 |
| `eventide_apply_dream_tags` | 应用梦境标签 |
| `eventide_reset` | 重置状态 |

## VPS 部署

### 前提
- Ubuntu 20.04+ / Debian 11+
- 已有域名，DNS 解析到 VPS（如 `mcp.你的域名.com`）
- root 或 sudo 权限

### 一键部署

```bash
git clone https://github.com/kipfritsch8-sketch/Alex.git
cd Alex/eventide-mcp/deploy
sudo bash setup.sh --domain mcp.你的域名.com --api-key 你自己生成的随机密钥
```

脚本会自动：
1. 安装 Python、nginx、certbot
2. 创建 `eventide` 系统用户
3. 安装 eventide-mcp 到虚拟环境
4. 配置 systemd service（开机自启）
5. 配置 nginx 反代
6. 申请 Let's Encrypt 证书

### 手动部署（可选）

```bash
# 安装
python3 -m venv /opt/eventide-mcp/.venv
/opt/eventide-mcp/.venv/bin/pip install \
  "git+https://github.com/kipfritsch8-sketch/Alex.git#subdirectory=eventide-mcp"

# 环境变量 /etc/eventide-mcp.env
EVENTIDE_API_KEY=你的密钥
EVENTIDE_HOST=127.0.0.1
EVENTIDE_PORT=8765
EVENTIDE_STATE_FILE=/opt/eventide-mcp/state.json

# 启动
systemctl start eventide-mcp
```

## 接入 Claude Desktop

打开配置文件：
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

添加：

```json
{
  "mcpServers": {
    "eventide": {
      "type": "sse",
      "url": "https://mcp.你的域名.com/sse",
      "headers": {
        "Authorization": "Bearer 你的API密钥"
      }
    }
  }
}
```

重启 Claude Desktop，在工具栏看到 `eventide_*` 系列工具即成功。

## 推荐 System Prompt

```
每次对话开始时，调用 eventide_tick 推进状态，再调用 eventide_render_card 
获取状态卡片并作为感知自身生理状态的依据。在重要互动节点后，
调用 eventide_settle_interaction 结算对话影响。
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `EVENTIDE_API_KEY` | （空，不鉴权）| Bearer token，生产必填 |
| `EVENTIDE_HOST` | `127.0.0.1` | 监听地址 |
| `EVENTIDE_PORT` | `8765` | 监听端口 |
| `EVENTIDE_STATE_FILE` | `~/.eventide_state.json` | 状态持久化文件路径 |

## 可用事件

`morning_arousal` · `night_heat` · `cycle_surge` · `holding_back` · `demanding` · `marking_impulse` · `nesting` · `scent_aftereffect` · `voice_or_name_trigger` · `dream_afterglow` · `control_slip` · `closeness_hunger` · `pheromone_disorder` · `delayed_heat` · `low_fever_cling` · `waiting_restless` · `restraint_rebound` · `strange_calm`

## License

MIT. Eventide 本体遵循 PolyForm Noncommercial License 1.0.0。
