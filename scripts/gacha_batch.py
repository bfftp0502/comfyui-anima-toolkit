#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抽卡连抽 N 张：角色固定，服装/画师/姿势/背景每张随机（全库抽取，不区分 SFW/R18）。
用法: python gacha_batch.py <N> <角色tag> [固定画师@名]
  例: python gacha_batch.py 5 nahida_(genshin_impact)
依赖: 同目录 anima_tools.py / run_latest.py；ComfyUI 运行中
交付: 脚本只出图+复制改名到 change_name/ +打印路径，交付由 agent 按流程执行
"""
import subprocess, json, os, re, datetime, sys, sqlite3, time, shutil, random, base64, urllib.parse, urllib.request
from pathlib import Path

# Windows 控制台默认 GBK：强制 stdout/stderr 走 UTF-8，避免中文/图标打印崩溃
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent.parent           # 仓库根目录
SCRIPT_DIR = Path(__file__).resolve().parent                # 脚本目录
WORKSPACE = Path(os.environ.get("RUN_IMAGE_WORKSPACE", BASE_DIR / "workspace"))
ANIMA_DB = BASE_DIR / "data" / "anima_tools.sqlite"
OUT_DIR = Path(os.environ.get("COMFY_OUTPUT_DIR", Path.home() / "ComfyUI" / "output")) / "change_name"
ENV_FILE = Path(os.environ.get("DANBOORU_ENV", Path.home() / ".env"))
PROXY = os.environ.get("HTTPS_PROXY", "") or os.environ.get("http_proxy", "") or ""
COMFY_API = os.environ.get("COMFY_API", "http://127.0.0.1:8188").rstrip("/")

# 背景过滤：猎奇/脏乱场景、混进来的服装条目、拼音残留条目
BAD_BG = ["trypophobia", "toilet", "severed", "blood", "corpse", "death",
          "gore", "dead", "bathroom", "shower", "skin", "ghost",
          "outfit", "clothes", "clothing", "dress", "skirt", "shirt", "jacket",
          "coat", "pants", "uniform", "costume", "swimsuit", "bikini", "lingerie", "underwear",
          "tianliang", "duohe", "fangdongye",           # 背景库混入的拼音残留条目
          "internal organs", "organs"]                   # 猎奇内脏

NEG_STD = ("lowres, bad anatomy, bad hands, worst quality, blurry, watermark, signature, "
           "text, monochrome, oil painting, greasy, glossy, score_1, score_2, score_3, "
           "bad proportions, deformed anatomy, deformed face, deformed eyes, "
           "multiple fingers, artist name, 1boy, hetero, yuri, facing away")

# 服装互斥处理：矛盾条目不重抽，随机二选一——选到的进正面，没选到的进负面
CLOTH_CONFLICT = [
    (["barefoot", "unworn", "shoeless", "shoefree"],
     ["shoes", "high heels", "boots", "sneakers", "loafers", "sandals", "slippers",
      "stockings", "thighhighs", "socks", "tights", "pantyhose", "footwear"]),
    (["naked", "nude", "fully nude"],
     ["hanfu", "dress", "kimono", "qipao", "uniform", "suit", "armor", "outfit", "gown",
      "skirt", "shirt", "jacket", "bikini", "swimsuit", "bodysuit", "costume", "maid"]),
]

# 姿势过滤：双人互动 / 需要第二人的姿势（单人图必错）+ 异常字符条目
POSE_BAD = ["another", "carry me", "piggyback", "bridal", "handholding", "holding hands",
            "kissing", "embrace", "cuddling", "lap pillow", "face sitting",
            "scissoring", "tribadism", "making out", "sixty nine",
            "penetration", "handjob", "fellatio", "blowjob", "cunnilingus",
            "intercourse", "sex"]

# 易出多人 / 风格不稳的画师降权 ×0.3（按画师名子串匹配，可自行追加）
# 注意：只有「画师池加权」那段代码启用时才生效，默认是等权随机
LOW_WEIGHT_ARTISTS = ["utori"]

# ── 提示词各槽位权重（默认全 1.0 = 不加权重，原样写入）──
# >1 强化、<1 弱化。例如：pose 调 1.2、bg 调 0.8 → 姿势更突出、背景更弱；
# 想弱化画师风格（让角色更像）把 artist 设 0.5。
# 注意：库里自带权重的服装条目（如 "(Fedora:1.1)"）权重=1.0 时原样保留，
#       改槽位权重时会被跳过、不再套一层（避免出现 (x:1.1:1.2) 这种非法写法）。
WEIGHTS = {
    "quality": 1.0,      # masterpiece / very aesthetic / best quality
    "subject": 1.0,      # 1girl / solo
    "appearance": 1.0,   # 发色/瞳色锚定
    "cloth": 1.0,        # 服装（复合条目拆 & 后逐个处理）
    "pose": 1.0,
    "bg": 1.0,
    "artist": 1.0,
}

QUALITY_TAGS = ["masterpiece", "very aesthetic", "best quality"]
SUBJECT_TAGS = ["1girl", "solo"]
_WEIGHTED_RE = re.compile(r"\([^()]*:[\d.]+\)$")


def w(tag, weight):
    """给单个标签套权重；权重=1.0 或标签本身已有权重语法时原样返回"""
    tag = (tag or "").strip()
    if not tag or abs(weight - 1.0) < 1e-6 or _WEIGHTED_RE.search(tag):
        return tag
    return f"({tag}:{weight})"

# 服装库混入的非服装条目（动作/持械/机械/角色主题），命中重抽——是「条目类型」过滤，不是内容分级
CLOTH_EXTRA_BAD = ["holding", "carry", "gun", "rifle", "sword", "polearm", "revolver",
                   "hammer", "axe", "shield", "weapon", "ar-15", "assault", "lance", "blade",
                   "pistol", "katana", "scepter", "cyborg", "mechanical", "machinery", "mecha",
                   "cyberpunk", "cyberwitch", "robot", "ninja", "valkyrie", "necromancer",
                   "wizard", "knight", "solider", "soldier", "geisha", "onmyoji", "vampire",
                   "slime", "bride", "detective", "ballerina", "bloodborne", "fire keeper",
                   "deerstalker", "warhammer", "demon", "angel wings", "cat girl"]

# ── 服装抽取加权（默认注释，等权全库随机）──
# 想提高「正常衣服」权重、压低擦边服装（正常 5 : 擦边 1），把下面整段取消注释，
# 再把下面循环里的 cloth = pick(...) 换成这段：
#   cloth = None
#   for _ in range(12):
#       cand = cloth_weighted_rand()
#       if not any(b in cand.lower() for b in CLOTH_EXTRA_BAD):
#           cloth = cand
#           break
#   cloth = cloth or "Elegant Dress"
# NORMAL_CLOTH_EXTRA = ["swimsuit", "bikini", "lingerie", "underwear", "bra", "panties",
#                       "thighhighs", "stockings", "tights", "garter", "fishnet", "see-through",
#                       "transparent", "low cut", "plunging", "off-shoulder", "tube top",
#                       "crop top", "halter", "camisole", "slip", "negligee", "bodysuit",
#                       "corset", "bustier", "midriff", "bare shoulders", "exposed",
#                       "revealing", "skirt lift", "dress lift"]
#
# def cloth_weighted_rand():
#     db = sqlite3.connect(f"file:{ANIMA_DB}?mode=ro", uri=True)
#     names = [r[0] for r in db.execute("SELECT name FROM clothing").fetchall()]
#     db.close()
#     weights = [1 if any(w in n.lower() for w in NORMAL_CLOTH_EXTRA) else 5 for n in names]
#     return random.choices(names, weights=weights, k=1)[0]


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=60)
    return r.stdout.strip()


def pick(cmd, bad_list=(), max_try=10, alpha_only=False, valid_only=False):
    for _ in range(max_try):
        v = run(cmd)
        if not v:
            continue
        if any(b in v.lower() for b in bad_list):
            continue
        if alpha_only and not v[0].isalpha():
            continue
        if valid_only and re.search(r"[\\|/]", v):
            continue
        return v
    return "Simple Background"


def strip_weight(s):
    return re.sub(r"\(([^():]*):[\d.]+\)", r"\1", s)


def side_of(p):
    """part 归属：(互斥组索引, 侧 'a'/'b') 或 None；自相矛盾 part（含同组两侧词）归该组 a 侧"""
    c = p.lower()
    for idx, (a, b) in enumerate(CLOTH_CONFLICT):
        has_a = any(w in c for w in a)
        has_b = any(w in c for w in b)
        if has_a and has_b:
            return (idx, 'a')
        if has_a:
            return (idx, 'a')
        if has_b:
            return (idx, 'b')
    return None


def _conflict_group(sides):
    """返回存在 a/b 两侧的互斥组索引，无则 None"""
    for idx in range(len(CLOTH_CONFLICT)):
        g = [s for s in sides if s and s[0] == idx]
        if any(s[1] == 'a' for s in g) and any(s[1] == 'b' for s in g):
            return idx
    return None


def conflict_both(cloth):
    """条目拆 & 后同一互斥组两侧都有独立 part → 可二选一"""
    sides = [side_of(p.strip()) for p in cloth.split("&")]
    return _conflict_group(sides) is not None


def split_conflict_cloth(cloth):
    """互斥条目按 & 拆，随机二选一 → (正面词串, 负面词列表)"""
    parts = [p.strip() for p in cloth.split("&")]
    sides = [side_of(p) for p in parts]
    g = _conflict_group(sides)
    a_idx = [i for i, s in enumerate(sides) if s and s[0] == g and s[1] == 'a']
    b_idx = [i for i, s in enumerate(sides) if s and s[0] == g and s[1] == 'b']
    keep, drop = (a_idx, b_idx) if random.choice([True, False]) else (b_idx, a_idx)
    pos = ", ".join(parts[i] for i in keep)
    neg = [strip_weight(parts[i]) for i in drop]
    return pos, neg


def load_artist_pool(char_tag):
    """拉画过该角色的画师排行（频次榜近似）：18s 内多页拉取（每页 200 张，高分优先），
    按出现频次加权随机用。无网络/失败/超时 → None，回退全量 arand"""
    try:
        creds = {}
        if ENV_FILE.exists():
            for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    creds[k.strip()] = v.strip()
        user = os.environ.get("DANBOORU_USER", "") or creds.get("DANBOORU_USER", "")
        key = os.environ.get("DANBOORU_API_KEY", "") or creds.get("DANBOORU_API_KEY", "")
        if not (user and key):
            return None
        freq = {}
        page_id = None
        deadline = time.time() + 18  # 硬截止，避免连抽开始前卡太久
        while time.time() < deadline:
            params = {"tags": char_tag + " order:score", "limit": 200}
            if page_id:
                params["page"] = f"b{page_id}"
            url = "https://danbooru.donmai.us/posts.json?" + urllib.parse.urlencode(params)
            req = urllib.request.Request(url)
            req.add_header("Authorization", "Basic " + base64.b64encode(f"{user}:{key}".encode()).decode())
            req.add_header("User-Agent", "gacha-batch-bot/1.0")
            if PROXY:
                opener = urllib.request.build_opener(
                    urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))
            else:
                opener = urllib.request.build_opener()
            with opener.open(req, timeout=10) as r:
                data = json.load(r)
            if not data:
                break
            for p in data:
                artist = (p.get("tag_string_artist") or "").strip()
                if artist:
                    for a in artist.split(" "):
                        freq[a] = freq.get(a, 0) + 1
            page_id = data[-1]["id"]
        pool = sorted(((a, c) for a, c in freq.items()), key=lambda x: -x[1])
        return pool[:100] or None  # 只取频次前 100（画得最多的画师，特征遵循最好）
    except Exception:
        return None


def safe_name(s):
    s = s.replace("@", "")
    s = re.sub(r"[()\[\]&:/,.+*\\]", "_", s)
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def char_appearance(char_tag):
    """从 anima_tools characters 表查角色的 hair/eye（外观锚定）。
    只精确匹配完整角色名（含系列）；查不到不填外观——模糊匹配会串到同名角色"""
    norm = char_tag.replace("_", " ").strip()
    db = sqlite3.connect(f"file:{ANIMA_DB}?mode=ro", uri=True)
    rows = db.execute(
        "SELECT hair, eye FROM characters WHERE name = ? LIMIT 1",
        (norm,)).fetchall()
    db.close()
    if not rows:
        return None, None
    h = (rows[0][0] or "").strip()
    e = (rows[0][1] or "").strip()
    return (h or None), (e or None)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    CHAR = sys.argv[2] if len(sys.argv) > 2 else "furina_(genshin_impact)"
    ARTIST = sys.argv[3] if len(sys.argv) > 3 else ""  # 固定画师（传 @名；空=画师池/随机）
    py = sys.executable
    anima_tools = str(SCRIPT_DIR / "anima_tools.py")

    hair, eye = char_appearance(CHAR)
    appearance = ", ".join(x for x in (hair, eye) if x)
    nl_app = f"with {appearance}" if appearance else ""
    print(f"角色: {CHAR} | 外观锚定: {appearance or '库缺字段'}")

    # 固定角色 → 尝试拉「画过该角色的画师池」；失败回退 arand
    artist_pool = load_artist_pool(CHAR) if not ARTIST else None
    used_artists = set()
    if artist_pool:
        print(f"▶ 画师池加载成功（{len(artist_pool)} 位画过{CHAR.split('(')[0]}的画师，等权随机）")
    else:
        print("▶ 画师池不可用（无网络/超时/未配 danbooru 凭据），回退全量 arand 随机")

    results = []
    for i in range(N):
        # 服装：默认全库等权随机；想按「正常/擦边」加权见文件上方注释掉的 cloth_weighted_rand()
        cloth = pick([py, anima_tools, "cloth-rand"], bad_list=CLOTH_EXTRA_BAD)
        extra_neg = []
        if conflict_both(cloth):
            cloth, extra_neg = split_conflict_cloth(cloth)  # 互斥二选一：保留侧进正面，丢弃侧进负面
        if ARTIST:
            artist = ARTIST
        elif artist_pool:
            cands = [(n, c) for n, c in artist_pool if n not in used_artists]
            if cands:
                names = [n for n, _ in cands]
                # ── 权重相关（默认注释，等权随机）──
                # 想让「画得多的画师」更容易被抽到，去掉下两行注释即可；
                # weights = [max(c, 1) * (0.3 if any(a in n.lower() for a in LOW_WEIGHT_ARTISTS) else 1)
                #            for n, _ in cands]
                # artist = "@" + random.choices(names, weights=weights, k=1)[0]
                artist = "@" + random.choice(names)
                used_artists.add(artist[1:])
            else:
                artist = run([py, anima_tools, "arand"])
        else:
            artist = run([py, anima_tools, "arand"])
        pose = pick([py, anima_tools, "pose-rand"], bad_list=POSE_BAD,
                    alpha_only=True, valid_only=True)
        bg = pick([py, anima_tools, "background-rand"], BAD_BG)

        cloth_tags = ", ".join(w(p, WEIGHTS["cloth"]) for p in cloth.split("&") if p.strip())
        # ── 各槽位按 WEIGHTS 逐个套权重（默认 1.0，等于原样写入）──
        # 想让画师风格弱一点、角色更像：把 WEIGHTS["artist"] 改成 0.5 即可
        head_parts = ([w(t, WEIGHTS["quality"]) for t in QUALITY_TAGS]
                      + [w(t, WEIGHTS["subject"]) for t in SUBJECT_TAGS]
                      + [w(x, WEIGHTS["appearance"]) for x in (hair, eye) if x]
                      + [cloth_tags,
                         w(pose.lower().replace(" ", "_"), WEIGHTS["pose"]),
                         w(bg.lower().replace(" ", "_"), WEIGHTS["bg"]),
                         w(artist, WEIGHTS["artist"])])
        desc = (f"{', '.join(p for p in head_parts if p)}, "
                f"natural language: a girl {nl_app}, "
                f"wearing {cloth}, set in {bg}, lively and charming")
        negative = NEG_STD
        if extra_neg:
            negative += ", " + ", ".join(extra_neg)
        files = {
            "args_character.json": {"character": CHAR},
            "args_description.json": {"description": desc},
            "args_negative.json": {"negative": negative},
        }
        for fn, obj in files.items():
            with open(os.path.join(WORKSPACE, fn), "w", encoding="utf-8") as f:
                json.dump(obj, f, ensure_ascii=False)

        r = subprocess.run([py, str(SCRIPT_DIR / "run_latest.py"), "--target", "anima",
                            "--mode", "run", "--no-grab", "--no-free",
                            "--width", "864", "--height", "1536"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=610, cwd=str(WORKSPACE))
        out = r.stdout + r.stderr
        m = re.search(r"出图完成: (.+?)\n", out)
        if not m:
            print(f"[{i+1}] FAILED: {out[-300:]}")
            results.append(None)
            continue
        src = m.group(1).strip()
        time.sleep(1)  # 出图后等 1 秒再复制改名，给 ComfyUI 前端轮询 output 留窗口
        ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        new = os.path.join(OUT_DIR, f"anima-{safe_name(CHAR)}-{safe_name(artist)}-{ts}.png")
        shutil.copy2(src, new)  # 复制到 change_name 并改名；原图保留在输出目录
        results.append(new)
        print(f"[{i+1}/{N}] {cloth} | {artist} | {pose} | {bg}\n    -> {new}")

    # 整批结束统一释放显存（连抽不逐张 /free，省模型重载）
    try:
        req = urllib.request.Request(f"{COMFY_API}/free",
                                     data=json.dumps({"unload_models": True, "free_memory": True}).encode(),
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=15)
        print("✅ 批次结束已释放显存（/free）")
    except Exception as e:
        print(f"⚠️ 批次结束 /free 失败: {e}")

    print("=== DONE ===")
    for p in results:
        if p:
            print(p)


if __name__ == "__main__":
    main()
