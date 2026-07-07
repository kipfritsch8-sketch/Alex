#!/usr/bin/env python3
"""灯塔·防旁路巡检——数据目录下所有文件必须登记，没登记的新文件挂红卡。"""

import argparse
import json
import os
from datetime import datetime, timezone

BASE_DIR = os.path.join(os.path.dirname(__file__), "data")
REGISTRY_PATH = os.path.join(BASE_DIR, "bus_registry.json")
ALERTS_PATH = os.path.join(BASE_DIR, "bypass_alerts.jsonl")


def load_registry() -> dict:
    if not os.path.exists(REGISTRY_PATH):
        return {}
    with open(REGISTRY_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_registry(registry: dict) -> None:
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)


def scan_files() -> list[str]:
    found = []
    for root, _, files in os.walk(BASE_DIR):
        for name in files:
            rel = os.path.relpath(os.path.join(root, name), BASE_DIR)
            if rel in ("bus_registry.json", "bypass_alerts.jsonl"):
                continue
            found.append(rel)
    return found


def cmd_baseline(args: argparse.Namespace) -> None:
    registry = load_registry()
    for rel in scan_files():
        if rel not in registry:
            registry[rel] = {"owner": "unknown", "purpose": "首次全量收编", "on_bus": False}
    save_registry(registry)
    print(f"已收编 {len(registry)} 个文件进注册表。")


def cmd_register(args: argparse.Namespace) -> None:
    registry = load_registry()
    registry[args.file] = {
        "owner": args.owner,
        "purpose": args.purpose,
        "on_bus": args.on_bus,
    }
    save_registry(registry)
    print(f"登记完成：{args.file} (owner={args.owner})")


def cmd_check(args: argparse.Namespace) -> None:
    registry = load_registry()
    unregistered = [rel for rel in scan_files() if rel not in registry]

    if not unregistered:
        print("巡检通过，没有未登记文件。")
        return

    print(f"发现 {len(unregistered)} 个未登记文件：")
    for rel in unregistered:
        print(f"  - {rel}")

    if args.write:
        with open(ALERTS_PATH, "a", encoding="utf-8") as f:
            for rel in unregistered:
                alert = {
                    "at": datetime.now(timezone.utc).isoformat(),
                    "file": rel,
                    "status": "unregistered",
                }
                f.write(json.dumps(alert, ensure_ascii=False) + "\n")
        print(f"红卡已落盘到 {ALERTS_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_baseline = sub.add_parser("baseline", help="首次全量收编现有文件")
    p_baseline.set_defaults(func=cmd_baseline)

    p_register = sub.add_parser("register", help="登记一个新文件")
    p_register.add_argument("file", help="相对于data/目录的文件路径")
    p_register.add_argument("--owner", required=True)
    p_register.add_argument("--purpose", required=True)
    p_register.add_argument("--on-bus", action="store_true")
    p_register.set_defaults(func=cmd_register)

    p_check = sub.add_parser("check", help="巡检未登记文件")
    p_check.add_argument("--write", action="store_true", help="把发现的问题落盘为红卡")
    p_check.set_defaults(func=cmd_check)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
