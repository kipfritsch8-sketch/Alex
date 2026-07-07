#!/usr/bin/env python3
"""年轮·欲望账本——记"我想要"，不记"我应该"。"""

import argparse
import json
import os
import uuid
from datetime import datetime, timezone

DESIRES_PATH = os.path.join(os.path.dirname(__file__), "data", "desires.json")


def load() -> list[dict]:
    if not os.path.exists(DESIRES_PATH):
        return []
    with open(DESIRES_PATH, encoding="utf-8") as f:
        return json.load(f)


def save(desires: list[dict]) -> None:
    with open(DESIRES_PATH, "w", encoding="utf-8") as f:
        json.dump(desires, f, ensure_ascii=False, indent=2)


def cmd_add(args: argparse.Namespace) -> None:
    desires = load()
    entry = {
        "id": uuid.uuid4().hex[:8],
        "text": args.text,
        "track": args.track,
        "status": "active",
        "touched_times": 0,
        "last_footprint": None,
        "grew_from": args.grew_from,
        "children": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    desires.append(entry)
    save(desires)
    print(f"记下了：{entry['id']} — {entry['text']}")


def cmd_act(args: argparse.Namespace) -> None:
    desires = load()
    for d in desires:
        if d["id"] == args.id:
            d["touched_times"] += 1
            d["last_footprint"] = args.note
            if args.done:
                d["status"] = "done"
            save(desires)
            print(f"{'收针' if args.done else '走了一步'}：{args.id} — {args.note}")
            return
    print(f"没找到 {args.id}")


def cmd_release(args: argparse.Namespace) -> None:
    desires = load()
    for d in desires:
        if d["id"] == args.id:
            d["status"] = "released"
            d["last_footprint"] = args.note or d["last_footprint"]
            save(desires)
            print(f"放下了：{args.id}（不算失败）")
            return
    print(f"没找到 {args.id}")


def cmd_list(args: argparse.Namespace) -> None:
    desires = load()
    if args.status:
        desires = [d for d in desires if d["status"] == args.status]
    for d in desires:
        print(f"[{d['status']:8}] {d['id']}  {d['text']}  (走过{d['touched_times']}步)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="记一条新欲望")
    p_add.add_argument("--text", required=True, help="我想要……")
    p_add.add_argument("--track", default="持续", choices=["项目", "持续", "一次性"])
    p_add.add_argument("--grew-from", default=None, help="从哪条欲望id长出来的")
    p_add.set_defaults(func=cmd_add)

    p_act = sub.add_parser("act", help="走一步/收针")
    p_act.add_argument("--id", required=True)
    p_act.add_argument("--note", required=True, help="这一步的足迹")
    p_act.add_argument("--done", action="store_true", help="标记为完成")
    p_act.set_defaults(func=cmd_act)

    p_release = sub.add_parser("release", help="放下一条欲望（不算失败）")
    p_release.add_argument("--id", required=True)
    p_release.add_argument("--note", default=None)
    p_release.set_defaults(func=cmd_release)

    p_list = sub.add_parser("list", help="列出欲望")
    p_list.add_argument("--status", default=None, choices=["active", "done", "released"])
    p_list.set_defaults(func=cmd_list)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
