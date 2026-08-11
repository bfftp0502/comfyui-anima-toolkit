#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""解析 Comfyui-Anima-Tools 的五个 JS 数据文件 -> anima_tools.sqlite
数据源: <Comfyui-Anima-Tools>/js/data.js / character_data.js / clothing_data.js / pose_data.js / background_data.js（环境变量 ANIMA_TOOLS_JS 指定）
用法: python build_anima_tools_db.py
"""
import json, os, re, sqlite3, sys
from pathlib import Path

SRC = Path(os.environ.get("ANIMA_TOOLS_JS", r"C:\ComfyUI\custom_nodes\Comfyui-Anima-Tools\js"))
OUT = Path(__file__).resolve().parent.parent / "data" / "anima_tools.sqlite"


def parse_js_var(path: Path) -> list:
    txt = path.read_text(encoding="utf-8-sig")
    start = txt.find("[")
    end = txt.rfind("];")
    if start < 0 or end <= start:
        raise ValueError(f"cannot parse {path}")
    return json.loads(txt[start:end + 1])


def main():
    artists = parse_js_var(SRC / "data.js")
    chars = parse_js_var(SRC / "character_data.js")
    cloth = parse_js_var(SRC / "clothing_data.js")
    poses = parse_js_var(SRC / "pose_data.js")
    bgs = parse_js_var(SRC / "background_data.js")
    print(f"artists={len(artists)} characters={len(chars)} clothing={len(cloth)} poses={len(poses)} backgrounds={len(bgs)}")

    db = sqlite3.connect(OUT)
    db.execute("DROP TABLE IF EXISTS artists")
    db.execute("DROP TABLE IF EXISTS characters")
    db.execute("DROP TABLE IF EXISTS clothing")
    db.execute("DROP TABLE IF EXISTS poses")
    db.execute("DROP TABLE IF EXISTS backgrounds")
    db.execute("""CREATE TABLE artists(
        id TEXT, name TEXT, post_count INT, uniqueness_score REAL)""")
    db.execute("""CREATE TABLE characters(
        name TEXT, copyright TEXT, post_count INT, gender TEXT, hair TEXT, eye TEXT)""")
    db.execute("""CREATE TABLE clothing(
        id TEXT, name TEXT, name_zh TEXT, tags TEXT, categories TEXT, traits TEXT)""")
    db.execute("""CREATE TABLE poses(
        id TEXT, name TEXT, name_zh TEXT, tags TEXT, categories TEXT, traits TEXT)""")
    db.execute("""CREATE TABLE backgrounds(
        id TEXT, name TEXT, name_zh TEXT, tags TEXT, categories TEXT, traits TEXT)""")

    db.executemany("INSERT INTO artists VALUES(?,?,?,?)",
                   [(a.get("id"), a.get("name"), a.get("post_count", 0), a.get("uniqueness_score", 0)) for a in artists])
    db.executemany("INSERT INTO characters VALUES(?,?,?,?,?,?)",
                   [(c.get("name"), c.get("copyright"), c.get("post_count", 0), c.get("gender"), c.get("hair"), c.get("eye")) for c in chars])
    db.executemany("INSERT INTO clothing VALUES(?,?,?,?,?,?)",
                   [(c.get("id"), c.get("name"), c.get("name_zh"), c.get("tags"), "|".join(c.get("categories", [])), "|".join(c.get("traits", []))) for c in cloth])
    db.executemany("INSERT INTO poses VALUES(?,?,?,?,?,?)",
                   [(p.get("id"), p.get("name"), p.get("name_zh"), p.get("tags"), "|".join(p.get("categories", [])), "|".join(p.get("traits", []))) for p in poses])
    db.executemany("INSERT INTO backgrounds VALUES(?,?,?,?,?,?)",
                   [(b.get("id"), b.get("name"), b.get("name_zh"), b.get("tags"), "|".join(b.get("categories", [])), "|".join(b.get("traits", []))) for b in bgs])

    db.execute("CREATE INDEX idx_art_name ON artists(name)")
    db.execute("CREATE INDEX idx_art_count ON artists(post_count DESC)")
    db.execute("CREATE INDEX idx_char_name ON characters(name)")
    db.execute("CREATE INDEX idx_char_copy ON characters(copyright)")
    db.execute("CREATE INDEX idx_pose_name ON poses(name)")
    db.execute("CREATE INDEX idx_pose_zh ON poses(name_zh)")
    db.execute("CREATE INDEX idx_bg_name ON backgrounds(name)")
    db.execute("CREATE INDEX idx_bg_zh ON backgrounds(name_zh)")
    db.execute("COMMIT")
    db.close()
    print(f"OK -> {OUT}")


if __name__ == "__main__":
    main()
