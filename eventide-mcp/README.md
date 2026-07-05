# Eventide MCP Connector

将 [Eventide](https://github.com/chuli1122/Eventide) 生理状态系统接入 Claude Desktop 的 MCP connector。

## 功能

Claude Desktop 通过 MCP 协议调用以下工具，让 AI 伴侣拥有持久化的生理状态感知：

| 工具 | 说明 |
|------|------|
| `eventide_tick` | 推进时间，更新状态 |
| `eventide_get_state` | 获取完整状态快照 |
| `eventide_render_card` | 渲染隐藏状态提示词，注入 system prompt |
| `eventide_start_event` | 触发生理事件（如 morning_arousal） |
| `eventide_enter_cycle` | 切换周期（stable/building/preheat/sensitive/ebb/recovery） |
| `eventide_settle_interaction` | 结算对话对状态的影响 |
| `eventide_maybe_dream` | 检查梦境触发 |
| `eventide_apply_dream_tags` | 应用梦境标签效果 |
| `eventide_reset` | 重置状态 |

状态持久化到本地 JSON 文件（默认 `~/.eventide_state.json`），跨会话保持连续。

## 安装

### 前提

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) 已安装（推荐）

### 本地安装

```bash
git clone https://github.com/kipfritsch8-sketch/alex.git
cd alex/eventide-mcp
pip install -e .
```

## 接入 Claude Desktop

1. 打开 Claude Desktop 配置文件：
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`

2. 添加以下配置（合并到已有的 `mcpServers` 对象中）：

```json
{
  "mcpServers": {
    "eventide": {
      "command": "python",
      "args": ["-m", "eventide_mcp.server"],
      "env": {
        "EVENTIDE_STATE_FILE": "/Users/你的用户名/.eventide_state.json"
      }
    }
  }
}
```

> 如果使用 uvx 直接从 git 安装，可参考 `claude_desktop_config.json` 示例。

3. 重启 Claude Desktop，在工具列表中看到 `eventide_*` 系列工具即接入成功。

## 推荐使用方式

在你的 Claude Desktop system prompt 中加入：

```
每次对话开始时，调用 eventide_tick 推进状态，再调用 eventide_render_card 获取状态卡片并将其作为你感知自身状态的依据。在重要互动节点后，调用 eventide_settle_interaction 结算对话影响。
```

## 可用事件列表

`morning_arousal` · `night_heat` · `cycle_surge` · `holding_back` · `demanding` · `marking_impulse` · `nesting` · `scent_aftereffect` · `voice_or_name_trigger` · `dream_afterglow` · `control_slip` · `closeness_hunger` · `pheromone_disorder` · `delayed_heat` · `low_fever_cling` · `waiting_restless` · `restraint_rebound` · `strange_calm`

## License

本 connector 遵循 MIT 协议。Eventide 本体遵循 PolyForm Noncommercial License 1.0.0。
