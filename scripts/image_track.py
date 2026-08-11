#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
image_track.py — 记录/读取最近一次跑图输出（供「收图」口令用）

跑图完成后调用 --record，把输出图路径写入状态文件；
收图口令调用 --get，返回状态文件里记录的路径。

用法：
  python image_track.py --record "<图片路径>"   # 跑图完成后记录
  python image_track.py --get                   # 收图时读取
"""
import argparse
import json
import sys
from pathlib import Path

STATE_FILE = Path(__file__).resolve().parent / "last_image.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", default=None, help="记录本次出图路径")
    ap.add_argument("--get", action="store_true", help="读取上次出图路径")
    args = ap.parse_args()

    if args.record:
        STATE_FILE.write_text(json.dumps({"path": args.record, "ts": __import__("time").time()}),
                              encoding="utf-8")
        print(f"✅ 已记录: {args.record}")
        return

    if args.get:
        if not STATE_FILE.exists():
            sys.exit("⚠️ 没有已记录的出图（还没跑过图）")
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        p = data.get("path", "")
        if not Path(p).exists():
            sys.exit(f"⚠️ 记录的图不存在了: {p}")
        print(p)
        return

    ap.print_help()


if __name__ == "__main__":
    main()
