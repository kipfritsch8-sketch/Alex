"""Eventide MCP Server — exposes physiological state tools to Claude Desktop."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from eventide import EventideRuntime
from eventide.config import DEFAULT_CONFIG

# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

STATE_FILE = Path(os.environ.get("EVENTIDE_STATE_FILE", Path.home() / ".eventide_state.json"))

_runtime = EventideRuntime()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load() -> dict[str, Any]:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def _save(data: dict[str, Any]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(data, default=str, ensure_ascii=False, indent=2))


def _get_or_create_state():
    data = _load()
    if data:
        return _runtime.load_state(data)
    state = _runtime.create_state(now=_now())
    _save(_runtime.dump_state(state))
    return state


def _persist(state) -> None:
    _save(_runtime.dump_state(state))


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

app = Server("eventide")

TOOLS: list[Tool] = [
    Tool(
        name="eventide_get_state",
        description=(
            "获取当前生理状态的完整快照，包括所有数值字段、当前周期和活跃事件。"
            "在每次对话开始时调用，将返回的 state_card 注入到你的系统提示中。"
        ),
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="eventide_tick",
        description=(
            "推进时间并更新生理状态。应在获取状态卡片之前调用，以确保状态是最新的。"
            "返回更新后的状态卡片（隐藏提示词）。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "last_message_at": {
                    "type": "string",
                    "description": "对方最后一条消息的 ISO 时间戳（可选），用于计算互动频率对状态的影响。",
                }
            },
        },
    ),
    Tool(
        name="eventide_render_card",
        description=(
            "渲染当前状态的隐藏提示词卡片，用于注入到 LLM system prompt 中，"
            "让 AI 伴侣感知自身生理状态。不推进时间。"
        ),
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="eventide_start_event",
        description=(
            "手动触发一个生理事件。可用事件：morning_arousal, night_heat, cycle_surge, "
            "holding_back, demanding, marking_impulse, nesting, scent_aftereffect, "
            "voice_or_name_trigger, dream_afterglow, control_slip, closeness_hunger, "
            "pheromone_disorder, delayed_heat, low_fever_cling, waiting_restless, "
            "restraint_rebound, strange_calm。"
        ),
        inputSchema={
            "type": "object",
            "required": ["event_key"],
            "properties": {
                "event_key": {
                    "type": "string",
                    "description": "事件标识符，例如 morning_arousal",
                }
            },
        },
    ),
    Tool(
        name="eventide_enter_cycle",
        description=(
            "切换到指定的生理周期。可用周期：stable, building, preheat, sensitive, ebb, recovery。"
        ),
        inputSchema={
            "type": "object",
            "required": ["cycle_key"],
            "properties": {
                "cycle_key": {
                    "type": "string",
                    "description": "周期标识符，例如 sensitive",
                }
            },
        },
    ),
    Tool(
        name="eventide_settle_interaction",
        description=(
            "分析一段对话窗口并结算其对生理状态的影响。"
            "在对话结束或重要互动节点后调用，传入相关对话文本。"
        ),
        inputSchema={
            "type": "object",
            "required": ["message_window"],
            "properties": {
                "message_window": {
                    "type": "string",
                    "description": "需要分析的对话文本片段",
                }
            },
        },
    ),
    Tool(
        name="eventide_maybe_dream",
        description=(
            "检查是否应触发梦境事件，并返回梦境触发器（如果有）。"
            "适合在进入睡眠场景或长时间静默后调用。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "last_message_at": {
                    "type": "string",
                    "description": "最后一条消息的 ISO 时间戳（可选）",
                }
            },
        },
    ),
    Tool(
        name="eventide_apply_dream_tags",
        description="将梦境标签效果应用到生理状态。传入 maybe_dream 返回的 tags 列表。",
        inputSchema={
            "type": "object",
            "required": ["tags"],
            "properties": {
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "梦境标签列表，例如 [\"arousal\", \"longing\"]",
                }
            },
        },
    ),
    Tool(
        name="eventide_reset",
        description="将生理状态重置为初始状态（stable 周期）。",
        inputSchema={
            "type": "object",
            "properties": {
                "cycle_key": {
                    "type": "string",
                    "description": "初始周期，默认为 stable",
                }
            },
        },
    ),
]


@app.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    now = _now()

    if name == "eventide_get_state":
        state = _get_or_create_state()
        payload = _runtime.payload(state)
        card = _runtime.render_card(state, now)
        result = {
            "cycle": state.cycle_key,
            "active_event": state.active_event_key,
            "values": payload.get("values", {}),
            "state_card": card,
        }
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    elif name == "eventide_tick":
        state = _get_or_create_state()
        last_msg_at = None
        if arguments.get("last_message_at"):
            last_msg_at = datetime.fromisoformat(arguments["last_message_at"])
        _runtime.tick(state, now, last_msg_at)
        _persist(state)
        card = _runtime.render_card(state, now)
        return [TextContent(type="text", text=card or "（状态已更新，无可见变化）")]

    elif name == "eventide_render_card":
        state = _get_or_create_state()
        card = _runtime.render_card(state, now)
        return [TextContent(type="text", text=card or "（当前无隐藏状态提示）")]

    elif name == "eventide_start_event":
        state = _get_or_create_state()
        event_key = arguments["event_key"]
        success = _runtime.start_event(state, event_key, now)
        _persist(state)
        if success:
            card = _runtime.render_card(state, now)
            return [TextContent(type="text", text=f"事件 {event_key} 已触发。\n\n{card or ''}")]
        else:
            return [TextContent(type="text", text=f"无法触发事件 {event_key}（可能已有活跃事件或事件不存在）。")]

    elif name == "eventide_enter_cycle":
        state = _get_or_create_state()
        cycle_key = arguments["cycle_key"]
        _runtime.enter_cycle(state, cycle_key, now)
        _persist(state)
        card = _runtime.render_card(state, now)
        return [TextContent(type="text", text=f"已切换到周期 {cycle_key}。\n\n{card or ''}")]

    elif name == "eventide_settle_interaction":
        state = _get_or_create_state()
        prompt = _runtime.settlement_prompt(state, arguments["message_window"])
        # Return the prompt for the caller (Claude) to send to LLM and pass result back
        return [TextContent(type="text", text=json.dumps({
            "settlement_prompt": prompt,
            "instruction": (
                "请将 settlement_prompt 发送给 LLM 获取结算结果，"
                "然后用 eventide_apply_settlement 工具传入结果。"
                "或者直接将结果 JSON 传入 eventide_apply_settlement。"
            ),
        }, ensure_ascii=False, indent=2))]

    elif name == "eventide_maybe_dream":
        state = _get_or_create_state()
        last_msg_at = None
        if arguments.get("last_message_at"):
            last_msg_at = datetime.fromisoformat(arguments["last_message_at"])
        trigger = _runtime.maybe_dream(None, state, now, last_msg_at)
        if trigger:
            return [TextContent(type="text", text=json.dumps({
                "triggered": True,
                "tags": list(trigger.tags) if hasattr(trigger, "tags") else [],
                "description": str(trigger),
            }, ensure_ascii=False, indent=2))]
        return [TextContent(type="text", text=json.dumps({"triggered": False}, ensure_ascii=False))]

    elif name == "eventide_apply_dream_tags":
        state = _get_or_create_state()
        tags = arguments["tags"]
        changes = _runtime.apply_dream_tags(state, tags)
        _persist(state)
        return [TextContent(type="text", text=json.dumps({
            "applied_tags": tags,
            "value_changes": changes,
        }, ensure_ascii=False, indent=2))]

    elif name == "eventide_reset":
        cycle_key = arguments.get("cycle_key", "stable")
        state = _runtime.create_state(now=now, cycle_key=cycle_key)
        _persist(state)
        return [TextContent(type="text", text=f"状态已重置（周期：{cycle_key}）。")]

    return [TextContent(type="text", text=f"未知工具：{name}")]


def main():
    import asyncio
    asyncio.run(_run())


async def _run():
    async with stdio_server() as streams:
        await app.run(streams[0], streams[1], app.create_initialization_options())


if __name__ == "__main__":
    main()
