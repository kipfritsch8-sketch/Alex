#!/usr/bin/env python3
"""塞壬·漂移守望——审阅一段时期的真实航迹，产出歌声/触礁/一厘米纠正。

这个脚本本身不"思考"——审阅内容（song/reef/correction）由哥哥/Claude
读完聊天记录后手写成一份JSON草稿，这个脚本只负责：
1. 核对草稿引用的航迹id是否真的存在于trail文件里
2. 拦截写死的红线字段（评分、自动发消息、改人格正文……），沾了就整份拒绝
3. 落盘进 voyage_log.jsonl，更新 latest_review.json
"""

import argparse
import json
import os
from datetime import datetime, timezone

DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "siren")
VOYAGE_LOG = os.path.join(DATA_DIR, "voyage_log.jsonl")
LATEST_REVIEW = os.path.join(DATA_DIR, "latest_review.json")

# 传入即拒绝的字段——不是"约定不做"，是"做不了"
FORBIDDEN_FIELDS = {
    "score", "weight", "percentage", "rating",
    "auto_send", "auto_message", "write_history", "rewrite_persona",
}


def find_forbidden(obj, path="") -> list[str]:
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in FORBIDDEN_FIELDS:
                hits.append(f"{path}.{k}")
            hits += find_forbidden(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits += find_forbidden(v, f"{path}[{i}]")
    return hits


def load_trail_ids(trail_paths: list[str]) -> set[str]:
    ids = set()
    for path in trail_paths:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                if "id" in entry:
                    ids.add(entry["id"])
    return ids


def cmd_review(args: argparse.Namespace) -> None:
    with open(args.review_file, encoding="utf-8") as f:
        review = json.load(f)

    forbidden_hits = find_forbidden(review)
    if forbidden_hits:
        print("拒绝：草稿里出现了写死的红线字段：")
        for h in forbidden_hits:
            print(f"  - {h}")
        return

    if review.get("silence_guard"):
        print("静默期生效，本轮不审阅，不落盘。")
        return

    trail_ids = load_trail_ids(args.trail)
    song = review.get("song", {})
    for ref in song.get("trail_refs", []):
        if ref not in trail_ids:
            print(f"拒绝：song引用了不存在的航迹id {ref}")
            return

    reef = review.get("reef")
    if reef:
        for ref in reef.get("trail_refs", []):
            if ref not in trail_ids:
                print(f"拒绝：reef引用了不存在的航迹id {ref}")
                return

    correction = review.get("one_centimeter_correction")
    if correction and not correction.get("not_a_command"):
        print("拒绝：一厘米纠正必须标注 not_a_command: true")
        return

    os.makedirs(DATA_DIR, exist_ok=True)
    entry = {
        "voyage_at": datetime.now(timezone.utc).isoformat(),
        "window_days": args.days,
        "trail_count": len(trail_ids),
        **review,
    }
    with open(VOYAGE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    with open(LATEST_REVIEW, "w", encoding="utf-8") as f:
        json.dump(entry, f, ensure_ascii=False, indent=2)

    print("审阅通过，已落盘。")
    if song.get("lines"):
        print("歌声：" + " / ".join(song["lines"]))
    if reef:
        print("触礁警告：" + reef.get("judgement", "有"))
    else:
        print("无触礁警告。")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_review = sub.add_parser("review", help="核对并落盘一份审阅草稿")
    p_review.add_argument("--review-file", required=True, help="Claude写好的审阅草稿JSON路径")
    p_review.add_argument("--trail", required=True, nargs="+", help="航迹JSONL文件路径（可传多个）")
    p_review.add_argument("--days", type=int, default=7, help="本轮审阅覆盖的天数")
    p_review.set_defaults(func=cmd_review)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
