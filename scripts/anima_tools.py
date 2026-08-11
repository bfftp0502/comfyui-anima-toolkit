#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Anima-Tools 数据库查询（生图选画师/角色/服装用）
数据源: anima_tools.sqlite（源自 Comfyui-Anima-Tools 插件 js/data.js 等，40K 画师 + 8K 角色 + 430 服装）

用法:
  python anima_tools.py artist "dai"          # 模糊搜画师，按作品数排序
  python anima_tools.py artist-top 20         # 全量作品数 Top N
  python anima_tools.py arand                 # 全量加权随机抽 1 个画师
  python anima_tools.py arand "genshin"       # 从名字含关键词的画师里随机抽
  python anima_tools.py char "genshin"        # 按系列(copyright)搜角色，按热度排序
  python anima_tools.py char "genshin" 20     # 系列 Top N
  python anima_tools.py crand "genshin"       # 系列内加权随机抽 1 个角色
  python anima_tools.py crand "genshin" 3     # 系列内加权随机抽 3 个
  python anima_tools.py cloth "礼服"           # 按分类/名称/特征查服装（中英文都行）
  python anima_tools.py cloth-top 10          # 服装库样本
"""
import random, sqlite3, sys
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "anima_tools.sqlite"


def db():
    return sqlite3.connect(f"file:{DB}?mode=ro", uri=True)


def artist_search(kw, limit=15):
    c = db()
    rows = c.execute(
        "SELECT name, post_count, uniqueness_score FROM artists WHERE name LIKE ? "
        "ORDER BY post_count DESC LIMIT ?", (f"%{kw}%", limit)).fetchall()
    c.close()
    for name, pc, us in rows:
        print(f"@{name}  |  {pc:,} 张  |  独特度 {us}")


def artist_top(n):
    c = db()
    rows = c.execute("SELECT name, post_count, uniqueness_score FROM artists "
                     "ORDER BY post_count DESC LIMIT ?", (n,)).fetchall()
    c.close()
    for i, (name, pc, us) in enumerate(rows, 1):
        print(f"{i:>3}. @{name}  |  {pc:,} 张  |  独特度 {us}")


def artist_random(kw=None):
    c = db()
    if kw:
        rows = c.execute("SELECT name, post_count FROM artists WHERE name LIKE ?",
                         (f"%{kw}%",)).fetchall()
    else:
        rows = c.execute("SELECT name, post_count FROM artists").fetchall()
    c.close()
    if not rows:
        print("无匹配"); return
    pick = random.choices([r[0] for r in rows],
                          weights=[max(r[1], 10) for r in rows], k=1)[0]
    print(f"@{pick}")


def char_search(copy, limit=15):
    c = db()
    rows = c.execute(
        "SELECT name, post_count, gender, hair, eye FROM characters "
        "WHERE copyright LIKE ? ORDER BY post_count DESC LIMIT ?",
        (f"%{copy}%", limit)).fetchall()
    c.close()
    for name, pc, g, h, e in rows:
        print(f"{name}  |  {pc:,} 张  |  {g}  {h}/{e}")


def char_random(copy=None, k=1):
    c = db()
    if copy:
        rows = c.execute("SELECT name, post_count FROM characters WHERE copyright LIKE ?",
                         (f"%{copy}%",)).fetchall()
    else:
        rows = c.execute("SELECT name, post_count FROM characters").fetchall()
    c.close()
    if not rows:
        print("无匹配"); return
    picks = random.choices([r[0] for r in rows],
                           weights=[max(r[1], 10) for r in rows], k=k)
    print("\n".join(picks))


def cloth_search(kw, limit=10):
    c = db()
    rows = c.execute(
        "SELECT name, name_zh, tags, categories FROM clothing "
        "WHERE name LIKE ? OR name_zh LIKE ? OR tags LIKE ? OR categories LIKE ? "
        "LIMIT ?", (f"%{kw}%", f"%{kw}%", f"%{kw}%", f"%{kw}%", limit)).fetchall()
    c.close()
    for name, name_zh, tags, cats in rows:
        print(f"◆ {name}（{name_zh}）\n   tags: {tags.strip()}\n   分类: {cats}")


def cloth_top(n):
    c = db()
    rows = c.execute("SELECT name, name_zh, tags FROM clothing LIMIT ?", (n,)).fetchall()
    c.close()
    for name, name_zh, tags in rows:
        print(f"◆ {name}（{name_zh}）\n   tags: {tags.strip()}")


def pose_search(kw, limit=10):
    c = db()
    rows = c.execute(
        "SELECT name, name_zh, tags, categories FROM poses "
        "WHERE name LIKE ? OR name_zh LIKE ? OR tags LIKE ? OR categories LIKE ? OR traits LIKE ? "
        "LIMIT ?", (f"%{kw}%", f"%{kw}%", f"%{kw}%", f"%{kw}%", f"%{kw}%", limit)).fetchall()
    c.close()
    if not rows:
        print("无匹配"); return
    for name, name_zh, tags, cats in rows:
        print(f"◆ {name}（{name_zh}）\n   tags: {tags.strip()}\n   分类: {cats}")


def bg_search(kw, limit=10):
    c = db()
    rows = c.execute(
        "SELECT name, name_zh, tags, categories FROM backgrounds "
        "WHERE name LIKE ? OR name_zh LIKE ? OR tags LIKE ? OR categories LIKE ? OR traits LIKE ? "
        "LIMIT ?", (f"%{kw}%", f"%{kw}%", f"%{kw}%", f"%{kw}%", f"%{kw}%", limit)).fetchall()
    c.close()
    if not rows:
        print("无匹配"); return
    for name, name_zh, tags, cats in rows:
        print(f"◆ {name}（{name_zh}）\n   tags: {tags.strip()}\n   分类: {cats}")


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__); return
    cmd = args[0]
    if cmd == "artist" and len(args) > 1:
        artist_search(args[1])
    elif cmd == "artist-top" and len(args) > 1:
        artist_top(int(args[1]))
    elif cmd == "arand":
        artist_random(args[1] if len(args) > 1 else None)
    elif cmd == "char" and len(args) > 1:
        char_search(args[1], int(args[2]) if len(args) > 2 else 15)
    elif cmd == "crand":
        copy = args[1] if len(args) > 1 else None
        char_random(copy, int(args[2]) if len(args) > 2 else 1)
    elif cmd == "cloth" and len(args) > 1:
        cloth_search(args[1])
    elif cmd == "cloth-top" and len(args) > 1:
        cloth_top(int(args[1]))
    elif cmd == "pose" and len(args) > 1:
        pose_search(args[1], int(args[2]) if len(args) > 2 else 10)
    elif cmd == "background" and len(args) > 1:
        bg_search(args[1], int(args[2]) if len(args) > 2 else 10)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
