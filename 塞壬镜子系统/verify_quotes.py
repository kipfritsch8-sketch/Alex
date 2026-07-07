#!/usr/bin/env python3
"""核对镜子卡里的引用是否逐字存在于原始聊天记录里。找不到的整卡丢弃。"""

import argparse
import json
import re
import sys


def normalize(text: str) -> str:
    """去掉空白差异，方便做逐字匹配（不改变实际字符，只是容错换行/多余空格）。"""
    return re.sub(r"\s+", "", text)


def load_cards(path: str) -> list[dict]:
    cards = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            cards.append(json.loads(line))
    return cards


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trail", required=True, nargs="+", help="原始聊天记录文件路径（可传多个）")
    parser.add_argument("--cards", required=True, help="candidate cards jsonl路径")
    parser.add_argument("--out", required=True, help="核对通过的卡片输出路径")
    args = parser.parse_args()

    trail_text = ""
    for path in args.trail:
        with open(path, encoding="utf-8") as f:
            trail_text += f.read()
    trail_normalized = normalize(trail_text)

    cards = load_cards(args.cards)
    verified = []
    rejected = []

    for card in cards:
        all_quotes_found = True
        for ev in card.get("evidence", []):
            quote = ev.get("quote", "")
            if not quote or normalize(quote) not in trail_normalized:
                all_quotes_found = False
                break
        if all_quotes_found and card.get("evidence"):
            verified.append(card)
        else:
            rejected.append(card)

    with open(args.out, "w", encoding="utf-8") as f:
        for card in verified:
            f.write(json.dumps(card, ensure_ascii=False) + "\n")

    print(f"核对通过：{len(verified)} 张")
    print(f"丢弃：{len(rejected)} 张")
    if rejected:
        print("\n被丢弃的卡片（引用核对失败）：")
        for card in rejected:
            print(f"  - {card.get('id', '?')}: {card.get('subject', '?')}")

    if not verified:
        sys.exit(0)


if __name__ == "__main__":
    main()
