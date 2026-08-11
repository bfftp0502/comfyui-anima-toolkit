#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ComfyUI detached 启动（脱离 agent 进程管理，常驻）"""
import os
import subprocess, sys, time, urllib.request
from pathlib import Path

COMFY = Path(os.environ.get("COMFY_DIR", Path.home() / "ComfyUI"))
PY = Path(os.environ.get("COMFY_PY", COMFY / "venv" / "Scripts" / "python.exe"))
LOG = Path(os.environ.get("COMFY_LOG", COMFY / "comfy_detached.log"))
PORT = int(os.environ.get("COMFY_PORT", "8188"))

# 探活：已在线则不重复启动
try:
    urllib.request.urlopen(f'http://127.0.0.1:{PORT}/system_stats', timeout=3)
    print(f'ComfyUI 已在线（{PORT}），跳过启动')
    sys.exit(0)
except Exception:
    pass

with open(LOG, 'ab') as out:
    p = subprocess.Popen(
        [str(PY), '-E', 'main.py', '--listen', '127.0.0.1', '--port', str(PORT)],
        cwd=str(COMFY),
        stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )
print(f'ComfyUI detached 已发起 (pid={p.pid})，日志: {LOG}')
