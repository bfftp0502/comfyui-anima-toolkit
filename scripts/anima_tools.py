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
  python anima_tools.py cloth-rand            # 服装随机抽 1 个（全库）
  python anima_tools.py pose-rand             # 姿势随机抽 1 个（全库）
  python anima_tools.py background-rand       # 背景随机抽 1 个（抽卡用）
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
    # ── 权重相关（默认注释，等权随机）──
    # 想按作品数加权（画得多的画师更容易被抽到），并给带括号画师降权 ×0.3，去掉下面注释即可：
    # weights = []
    # for name, pc in rows:
    #     w = max(pc, 10)
    #     if "(" in name:
    #         w *= 0.3
    #     weights.append(w)
    # pick = random.choices([r[0] for r in rows], weights=weights, k=1)[0]
    pick = random.choice([r[0] for r in rows])
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
    # ── 权重相关（默认注释，等权随机）──
    # 想按 post_count 加权（热门角色更容易被抽到），去掉下面注释即可：
    # picks = random.choices([r[0] for r in rows],
    #                        weights=[max(r[1], 10) for r in rows], k=k)
    picks = random.choices([r[0] for r in rows], k=k)
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


def cloth_random():
    c = db()
    rows = c.execute("SELECT name FROM clothing").fetchall()
    c.close()
    if not rows:
        print("无匹配"); return
    print(random.choice(rows)[0])


def pose_random():
    c = db()
    rows = c.execute("SELECT name FROM poses").fetchall()
    c.close()
    if not rows:
        print("无匹配"); return
    print(random.choice(rows)[0])


def bg_random():
    c = db()
    rows = c.execute("SELECT name FROM backgrounds").fetchall()
    c.close()
    if not rows:
        print("无匹配"); return
    print(random.choice(rows)[0])


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
    elif cmd == "cloth-rand":
        cloth_random()
    elif cmd == "pose-rand":
        pose_random()
    elif cmd == "background-rand":
        bg_random()
    elif cmd == "pose" and len(args) > 1:
        pose_search(args[1], int(args[2]) if len(args) > 2 else 10)
    elif cmd == "background" and len(args) > 1:
        bg_search(args[1], int(args[2]) if len(args) > 2 else 10)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
