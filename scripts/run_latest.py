#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_latest.py — 「生图/跑图」核心：读三文件（角色/描述/负面），按模板+模式组装并提交 ComfyUI

流程：
  1. 读 args_character.json / args_description.json / args_negative.json（三文件定稿）
  2. 按 --target anima + --mode direct|run 组装完整 args（节点映射 + 负面 + 随机 seed）
  3. 提交对应工作流 → 轮询等出图
  4. 记录输出图（image_track.py）→ 调 /free 卸载 ComfyUI 模型（不关 ComfyUI 进程）

用法：
  python run_latest.py --target anima --mode direct --no-grab [--width/--height]
  python run_latest.py --target anima --mode run --no-grab
"""
import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

# ===== 部署配置（环境变量可覆盖；未配置时按仓库相对位置/默认值）=====
BASE_DIR = Path(__file__).resolve().parent.parent          # 仓库根目录（comfyui-anima-toolkit/）
SCRIPT_DIR = Path(__file__).resolve().parent               # 脚本目录（comfyui-anima-toolkit/scripts/）
WORKSPACE = Path(os.environ.get("RUN_IMAGE_WORKSPACE", BASE_DIR / "workspace"))
COMFY_API = "http://127.0.0.1:8188"
OUTPUT_DIR = Path(os.environ.get("COMFY_OUTPUT_DIR", Path.home() / "ComfyUI" / "output"))
HERMES = os.environ.get("HERMES_BIN") or shutil.which("hermes") or "hermes"
QQ_OPENID = os.environ.get("QQ_OPENID", "")                 # 未配置 → 通知降级为仅打印（agent 播报）
QQ_TARGET = f"qqbot:{QQ_OPENID}" if QQ_OPENID else None
WEBUI_SESSIONS = os.environ.get("WEBUI_SESSIONS", "")       # 未配置 → 跳过自动抓取
ARGS_FILE = WORKSPACE / "args_gen.json"  # 旧单文件（兼容回退）
CHAR_FILE = WORKSPACE / "args_character.json"  # 角色+画师（独立文件，anima run 专用）
DESC_FILE = WORKSPACE / "args_description.json"  # 场景描述（独立文件，anima run 专用）
NEG_FILE = WORKSPACE / "args_negative.json"  # 负面词（独立文件）
PROMPT_FILE = WORKSPACE / "args_prompt.json"  # 整段正面（anima direct 专用）

# 模板 → 工作流（direct=双编码器生图 / run=三编码器跑图）、节点id、固定负向、尺寸节点id
# ⚠️ 用户定稿：生图流程只有两个 CLIPTextEncode（正面合并+负面）；跑图有三个（11/4 角色 + 66 描述 + 负面），67 ConditioningCombine(角色,描述) → positive
TEMPLATES = {
    "anima": {
        "workflow": "anima-txt2img-aesthetic-lora",       # direct（生图/直出）：双编码器
        "workflow_run": "anima-txt2img-aesthetic-lora-run",  # run（跑图）：三编码器 + Combine
        "char_id": "11",
        "desc_id": None,        # direct：描述并入角色节点
        "desc_id_run": "66",    # run：描述独立节点
        "neg_id": "12",
        "latent_id": "28",
        "negative": "lowres, bad anatomy, bad hands, worst quality, blurry, watermark, signature, text, monochrome, oil painting, greasy, glossy",
    },
}

def build_args(target: str, mode: str = "direct", width: int | None = None, height: int | None = None, batch: int | None = None) -> tuple[dict, Path]:
    """读角色/描述/负面独立文件（三文件定稿），组装对应模板的完整 args（写临时文件）。

    文件约定：
      args_prompt.json      → {"prompt": "整段正面"}  （anima direct：模型直接写含场景/角色/画师的一段，不拼接）
      args_character.json   → {"character": "角色+画师"}  （仅 anima run 三编码器用）
      args_description.json → {"description": "场景描述"}  （仅 anima run 三编码器用）
      args_negative.json    → {"negative": "负面词"}       （模板基础+按场景扩写）
    兼容旧 args_gen.json。

    mode:
      direct（生图/直出）→ 双编码器工作流：读 args_prompt.json 整段进正面节点（desc_id=None）
      run（跑图）        → anima 三编码器工作流：角色节点 + 描述节点 + ConditioningCombine
    """
    if target not in TEMPLATES:
        sys.exit(f"[错误] 未知模板 {target}，可用: {list(TEMPLATES)}")
    tpl = TEMPLATES[target]
    desc_id = tpl["desc_id_run"] if mode == "run" else tpl["desc_id"]

    # 整段直写优先（anima direct）
    if mode == "direct":
        if not PROMPT_FILE.exists():
            sys.exit("⚠️ 没有 args_prompt.json——先写整段正面提示词（{\"prompt\": \"...\"}）")
        try:
            pdata = json.loads(PROMPT_FILE.read_text(encoding="utf-8"))
            prompt_text = str(pdata.get("prompt", "") or pdata.get("description", "")).strip()
        except Exception as e:
            sys.exit(f"⚠️ args_prompt.json 解析失败: {e}")
        if not prompt_text:
            sys.exit("⚠️ args_prompt.json 里没有内容（需 prompt 字段）")

        # 负面词：优先 args_negative.json，否则模板默认
        negative = tpl["negative"]
        if NEG_FILE.exists():
            try:
                ndata = json.loads(NEG_FILE.read_text(encoding="utf-8"))
                if str(ndata.get("negative", "")).strip():
                    negative = str(ndata["negative"]).strip()
            except Exception:
                pass

        seed = random.randint(1, 2**31 - 1)
        args = {f"prompt_{tpl['char_id']}": prompt_text, f"prompt_{tpl['neg_id']}": negative, "seed": seed}
        if width or height:
            args["width"] = width or 0
            args["height"] = height or 0
        if batch:
            args["batch_size"] = batch
        tmp = WORKSPACE / f"_run_{target}.json"
        tmp.write_text(json.dumps(args, ensure_ascii=False, indent=2), encoding="utf-8")
        return args, tmp

    # anima run：三编码器工作流，角色/描述分文件
    character, description = "", ""
    if CHAR_FILE.exists() and DESC_FILE.exists():
        try:
            cdata = json.loads(CHAR_FILE.read_text(encoding="utf-8"))
            ddata = json.loads(DESC_FILE.read_text(encoding="utf-8"))
            character = str(cdata.get("character", "") or cdata.get("prompt", "")).strip()
            description = str(ddata.get("description", "") or ddata.get("prompt", "")).strip()
        except Exception as e:
            sys.exit(f"⚠️ args_character.json / args_description.json 解析失败: {e}")
    elif ARGS_FILE.exists():
        data = json.loads(ARGS_FILE.read_text(encoding="utf-8"))
        character = str(data.get("character", "") or data.get("prompt", "")).strip()
        description = str(data.get("description", "")).strip()
    else:
        sys.exit("⚠️ 没有提示词文件——先写角色/场景（set_character.py / set_scene.py）")

    if not character and not description:
        sys.exit("⚠️ 提示词文件里没有内容（需 character 或 description）")

    # 负面词：优先 args_negative.json，否则模板默认
    negative = tpl["negative"]
    if NEG_FILE.exists():
        try:
            ndata = json.loads(NEG_FILE.read_text(encoding="utf-8"))
            if str(ndata.get("negative", "")).strip():
                negative = str(ndata["negative"]).strip()
        except Exception:
            pass

    seed = random.randint(1, 2**31 - 1)
    args = {f"prompt_{tpl['neg_id']}": negative, "seed": seed}
    if character:
        args[f"prompt_{tpl['char_id']}"] = character
    if description and desc_id:
        if character:
            args[f"prompt_{desc_id}"] = description
        else:
            # character 空：描述进角色节点，防占位符进图
            args[f"prompt_{tpl['char_id']}"] = description
    elif description and not desc_id:
        args[f"prompt_{tpl['char_id']}"] = f"{character}, {description}" if character else description
    if width or height:
        args["width"] = width or 0
        args["height"] = height or 0
    if batch:
        args["batch_size"] = batch
    tmp = WORKSPACE / f"_run_{target}.json"
    tmp.write_text(json.dumps(args, ensure_ascii=False, indent=2), encoding="utf-8")
    return args, tmp


def submit(workflow: str, args_file: Path) -> str:
    cmd = ["node", "run_workflow_args.js", "submit", f"local/{workflow}", f"./{args_file.name}"]
    r = subprocess.run(cmd, cwd=WORKSPACE, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        sys.exit(f"[提交失败] {r.stderr[-500:] or r.stdout[-500:]}")
    return r.stdout


def wait_and_find_output(prompt_id: str, timeout_s: int = 600) -> Path:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{COMFY_API}/history", timeout=10) as resp:
                hist = json.load(resp)
            item = hist.get(prompt_id)
            if item:
                status = item.get("status", {})
                if status.get("completed") or status.get("status_str") == "success":
                    for out in item.get("outputs", {}).values():
                        for img in out.get("images", []):
                            p = OUTPUT_DIR / img.get("subfolder", "") / img["filename"]
                            if p.exists():
                                return p
                            p2 = OUTPUT_DIR / img["filename"]
                            if p2.exists():
                                return p2
                if status.get("status_str") == "error":
                    sys.exit(f"[生图失败] {json.dumps(status)[:300]}")
        except Exception:
            pass
        time.sleep(5)
    # 超时：先取消 ComfyUI 端任务再退出，避免任务残留/写管道卡死
    try:
        req = urllib.request.Request(f"{COMFY_API}/interrupt", data=b"", method="POST")
        urllib.request.urlopen(req, timeout=10)
        print("⚠️ 等出图超时，已向 ComfyUI 发送 /interrupt 取消任务")
    except Exception as e:
        print(f"⚠️ 超时后 /interrupt 失败: {e}")
    sys.exit("[超时] 等出图超过 10 分钟，已取消 ComfyUI 任务")


def free_comfyui_memory():
    try:
        req = urllib.request.Request(
            f"{COMFY_API}/free",
            data=json.dumps({"unload_models": True, "free_memory": True}).encode(),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=15)
        print("✅ 已卸载 ComfyUI 模型（/free），显存已释放")
    except Exception as e:
        print(f"⚠️ /free 调用失败: {e}")


def notify_qq_done():
    """跑图（mode=run）完成后 QQ 通知「跑图完成✅」。

    direct（直出）图直接发当前会话，不需要通知；run（跑图）出图在 Web 收图会话，
    必须通知用户去收图。未配置 QQ_OPENID 时降级为仅打印（由 agent 向用户播报）。
    """
    if not QQ_TARGET:
        print("✅ 出图完成（未配置 QQ_OPENID，由 agent 向用户播报「跑图完成✅」）")
        return
    try:
        r = subprocess.run(
            [HERMES, "send", "--to", QQ_TARGET, "跑图完成✅"],
            capture_output=True, text=True, timeout=60,
        )
        if r.returncode == 0:
            print("✅ QQ 通知已发送（跑图完成✅）")
        else:
            print(f"⚠️ QQ 通知发送失败: {r.stderr[-200:] or r.stdout[-200:]}")
    except Exception as e:
        print(f"⚠️ QQ 通知发送异常: {e}")


def find_fallback() -> Path:
    files = sorted(OUTPUT_DIR.rglob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        sys.exit("⚠️ 没找到输出图")
    return files[0]


def auto_grab_prompt() -> bool:
    """生图前自动抓取 WebUI 会话最新提示词：若最新会话比 args 文件新，则抓取覆盖。
    返回 True=已抓取/无需抓取/跳过；False=抓取失败，中止生图。
    需配置 WEBUI_SESSIONS（WebUI 会话目录）；未配置直接跳过。"""
    from pathlib import Path as _P
    if not WEBUI_SESSIONS:
        print("▶ 未配置 WEBUI_SESSIONS，跳过自动抓取（用现有 args）")
        return True
    sess_dir = _P(WEBUI_SESSIONS)
    best = None
    for f in sess_dir.glob("*.json"):
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
        print("⚠️ 没有 local 会话，跳过抓取（用现有 args）")
        return True
    newest_args_mtime = 0.0
    for f in (CHAR_FILE, DESC_FILE, NEG_FILE, ARGS_FILE):
        if f.exists():
            newest_args_mtime = max(newest_args_mtime, f.stat().st_mtime)
    if newest_args_mtime >= best.stat().st_mtime:
        print(f"▶ 提示词文件已是最新（{newest_args_mtime:.0f} ≥ 会话 {best.stat().st_mtime:.0f}），直接使用")
        return True
    print(f"▶ local 会话更新（{best.name}），自动抓取提示词...")
    grab = SCRIPT_DIR / "grab_prompt.py"
    if not grab.exists():
        print("⚠️ 未找到 grab_prompt.py，跳过抓取（用现有 args）")
        return True
    r = subprocess.run([sys.executable, str(grab)],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0 or not (DESC_FILE.exists() or ARGS_FILE.exists()):
        print(f"❌ 抓取失败: {r.stdout[-200:]} {r.stderr[-200:]}")
        print("   → 手动修正提示词后重试，或检查 local 会话输出")
        return False
    print("✅ 已自动抓取并写入 args_character.json + args_description.json")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True, choices=list(TEMPLATES), help="anima")
    ap.add_argument("--mode", choices=["direct", "run"], default="direct", help="direct=双编码器生图（默认）；run=三编码器跑图（角色+描述 Combine）")
    ap.add_argument("--width", type=int, default=None, help="覆盖宽度（如 832）")
    ap.add_argument("--height", type=int, default=None, help="覆盖高度（如 1216）")
    ap.add_argument("--no-grab", action="store_true", help="跳过 auto_grab_prompt（default 直出/跑图流程用）")
    ap.add_argument("--no-free", action="store_true", help="跳过跑完后的 /free 卸载（批量连抽用：整批结束后统一释放）")
    args = ap.parse_args()

    tpl = TEMPLATES[args.target]
    workflow = tpl["workflow_run"] if args.mode == "run" else tpl["workflow"]
    print(f"▶ 模板: {args.target} [{args.mode}] → 工作流 {workflow}")
    if args.width or args.height:
        print(f"▶ 尺寸: {args.width or '默认'} × {args.height or '默认'}")

    if not args.no_grab and not auto_grab_prompt():
        sys.exit("[中止] 提示词抓取失败，未提交")

    _, tmp_args = build_args(args.target, args.mode, args.width, args.height)
    print(f"▶ 已组装 args（正向 + 负面 + 随机 seed）: {tmp_args.name}")

    out = submit(workflow, tmp_args)
    prompt_id = None
    for line in out.splitlines():
        if "prompt_id" in line.lower() or "prompt" in line.lower():
            prompt_id = line.split()[-1].strip().strip('",:')
            break
    print("▶ 已提交，等出图...")

    img = wait_and_find_output(prompt_id) if prompt_id else find_fallback()
    subprocess.run([sys.executable, str(SCRIPT_DIR / "image_track.py"), "--record", str(img)],
                   capture_output=True, timeout=30)
    print(f"✅ 出图完成: {img}")

    if args.mode == "run":
        notify_qq_done()

    try:
        if ARGS_FILE.exists():
            (WORKSPACE / "args_consumed.txt").write_text(str(ARGS_FILE.stat().st_mtime), encoding="utf-8")
            print("▶ 已标记本版提示词为已消费")
    except Exception as e:
        print(f"⚠️ 消费标记写入失败: {e}")

    tmp_args.unlink(missing_ok=True)
    if not args.no_free:
        free_comfyui_memory()


if __name__ == "__main__":
    main()
