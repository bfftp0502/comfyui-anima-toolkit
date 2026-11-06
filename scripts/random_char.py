#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
random_char.py — 随机角色/画师选择（「跑图」单独说时用）

从 danbooru 索引随机挑一个角色（characters，count 高优先）和/或画师（artists）。

用法：
  python random_char.py --char        # 随机角色
  python random_char.py --artist      # 随机画师
  python random_char.py --both        # 随机角色+画师
"""
import argparse
import random
import sqlite3
import sys
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "tags_index.sqlite"


def pick(category: str, exclude_tags: set = None, limit_candidates: int = 200) -> str:
    """从指定分类随机挑一个标签（默认等权；按 count 加权的写法在函数里注释着）。"""
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cur = conn.cursor()
    cur.execute(
        "SELECT tag, count FROM tags WHERE category = ? ORDER BY count DESC LIMIT ?",
        (category, limit_candidates),
    )
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return ""
    candidates = [(t, c) for t, c in rows if not exclude_tags or t not in exclude_tags]
    if not candidates:
        return ""
    # ── 权重相关（默认注释，等权随机）──
    # 想按 count 加权（热门 tag 更容易被抽到），去掉下面两行注释即可：
    # weights = [max(c, 10) for _, c in candidates]
    # return random.choices([t for t, _ in candidates], weights=weights, k=1)[0]
    return random.choice([t for t, _ in candidates])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--char", action="store_true")
    ap.add_argument("--artist", action="store_true")
    ap.add_argument("--both", action="store_true")
    args = ap.parse_args()

    if args.both:
        print(f"{pick('characters')} {pick('artists')}")
    elif args.char:
        print(pick("characters"))
    elif args.artist:
        print(pick("artists"))
    else:
        print("用法: python random_char.py --char | --artist | --both")


if __name__ == "__main__":
    main()
