#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ComfyUI detached 启动（脱离 agent 进程管理，常驻）"""
import os
import subprocess, sys, time, urllib.request
from pathlib import Path

COMFY = Path(os.environ.get("COMFY_DIR", Path.home() / "ComfyUI"))
PY = Path(os.environ.get("COMFY_PY", COMFY / "venv" / "Scripts" / "pythonw.exe"))  # pythonw = 无窗口启动（有窗口会被手动关闭 → window-CLOSE 杀 ComfyUI）
LOG = Path(os.environ.get("COMFY_LOG", COMFY / "comfy_detached.log"))
PORT = int(os.environ.get("COMFY_PORT", "8188"))
# 可选：显式指定 ComfyUI 的输入/输出目录（多实例并存时避免互相覆盖）
OUT_DIR = os.environ.get("COMFY_OUT_DIR", "")
IN_DIR = os.environ.get("COMFY_IN_DIR", "")

# 探活：已在线则不重复启动
try:
    urllib.request.urlopen(f'http://127.0.0.1:{PORT}/system_stats', timeout=3)
    print(f'ComfyUI 已在线（{PORT}），跳过启动')
    sys.exit(0)
except Exception:
    pass

extra_args = []
if OUT_DIR:
    extra_args += ["--output-directory", OUT_DIR]
if IN_DIR:
    extra_args += ["--input-directory", IN_DIR]

with open(LOG, 'ab') as out:
    p = subprocess.Popen(
        [str(PY), '-E', 'main.py', '--listen', '127.0.0.1', '--port', str(PORT)] + extra_args,
        cwd=str(COMFY),
        stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )
print(f'ComfyUI detached 已发起 (pid={p.pid})，日志: {LOG}')
