#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tag_lookup.py — 一键查 Danbooru canonical tag（local 扩写用）

local 扩写时如需确认角色/画师/系列的正确 tag，运行：
  python tag_lookup.py "<关键词>"

输出：匹配的 canonical tag（含分类和出现次数），供扩写时使用。
自动处理：CLI 守卫误报 → 直接用 sqlite 查，local 无需关心内部实现。
"""
import sqlite3
import sys
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "tags_index.sqlite"


def normalize(s: str) -> str:
    return s.strip().lower().replace("_", " ").replace("-", " ")


def lookup(keyword: str, limit: int = 8):
    if not DB.exists():
        sys.exit(f"[错误] 索引不存在: {DB}")
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cur = conn.cursor()

    norm = normalize(keyword)
    # tags 表: category / tag / tag_norm / count
    try:
        rows = cur.execute(
            "SELECT category, tag, count FROM tags WHERE tag_norm LIKE ? OR tag LIKE ? "
            "ORDER BY count DESC LIMIT ?",
            (f"%{norm}%", f"%{norm}%", limit),
        ).fetchall()
    except Exception as e:
        sys.exit(f"[查询失败] {e}")

    if rows:
        print(f"== 匹配（{len(rows)}）:")
        for cat, tag, count in rows:
            print(f"  [{cat}] {tag}  (count={count})")
    else:
        print(f"（无匹配: {keyword}）——可直接用下划线风格词，或换关键词再查")
    conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python tag_lookup.py <关键词>")
        sys.exit(1)
    lookup(sys.argv[1])
