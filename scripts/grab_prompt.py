#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
grab_prompt.py — 从 Web 会话抓取 local 生成的提示词并写入 args_gen.json

local（8B）不会调用工具写文件，只会把提示词作为文本输出到会话里。
本脚本从最新 local 会话的最后一条 assistant 消息中提取提示词，
校验（纯英文/质量前缀）后写入 args_gen.json，供生图任务使用。

用法：
  python grab_prompt.py                # 抓取最新 local 会话的最后 assistant 文本
  python grab_prompt.py --session <id> # 指定会话文件
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

SESSIONS_DIR = Path(os.environ.get("WEBUI_SESSIONS", "")) if os.environ.get("WEBUI_SESSIONS") else None
BASE = Path(__file__).resolve().parent.parent / "workspace"
OUT_FILE = BASE / "args_gen.json"  # 旧单文件（兼容）
CHAR_FILE = BASE / "args_character.json"  # 角色+画师独立文件
DESC_FILE = BASE / "args_description.json"  # 场景描述独立文件

# 质量前缀 / 常见提示词特征
QUALITY_MARKERS = ["masterpiece", "best quality", "score_9", "very aesthetic", "highres", "absurdres"]
NON_LATIN = re.compile(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af\u0400-\u04ff]")


def latest_local_session() -> Path:
    """找最新的 local profile 会话文件。"""
    best = None
    for f in SESSIONS_DIR.glob("*.json"):
        if f.name.startswith("_"):
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if d.get("profile") == "local":
            if best is None or f.stat().st_mtime > best.stat().st_mtime:
                best = f
    if best is None:
        sys.exit("❌ 没有找到 local 会话")
    return best


def extract_prompt(session_file: Path) -> str:
    """从会话最后一条 assistant 文本提取提示词（清洗杂质）。"""
    d = json.loads(session_file.read_text(encoding="utf-8"))
    msgs = d.get("messages", [])
    # 从后往前找最后的 assistant 消息（跳过 tool/error 类型）
    for m in reversed(msgs):
        if m.get("role") != "assistant":
            continue
        c = m.get("content")
        if not isinstance(c, str):
            continue
        text = c.strip()
        # 跳过明显的错误/取消消息
        if text.startswith("**") or "Task cancelled" in text or "Context" in text:
            continue
        # 清理 markdown 代码块
        text = re.sub(r"```(?:json|bash|python)?", "", text).strip()
        if not re.search(r"masterpiece|score_9|very aesthetic", text, re.IGNORECASE):
            continue
        return clean_prompt(text)
    sys.exit("❌ 会话里没找到提示词（需要包含 masterpiece/score_9 等质量标记的 assistant 消息）")


def clean_prompt(text: str) -> str:
    """从脏输出中提取干净的提示词主体。

    策略：找到 masterpiece 开头的一段，在杂质处截断：
    - 中文/日文出现处截断（标签应是纯英文）
    - 「画师」「查索引」「python」「```」「：」等杂质标记截断
    - 剥离角色名标签（ayaka_(...) 等带括号的 character 标签）
    """
    # 1) 找 masterpiece 起始
    m = re.search(r"(masterpiece,?\s+very aesthetic[^。\n]*)", text, re.IGNORECASE)
    if not m:
        m = re.search(r"(masterpiece[^。\n]*)", text, re.IGNORECASE)
    if not m:
        return text
    prompt = m.group(1).strip()

    # 2) 在中文/日文/杂质标记处截断
    cut = len(prompt)
    for marker in [r"[\u4e00-\u9fff]", r"[\u3040-\u30ff]", r"画师", r"查索引",
                   r"python", r"```", r"^\s*(请|建议|注意|例如)", r"："]:
        mm = re.search(marker, prompt)
        if mm:
            cut = min(cut, mm.start())
    prompt = prompt[:cut].strip()

    # 2.5) 剥离角色名标签：形如 xxx_(系列) 的 character 标签（节点11负责角色，描述里不允许）
    #      保留 2girls/1girl 等人数标签
    prompt = re.sub(r",\s*[a-z0-9_]+\([^)]*\)", "", prompt, flags=re.IGNORECASE)

    # 3) 去掉尾部悬空逗号
    prompt = re.sub(r",\s*$", "", prompt).strip()
    return prompt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", default=None, help="指定会话文件（默认最新 local 会话）")
    ap.add_argument("--character", default=None, help="角色+画师（用户指定，如 '@dairi qin_(arknights)'）")
    args = ap.parse_args()

    session_file = Path(args.session) if args.session else latest_local_session()
    print(f"▶ 会话: {session_file.name}")
    description = extract_prompt(session_file)

    # 校验描述（纯英文）
    if NON_LATIN.search(description):
        sys.exit(f"❌ 描述含中文/日文，拒绝写入:\n{description[:120]}")

    # 角色+画师：优先参数/已有值，否则从用户需求提取
    # 注意：绝不覆盖已有的 character（那是 default 写好的标准标签）
    existing = ""
    if CHAR_FILE.exists():
        try:
            existing = str(json.loads(CHAR_FILE.read_text(encoding="utf-8")).get("character", ""))
        except Exception:
            pass
    elif ARGS_FILE.exists():
        try:
            existing = str(json.loads(ARGS_FILE.read_text(encoding="utf-8")).get("character", ""))
        except Exception:
            pass
    character = args.character or existing or extract_character(session_file)
    if not character:
        print("⚠️ 未提取到角色/画师（用空字符串，仅提交描述）")

    # 组装：角色+画师 / 描述 分属两个独立文件
    cdata = {}
    if CHAR_FILE.exists():
        try:
            cdata = json.loads(CHAR_FILE.read_text(encoding="utf-8"))
        except Exception:
            cdata = {}
    cdata["character"] = character
    CHAR_FILE.write_text(json.dumps(cdata, ensure_ascii=False, indent=2), encoding="utf-8")
    DESC_FILE.write_text(json.dumps({"description": description}, ensure_ascii=False, indent=2), encoding="utf-8")
    # 同步旧单文件（兼容回退）
    out = {"character": character, "description": description}
    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("=" * 60)
    print(f"✅ 已写入: {CHAR_FILE} + {DESC_FILE.name}")
    print(f"   角色+画师: {character[:80]}")
    print(f"   描述: {description[:100]}{'...' if len(description) > 100 else ''}")
    print("=" * 60)


def extract_character(session_file: Path) -> str:
    """从会话第一条 user 消息提取角色/画师（用户需求开头的人名）。"""
    try:
        d = json.loads(session_file.read_text(encoding="utf-8"))
    except Exception:
        return ""
    msgs = d.get("messages", [])
    for m in msgs:
        if m.get("role") != "user":
            continue
        c = str(m.get("content", ""))
        if not c or c.startswith("[Workspace"):
            continue
        # 提取英文角色名（如 qin / raiden shogun / @dairi）
        m2 = re.search(r"(@[a-z0-9_]+|[a-z][a-z0-9_ ]{2,30})", c, re.IGNORECASE)
        if m2:
            return m2.group(1).strip()
        return c[:50].strip()
    return ""


if __name__ == "__main__":
    main()
