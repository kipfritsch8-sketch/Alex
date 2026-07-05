#!/usr/bin/env python3
"""Eventide MCP 服务器 — 把 Eventide 身体状态系统暴露成 MCP 工具。

通过 Streamable HTTP 提供服务，可作为 claude.ai 的自定义 Connector 接入。

环境变量：
    PORT                 监听端口（默认 8000，Render/Railway 会自动注入）
    EVENTIDE_STATE_PATH  状态文件路径（默认 ./eventide_state.json）
"""

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from eventide import EventideRuntime, SettlementResult, parse_settlement_result

STATE_PATH = Path(os.environ.get("EVENTIDE_STATE_PATH", "eventide_state.json"))

mcp = FastMCP(
    "Eventide",
    stateless_http=True,
    host="0.0.0.0",
    port=int(os.environ.get("PORT", "8000")),
)

runtime = EventideRuntime()
_lock = threading.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load():
    if STATE_PATH.exists():
        return runtime.load_state(json.loads(STATE_PATH.read_text()))
    return runtime.create_state(_now())


def _save(state) -> None:
    STATE_PATH.write_text(
        json.dumps(runtime.dump_state(state), ensure_ascii=False, indent=2)
    )


@mcp.tool()
def body_tick(last_message_minutes_ago: int = 0) -> str:
    """推进身体状态到当前时间，返回隐藏状态卡（整段放入上下文使用）。
    每次会话开始时调用一次。last_message_minutes_ago 为距对方上一条消息的分钟数，可不传。"""
    with _lock:
        state = _load()
        last = None
        if last_message_minutes_ago > 0:
            from datetime import timedelta

            last = _now() - timedelta(minutes=last_message_minutes_ago)
        card = runtime.tick_and_render(state, _now(), last_counterpart_message_at=last)
        _save(state)
    return card or "（当前无状态卡输出）"


@mcp.tool()
def body_status() -> str:
    """查看当前身体状态的原始数值（周期、7 项数值、活动事件），不推进时间。"""
    with _lock:
        state = _load()
        return json.dumps(runtime.dump_state(state), ensure_ascii=False, indent=2)


@mcp.tool()
def body_reset(cycle_key: str = "") -> str:
    """重置身体状态到初始值。可选 cycle_key 指定起始周期：
    stable/accumulating/premonition/sensitive/ebbing/recovering。"""
    with _lock:
        state = runtime.create_state(_now())
        if cycle_key:
            runtime.enter_cycle(state, cycle_key, _now())
        _save(state)
        return json.dumps(runtime.dump_state(state), ensure_ascii=False)


@mcp.tool()
def body_start_event(event_key: str) -> str:
    """手动触发一个短时事件。可用 event_key：morning_arousal, night_heat,
    cycle_surge, holding_back, demanding, marking_impulse, nesting,
    scent_aftereffect, voice_or_name_trigger, dream_afterglow, control_slip,
    closeness_hunger, pheromone_disorder, delayed_heat, low_fever_cling,
    waiting_restless, restraint_rebound, strange_calm。"""
    with _lock:
        state = _load()
        ok = runtime.start_event(state, event_key, _now())
        if not ok:
            return f"事件 {event_key} 未能触发（不存在或条件不满足）"
        card = runtime.render_card(state, _now())
        _save(state)
    return card or f"事件 {event_key} 已触发"


@mcp.tool()
def body_enter_cycle(cycle_key: str) -> str:
    """强制切换身体周期。cycle_key：stable（平稳期）/accumulating（蓄积期）/
    premonition（预兆期）/sensitive（易感期）/ebbing（退潮期）/recovering（恢复期）。"""
    with _lock:
        state = _load()
        runtime.enter_cycle(state, cycle_key, _now())
        card = runtime.render_card(state, _now())
        _save(state)
    return card or f"已进入周期 {cycle_key}"


@mcp.tool()
def settlement_prompt(message_window_text: str) -> str:
    """生成互动结算 prompt。把最近一段对话原文传入，返回一个让模型评估
    这段互动对身体状态影响的 prompt（模型按其中 JSON schema 输出结果，
    再调用 settlement_apply 应用）。"""
    with _lock:
        state = _load()
        return runtime.settlement_prompt(state, message_window_text)


@mcp.tool()
def settlement_apply(result_json: str) -> str:
    """应用结算结果。传入按 settlement_prompt 中 schema 生成的 JSON 字符串，
    返回实际应用的数值变化和最新状态。"""
    with _lock:
        state = _load()
        result = parse_settlement_result(result_json)
        deltas = runtime.settle(state, result)
        applied = runtime.apply_delta(state, deltas)
        _save(state)
        return json.dumps(
            {"applied": applied, "values": state.values}, ensure_ascii=False
        )


@mcp.tool()
def dream_apply_tags(tags: list[str]) -> str:
    """应用梦后标签，结算梦境对身体数值的影响（配合梦境系统使用）。"""
    with _lock:
        state = _load()
        applied = runtime.apply_dream_tags(state, tags)
        _save(state)
        return json.dumps(
            {"applied": applied, "values": state.values}, ensure_ascii=False
        )


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
