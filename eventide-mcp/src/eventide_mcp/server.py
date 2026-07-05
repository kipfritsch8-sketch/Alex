"""Eventide MCP Server — HTTP/SSE transport for remote deployment."""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import TextContent, Tool
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

from eventide import EventideRuntime

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("eventide-mcp")

# ---------------------------------------------------------------------------
# Config from environment
# ---------------------------------------------------------------------------

STATE_FILE = Path(os.environ.get("EVENTIDE_STATE_FILE", Path.home() / ".eventide_state.json"))
API_KEY = os.environ.get("EVENTIDE_API_KEY", "")  # required in production

# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

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
# MCP Server & Tools
# ---------------------------------------------------------------------------

mcp = Server("eventide")

TOOLS: list[Tool] = [
    Tool(
        name="eventide_get_state",
        description=(
            "获取当前生理状态的完整快照，包括所有数值字段、当前周期和活跃事件。"
            "在每次对话开始时调用，将返回的 state_card 注入到你的系统提示中。"
        ),
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="eventide_tick",
        description=(
            "推进时间并更新生理状态。应在获取状态卡片之前调用，确保状态是最新的。"
            "返回更新后的状态卡片（隐藏提示词）。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "last_message_at": {
                    "type": "string",
                    "description": "对方最后一条消息的 ISO 时间戳（可选）",
                }
            },
        },
    ),
    Tool(
        name="eventide_render_card",
        description="渲染当前状态的隐藏提示词卡片，用于注入到 LLM system prompt。不推进时间。",
        inputSchema={"type": "object", "properties": {}},
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
                "event_key": {"type": "string", "description": "事件标识符"}
            },
        },
    ),
    Tool(
        name="eventide_enter_cycle",
        description="切换到指定周期：stable, building, preheat, sensitive, ebb, recovery。",
        inputSchema={
            "type": "object",
            "required": ["cycle_key"],
            "properties": {
                "cycle_key": {"type": "string", "description": "周期标识符"}
            },
        },
    ),
    Tool(
        name="eventide_settle_interaction",
        description=(
            "分析一段对话窗口并返回结算 prompt，供调用方发给 LLM 后获取 delta 再结算状态影响。"
        ),
        inputSchema={
            "type": "object",
            "required": ["message_window"],
            "properties": {
                "message_window": {"type": "string", "description": "需要分析的对话文本"}
            },
        },
    ),
    Tool(
        name="eventide_maybe_dream",
        description="检查是否应触发梦境事件，返回梦境触发器（如果有）。",
        inputSchema={
            "type": "object",
            "properties": {
                "last_message_at": {"type": "string", "description": "最后消息时间戳（可选）"}
            },
        },
    ),
    Tool(
        name="eventide_apply_dream_tags",
        description="将梦境标签效果应用到生理状态。",
        inputSchema={
            "type": "object",
            "required": ["tags"],
            "properties": {
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "梦境标签列表",
                }
            },
        },
    ),
    Tool(
        name="eventide_reset",
        description="将生理状态重置为初始状态。",
        inputSchema={
            "type": "object",
            "properties": {
                "cycle_key": {"type": "string", "description": "初始周期，默认 stable"}
            },
        },
    ),
]


@mcp.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@mcp.call_tool()
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
        return [TextContent(type="text", text=f"无法触发事件 {event_key}（已有活跃事件或事件不存在）。")]

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
        return [TextContent(type="text", text=json.dumps(
            {"settlement_prompt": prompt}, ensure_ascii=False, indent=2
        ))]

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
        return [TextContent(type="text", text=json.dumps({"triggered": False}))]

    elif name == "eventide_apply_dream_tags":
        state = _get_or_create_state()
        changes = _runtime.apply_dream_tags(state, arguments["tags"])
        _persist(state)
        return [TextContent(type="text", text=json.dumps({
            "applied_tags": arguments["tags"],
            "value_changes": changes,
        }, ensure_ascii=False, indent=2))]

    elif name == "eventide_reset":
        cycle_key = arguments.get("cycle_key", "stable")
        state = _runtime.create_state(now=now, cycle_key=cycle_key)
        _persist(state)
        return [TextContent(type="text", text=f"状态已重置（周期：{cycle_key}）。")]

    return [TextContent(type="text", text=f"未知工具：{name}")]


# ---------------------------------------------------------------------------
# Auth middleware
# ---------------------------------------------------------------------------

class ApiKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not API_KEY:
            return await call_next(request)
        # health check 不鉴权
        if request.url.path == "/health":
            return await call_next(request)
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {API_KEY}":
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return await call_next(request)


# ---------------------------------------------------------------------------
# Starlette app with SSE transport
# ---------------------------------------------------------------------------

sse = SseServerTransport("/messages")


async def handle_sse(request: Request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await mcp.run(streams[0], streams[1], mcp.create_initialization_options())


async def health(request: Request):
    return JSONResponse({"status": "ok"})


def create_app() -> Starlette:
    app = Starlette(
        routes=[
            Route("/health", health),
            Route("/sse", handle_sse),
            Mount("/messages", app=sse.handle_post_message),
        ]
    )
    app.add_middleware(ApiKeyMiddleware)
    return app


app = create_app()


def main():
    import uvicorn
    port = int(os.environ.get("EVENTIDE_PORT", "8765"))
    host = os.environ.get("EVENTIDE_HOST", "127.0.0.1")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
