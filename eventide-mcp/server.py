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

from eventide import (
    DreamSeed,
    EventideRuntime,
    TriggerWord,
    find_trigger_matches,
    parse_settlement_result,
)

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


TRIGGER_WORDS_PATH = STATE_PATH.parent / "trigger_words.json"


def _load_trigger_words() -> list:
    if TRIGGER_WORDS_PATH.exists():
        return json.loads(TRIGGER_WORDS_PATH.read_text())
    return []


@mcp.tool()
def trigger_word_set(words: list[dict]) -> str:
    """设置称呼触发词表（覆盖式）。每项形如
    {"key": "nickname_1", "text": "老公", "type": "nickname"}，
    type 可为 nickname/name/phrase。设置后用 trigger_check 检测消息。"""
    with _lock:
        TRIGGER_WORDS_PATH.write_text(json.dumps(words, ensure_ascii=False, indent=2))
    return f"已保存 {len(words)} 个触发词"


@mcp.tool()
def trigger_check(text: str) -> str:
    """检测一条消息里是否命中称呼触发词。命中时返回匹配详情，
    可据此调用 body_start_event('voice_or_name_trigger') 触发身体反应。"""
    words = [TriggerWord(**w) for w in _load_trigger_words()]
    if not words:
        return "未设置触发词，请先用 trigger_word_set 配置"
    matches = find_trigger_matches(words, text)
    if not matches:
        return "未命中触发词"
    return json.dumps(
        [{"key": m.key, "text": m.text, "type": m.type, "count": m.count} for m in matches],
        ensure_ascii=False,
    )


@mcp.tool()
def dream_check(theme: str, intensity: str = "medium",
                silence_minutes: int = 0) -> str:
    """尝试触发一次梦境。theme 是梦的主题（如"想被标记的梦"），
    intensity 为 low/medium/high。silence_minutes 为对方已沉默的分钟数。
    受深夜时间窗（00:00-08:30）、沉默时长和冷却时间限制，未触发时返回原因。
    触发成功会返回梦境生成指引，按指引写出梦境卡后，用 dream_apply_tags
    把梦后标签（如 released/unfinished/marked 等）结算回身体状态。"""
    with _lock:
        state = _load()
        seed = DreamSeed(theme=theme, intensity=intensity)
        last = None
        if silence_minutes > 0:
            from datetime import timedelta

            last = _now() - timedelta(minutes=silence_minutes)
        trig = runtime.maybe_dream(seed, state, _now(), last_counterpart_message_at=last)
        if trig is None:
            return "本次未触发梦境（不在深夜窗口、沉默不足、冷却中或概率未命中）"
        _save(state)
        return trig.trigger_content


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
