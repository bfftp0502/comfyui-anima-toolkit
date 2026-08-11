#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
set_character.py — 「跑图」口令处理：写角色画师

default 收到「跑图」口令时调用：
  1. 写入 character 字段到 args_character.json（角色+画师，由参数/随机逻辑决定）
  2. 同步旧单文件 args_gen.json（兼容回退）

用法：
  python set_character.py "uzumaki_naruto @dairi"   # 指定角色画师
  python set_character.py random                     # 随机角色+画师
"""
import json
import random
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "workspace"
ARGS_FILE = BASE / "args_gen.json"  # 旧单文件（兼容）
CHAR_FILE = BASE / "args_character.json"  # 角色+画师独立文件


def main():
    if len(sys.argv) < 2:
        print("用法: python set_character.py \"角色 画师\" | random")
        sys.exit(1)
    arg = sys.argv[1]

    if arg.lower() == "random":
        r = subprocess.run([sys.executable, str(Path(__file__).resolve().parent / "random_char.py"), "--both"],
                           capture_output=True, text=True, timeout=60)
        character = r.stdout.strip()
    else:
        character = arg.strip()

    if not character:
        print("❌ 角色画师为空")
        sys.exit(1)

    # 写角色+画师到独立文件 args_character.json（场景描述在另一个文件，互不干扰）
    data = {}
    if CHAR_FILE.exists():
        try:
            data = json.loads(CHAR_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data["character"] = character
    CHAR_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    # 同步旧单文件（兼容回退：保留 description，只更新 character）
    if ARGS_FILE.exists():
        try:
            odata = json.loads(ARGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            odata = {}
        odata["character"] = character
        ARGS_FILE.write_text(json.dumps(odata, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✅ character 已写入: {character}")


if __name__ == "__main__":
    main()
