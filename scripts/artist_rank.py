#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
artist_rank.py — 查 danbooru 某角色的画师排行（作品数 + 平均分）

用法:
  python artist_rank.py "<角色canonical tag>"
  python artist_rank.py "furina_(genshin_impact)"

输出: 画师排行 @tag（作品数榜 + 平均分榜，平均分榜只算作品 >= 10 张的画师）
凭据: 读环境变量或 ~/.env 的 DANBOORU_USER / DANBOORU_API_KEY / DANBOORU_USER_ID
限速: danbooru 读取限速 10 req/s（全球共享），本脚本 0.15s/请求 ≈ 6.7 req/s
翻页: page=b<id> 游标，limit=200（posts.json 上限）
"""
import base64
import collections
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ENV = Path(os.environ.get("DANBOORU_ENV", Path.home() / ".env"))
PROXY = os.environ.get("HTTPS_PROXY", "") or os.environ.get("http_proxy", "") or ""  # 代理（danbooru 国内直连不通），可留空
SLEEP = 0.15
MIN_COUNT_FOR_AVG = 10


def load_env():
    creds = {}
    for line in ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            creds[k.strip()] = v.strip()
    return creds


def api_get(path, params):
    url = f"https://danbooru.donmai.us/{path}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    token = base64.b64encode(f"{USER}:{API_KEY}".encode()).decode()
    req.add_header("Authorization", f"Basic {token}")
    req.add_header("User-Agent", "artist-rank-bot/1.0 (danbooru artist ranking)")
    if PROXY:
        proxy = urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})
        opener = urllib.request.build_opener(proxy)
    else:
        opener = urllib.request.build_opener()
    with opener.open(req, timeout=30) as r:
        return json.load(r)


def main(tag):
    stats = collections.defaultdict(lambda: [0, 0])  # artist -> [count, score_sum]
    page_id = None
    total = 0
    while True:
        params = {"tags": tag, "limit": 200}
        if page_id:
            params["page"] = f"b{page_id}"
        data = api_get("posts.json", params)
        if not data:
            break
        for p in data:
            artist = (p.get("tag_string_artist") or "").strip()
            score = p.get("score") or 0
            if artist:
                for a in artist.split(" "):
                    stats[a][0] += 1
                    stats[a][1] += score
        total += len(data)
        print(f"\r已拉取 {total} 张（{len(stats)} 位画师）...", end="", flush=True)
        page_id = data[-1]["id"]
        time.sleep(SLEEP)
    print()

    if not stats:
        print(f"（{tag} 无结果——检查角色 tag 是否正确）")
        return

    by_count = sorted(stats.items(), key=lambda x: -x[1][0])
    by_avg = sorted(
        ((a, c, s / c) for a, (c, s) in stats.items() if c >= MIN_COUNT_FOR_AVG),
        key=lambda x: -x[2],
    )

    print(f"\n== {tag} 画师排行（共 {total} 张图）==")
    print(f"\n--- 作品数榜 ---")
    print(f"{'画师':<32}{'张数':>7}{'平均分':>8}")
    for a, (c, s) in by_count[:20]:
        print(f"@{a:<30}{c:>7}{s / c if c else 0:>8.1f}")
    print(f"\n--- 平均分榜（作品>={MIN_COUNT_FOR_AVG} 张）---")
    print(f"{'画师':<32}{'张数':>7}{'平均分':>8}")
    for a, c, avg in by_avg[:20]:
        print(f"@{a:<30}{c:>7}{avg:>8.1f}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python artist_rank.py <角色canonical tag>")
        sys.exit(1)
    creds = load_env()
    USER = creds.get("DANBOORU_USER", "")
    API_KEY = creds.get("DANBOORU_API_KEY", "")
    USER_ID = creds.get("DANBOORU_USER_ID", "")
    if not (USER and API_KEY):
        print("[错误] .env 缺少 DANBOORU_USER / DANBOORU_API_KEY")
        sys.exit(1)
    main(sys.argv[1])
