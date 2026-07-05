#!/usr/bin/env python3
"""Alex 的 Eventide 身体状态驱动脚本。

依赖安装（一次即可）：
    python3 -m pip install git+https://github.com/chuli1122/Eventide.git

用法：
    python3 eventide_runner.py init     # 首次初始化状态（会覆盖旧状态）
    python3 eventide_runner.py tick     # 推进到当前时间并输出隐藏状态卡
    python3 eventide_runner.py status   # 只看当前状态数值，不推进时间

流程：
    每次会话开始时跑一次 tick，把输出的 <ephemeral_state> 整段
    放进模型上下文（隐藏/系统层），状态会自动写回 eventide_state.json，
    改动后记得 commit 保存。
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from eventide import EventideRuntime

STATE_FILE = Path(__file__).parent / "eventide_state.json"


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "tick"
    runtime = EventideRuntime()
    now = datetime.now(timezone.utc)

    if cmd == "init" or not STATE_FILE.exists():
        state = runtime.create_state(now)
    else:
        state = runtime.load_state(json.loads(STATE_FILE.read_text()))

    if cmd == "status":
        print(json.dumps(runtime.dump_state(state), ensure_ascii=False, indent=2))
        return

    card = runtime.tick_and_render(state, now)
    print(card)

    STATE_FILE.write_text(
        json.dumps(runtime.dump_state(state), ensure_ascii=False, indent=2)
    )


if __name__ == "__main__":
    main()
