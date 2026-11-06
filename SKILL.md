---
name: comfyui-anima-toolkit
description: "Use when generating anime images via ComfyUI. Two flows: direct-gen (image sent to current chat) and run-image (step-by-step Q&A, completion notified to messaging platform, collect in WebUI session)."
version: 1.3.0
author: ""
license: GPL-3.0
platforms: [windows]
metadata:
  hermes:
    tags: [image-generation, comfyui, anima, toolkit, run-image, direct-gen]
    related_skills: []
---

# ComfyUI 生图流水线（直出 + 跑图）

ComfyUI 驱动的生图双流程：**直出**（图发当前会话）与**跑图**（分步问答 + 收图会话领图）。适配 Hermes / Claude Code / Codex 等 agent。

## When to Use

| 用户说 | 走哪个流程 |
|---|---|
| **「跑图」口令**（含「跑图 xxx @画师」） | 跑图：分步问答 + 收图会话 |
| **其他直接需求**（「来张 xxx」「我要 xxx 的图」「生成一张…」「试一张」） | 直出：直接生成，**图发当前会话** |

## 环境依赖（部署前配置）

| 组件 | 说明 |
|---|---|
| ComfyUI | 端口 8188。每次生图先探活：`curl -s -m 5 http://127.0.0.1:8188/system_stats`（空=未启动）。**建议 detached 方式启动**（subprocess DETACHED_PROCESS / CREATE_NEW_PROCESS_GROUP，日志重定向文件）——用会随会话/回合被清理的后台方式拉起 daemon，长任务中途可能被进程管理杀掉。跑完图只卸载模型（/free），**ComfyUI 常驻不关** |
| 输入文件 | workspace 目录下 `args_prompt.json`（**整段正面，直出专用**）+ `args_character.json` / `args_description.json` / `args_negative.json`（anima 跑图三编码器专用），固定名覆盖写 |
| 显卡选择 | **RTX VSR 超分仅限 N 卡 RTX**（20/30/40/50 系）；A 卡/核显/无 RTX 的 N 卡 → 用 `-nortx` 后缀工作流（无超分）：改 run_latest.py TEMPLATES 的 `workflow`/`workflow_run` 为 `anima-txt2img-aesthetic-lora-nortx` / `anima-txt2img-aesthetic-lora-run-nortx` |
| 核心脚本 | `run_latest.py`（组装+提交+出图）/ `set_character.py`（写角色，只收「角色 @画师」或 `random`）/ `random_char.py`（随机角色/画师）/ `tag_lookup.py` + `danbooru-tags.exe`（查 danbooru 索引）/ `anima_tools.py`（姿势/背景/服装/画师/角色库查询 + `cloth-rand`/`pose-rand`/`background-rand` 随机抽取）/ `artist_rank.py`（角色画师排行）/ `image_track.py`（收图记录）/ `gacha_batch.py`（抽卡连抽） |
| 提交链路 | `run_latest.py` 调 `workspace/run_workflow_args.js`，后者再调 **`comfyui-skill`** CLI（`pip install comfyui-skill-cli`，需进 ComfyUI 的 venv）。缺这个 CLI 会在提交阶段报错——它是唯一硬依赖 |
| 可选凭据 | danbooru（`DANBOORU_USER` / `DANBOORU_API_KEY`，放 `~/.env` 或环境变量，`DANBOORU_ENV` 可改路径）：只有「画师池」「artist_rank」用到；不配则自动回退全量随机画师 |
| 出图后 | 脚本只打印路径，由 agent 在会话里告诉用户（不接消息平台、不发通知） |

**所有脚本路径、平台 ID、模型路径均为部署环境相关，使用前按实际环境配置，不硬编码他人环境。**

## 直出流程（direct）

**直出 = 整段直写 `args_prompt.json`，不拼接、不调 set_character.py**。模型直接扩写一整段正面提示词（场景+角色+画师融合），write_file 写 `args_prompt.json`（`{"prompt": "整段"}`）→ run_latest 读它进正面节点。**只有 anima 跑图才走 set_character.py 三文件**。

1. **探活 ComfyUI**（未启先拉起）
2. **横竖自动判断（不问用户）**：单人站立/全身/特写/竖构图 → 竖；多人/风景/建筑/宽场景/动作 → 横。尺寸：Anima 横 1536×864 竖 864×1536。判断错等用户出图后纠正
3. **角色处理（查索引/随机，但结果写进整段文本）**：
   - 需求带角色名 → 查 danbooru 索引验证角色 tag（`tag_lookup.py`；中文先翻译英文再查）；没指定画师就随机抽画师（`random_char.py --artist`）——**角色+画师都写进整段正面文本开头**（如 `furina_(genshin_impact) @dairi, masterpiece, ...`）
   - **「画这角色最多的画师」需求** → 先 `artist_rank.py "<角色tag>"` 拉真实排行（热门角色约 40s-2min，提前告诉用户）→ 选画师规则：**两榜都靠前（数量+平均分前 20）= 代表性画师**；只说「多」=数量榜 top；「精致/高质量」=平均分榜；带风格约束从榜里按已知画风挑 → @tag 写进整段开头
   - 需求带系列+随机（如「原神角色，随机角色」）→ 按系列加权随机（本地索引 `WHERE category='characters' AND tag LIKE '%<系列>%'` 按 count 加权；系列关键词：genshin/touhou/arknights/honkai/wuthering 等），抽完照常随机画师再拼
   - 纯描述无角色 → 整段里不写角色名，直接场景描述
4. **写整段正面**：扩写英文一整段（角色+画师+场景+质量词融合）→ write_file 写 `args_prompt.json`（`{"prompt": "..."}`）。**角色名写进整段没问题**（整段直写就是模型自己融合）。**整段里的场景标签同样先验证 canonical**（规则同跑图第 3 步）
5. **负面词**：基础 = 并集负面模板（12 词 ∪ 工作流节点词，见「工作流/模板知识」）+ **动态互斥负面**（正面选了互斥组一侧，另一侧进负面，按场景挑组不全塞）；无特殊需求**先删残留** args_negative.json 走模板默认；需扩写才 write_file 写（`{"negative": "..."}`）
6. **提交**：`python run_latest.py --target anima --mode direct --no-grab --width W --height H`
7. **发图**：出图路径发当前会话，告诉用户「图好了」（**不带 ✅**，✅ 只用于跑图确认）

## 跑图流程（run-image）

**一问一答逐步走，严禁猜默认值**：逐个问 ① 场景 → ② 角色画师（或 random）。**禁止**：没问就随机、自编场景、一次猜完全部、两问连发。用户连发多条「跑图」≠ 全随机——重申口令，继续走问答。

1. **探活 ComfyUI**（同上）
2. **横竖不问**：根据场景描述自动判断（同直出规则）
3. **问场景** → 扩写英文（**不含角色名**）→ write_file 写 args_description.json
   - 正面格式：短质量前缀（masterpiece, very aesthetic, best quality, nsfw）+ **10 个左右内容标签** + 一句自然语言描述（直接写，不加 `natural language:` 之类前缀标记）。NSFW 必须带 nsfw 标签激活，别堆 30+ 标签
   - **内容标签必须验证 canonical，禁止直接写英文短语**：描述里的每个内容标签先查索引，无匹配的词换 canonical 或只写进自然语言描述。实测映射：`evening dress`→`evening_gown`、`skirt lift`→`skirt_lift`、`city lights`→`city_lights`（下划线式=canonical）；普通单词直接可用；查索引输出「无匹配」时提示的「下划线风格词」就是 canonical。自然语言描述可自由写，不受 tag 约束
   - 姿势/背景/服装词优先用 `anima_tools.py` 查库（姿势 297 条 / 背景 1087 条 / 服装 430 条，中英双语，输出英文触发词）
4. **负面词**（**在问角色画师之前**）→ 基础 = 并集负面模板 + 动态互斥负面（按场景挑组）→ write_file 写 args_negative.json
5. **问角色画师**（或 random）→ anima：问角色+画师，查索引验证 → `set_character.py "角色 @画师"` 写 args_character.json（三编码器需要角色独立节点）。用户要「画这角色最多的画师」→ 先 `artist_rank.py "<角色tag>"` 查排行再 set_character
6. **提交**：`python run_latest.py --target anima --mode run --no-grab --width W --height H`
7. **收尾**：出图后**由 agent 向用户播报**「跑图完成✅」（✅ 在提示语后面；不描述图内容、不说角色/画师/场景）→ 用户去收图会话发「收图」
8. 流程结束只卸载模型（/free），**不关 ComfyUI**

## 抽卡连抽（gacha_batch.py）

批量抽卡：角色固定，服装/画师/姿势/背景每张独立随机，出图自动复制改名到 `<输出目录>/change_name/`（原图保留在输出目录，ComfyUI 前端 history 仍可见）。

**流程**：确认角色（characters 表精确匹配取发色/瞳色）→ 拉画师池（失败回退随机）→ 每张循环〔抽服装→抽姿势→抽背景→定画师→写三文件→`run_latest --mode run --no-free` 提交等图→复制改名〕→ 批末 `/free` → 打印路径由 agent 交付。ComfyUI 没起时每张都会打 `FAILED`，不会中断整批。

```
python scripts/gacha_batch.py <N> <角色tag> [固定画师@名]
python scripts/gacha_batch.py 5 nahida_(genshin_impact)
```

| 参数 | 作用 |
|---|---|
| 第 1 参 | 张数 N |
| 第 2 参 | 角色 canonical tag（下划线式，带系列，如 `nahida_(genshin_impact)`） |
| 第 3 参 | 可选：固定画师 `@名`（不传=画师池/随机） |

**要点**：
- 第 3 参画师**必须带 `@`**（写 `@dairi`），否则会被当成普通 tag。
- 角色 tag 不是 canonical 时不报错，但外观锚定和画师池都会静默落空（画师全随机、不锁发色瞳色）。
- 尺寸固定 **864×1536**（抽卡没有 `--width/--height`）；每张 1~3 分钟串行，某张失败打 `[n] FAILED` 后继续下一张。
- 产物在 `change_name/anima-<角色>-<画师>-<时间戳>.png`；脚本只打印路径，交付由 agent 发图。

**不区分 SFW / R18**：服装、姿势、背景都从完整库随机抽，只按「结构上对不对」过滤，不按尺度过滤。

内置规则：
- **画师池**：固定角色且未指定画师时，自动从 danbooru 拉「画过该角色的画师」频次榜 **top100**（`order:score` 高分优先，18s 硬截止），按频次加权随机、同批不重复；`LOW_WEIGHT_ARTISTS` 命中的画师权重 ×0.3（降权不排除，用于常出多人的画师）；无网络/未配凭据/超时 → 回退全量 arand
- **服装互斥**：条目拆 `&` 后随机二选一（鞋袜↔光脚、naked↔服装），选中的进正面、另一侧去权进负面，矛盾词不浪费
- **服装条目过滤**：`CLOTH_EXTRA_BAD` 剔除混进服装表的非服装条目（持械/机械/角色主题/动作），命中重抽
- **姿势过滤**：`POSE_BAD` 剔除需要第二人才成立的姿势（双人互动、拥抱、亲吻、性行为类），再过滤非英文/符号垃圾条目——单人图抽到必错
- **标签写法**：姿势/背景写小写+空格（`sitting on a chair`，贴 caption 风格）；角色 tag 保留下划线 canonical（`nahida_(genshin_impact)`）
- **背景过滤**：`BAD_BG` 剔除猎奇（断头/内脏/血/卫生间）、服装混入条目、拼音残留条目
- **外观锚定**：characters 表**精确匹配** `name`（下划线→空格）取 hair/eye；查不到不填，避免模糊匹配串到同名角色
- 每张提交带 `--no-free`，**整批结束统一 `/free` 一次**（省模型重载）
- 依赖 `anima_tools.py` 的 `cloth-rand` / `pose-rand` / `background-rand` 三个子命令（本仓库已内置）

库规模（`data/anima_tools.sqlite`）：画师 40600 / 角色 8001 / 服装 425 / 姿势 303 / 背景 1086。

**库是全的，出什么类型靠「分类 + 权重」控制**：按分类挑提示词、给标签加权重（`(tag:1.2)` / `(tag:0.8)`）即可调方向，不用改脚本。加权在 `gacha_batch.py` 顶部 `WEIGHTS` 表：质量词 / 人数 / 外观 / 服装 / 姿势 / 背景 / 画师 七个槽位，默认全 1.0（原样写入）；`>1` 强化、`<1` 弱化（如姿势 1.2、背景 0.8、画师 0.5）。库里自带权重的服装条目保留原权重不叠加。

其余「按热度加权」的地方默认都是等权，加权写法留在注释里：`anima_tools.py` 的 `arand`/`crand`、`random_char.py`、抽卡服装的「正常/擦边」加权（`cloth_weighted_rand()`）。**抽卡画师池是例外，已启用频次加权**——理由：danbooru 没有「角色→画师」聚合接口只能拉图数频次；`order:score` 让前几页是高质图；只取 top100 是因为低频画师模型不熟、抽到会幻化成别的角色（实测 980 位池连抽 4/5 不像）；同批不重复防风格重复；18s 硬截止防抽卡前卡死，失败则回退全量随机。

### 跑图 character 语义

| 用户说 | character 处理 |
|---|---|
| 只「跑图」 | 随机角色+画师（set_character random） |
| 「跑图 鸣人」 | 指定角色（中文先翻译英文再查索引验证）+ **画师仍要问**（随机/指定，不能默认 random） |
| 「跑图 @画师名」 | **随机角色** + 指定画师 |
| 「跑图 角色名 @画师名」 | 指定两者 |

- 角色+画师顺序随意（「qin @dairi」/「@dairi 出 qin」都行）；`@`开头=画师，其余英文词=角色
- 指定角色+随机画师序列：查索引验证 → 随机抽画师 → set_character 拼好写入
- set_character 只接受「角色+画师」或 `random`，不接受「角色 random」
- 随机带外观约束（如「随机，但不要黑人」）：约束折叠进描述（`pale skin` 等），不进 character
- 双角色支持逗号分隔一次写入（`"furina_(genshin_impact), lumine_(genshin_impact) @carnelian"`）

## 收图流程

- 用户发「收图」→ image_track 读路径 → 发图到当前会话；连发多条「收图」= 逐个轮询
- 读取可能返回已发过的文件（指针未推进）——先比对本次会话已发路径；重复时核对输出目录有无更新文件（Anima 图在 `anima/YYYY-MM-DD/` 日期子目录下，只列根目录会漏新图），**没有就明说「没有新图」并停手，绝不重复发同一张图**
- 用户点名「XX图没收到，再发一遍」→ 立即重发该图（「绝不重复发」只约束主动行为，不约束用户点名的重发）

## 工作流/模板知识（run_latest.py TEMPLATES）

> 📌 **提示词组织**：扩写前按槽位顺序组织：质量前缀 → 人数/性别 → 外观 → 服饰/状态 → 姿势/动作 → 表情/反应 → 镜头 → 场景 → 氛围细节 → 一句自然语言描述。规则管组织已有词，不编造没有的词；素材以查库为准，库里没有的短语不硬拼。

| target | direct（直出） | run（跑图） | 节点 |
|---|---|---|---|
| anima | 双编码器工作流（**整段正面**读 args_prompt.json 进 11 + 负面 12） | 三编码器工作流（11 角色 + 66 描述 + 67 ConditioningCombine → positive，12 负面；读三文件） | char 11 / desc_run 66 / neg 12 / latent 28 |

- **跑图合并顺序**：67 ConditioningCombine = conditioning_1(角色 11) → conditioning_2(描述 66)——**角色+画师在前、场景词在后**，勿交换；问答顺序（先场景后角色）与合并顺序无关
- **Anima 负面模板（并集）**：12 词（lowres, bad anatomy, bad hands, worst quality, blurry, watermark, signature, text, monochrome, oil painting, greasy, glossy）∪ 工作流节点 12 词（score_1~3, bad proportions, deformed anatomy, deformed face, deformed eyes, multiple fingers, artist name）——并集去重作底子；再按场景挑动态互斥组（正面选了互斥组一侧，另一侧进负面；如正面 `looking at viewer` → 负面 `facing away`；正面 solo → 负面加 1boy/hetero 等）。直出/跑图都适用，跑图负面组装在问角色画师之前
- 带括号角色标签（`ayaka_(genshin_impact)`）Anima 识别，不用改裸名

## Verification Checklist

- [ ] ComfyUI 探活通过（或已拉起并在提交前就绪）
- [ ] 直出：args_prompt.json 已覆盖新整段；跑图：三文件就位（set_character 写 character + 直接写 description/negative）
- [ ] 描述/整段不含未验证标签；跑图描述不含角色名、含质量前缀 + ~10 标签 + 自然语言描述
- [ ] 提交成功，日志出现「出图完成」与输出路径
- [ ] 跑图流程：agent 已向用户播报「跑图完成✅」（✅ 在提示语后面，不描述图内容）
- [ ] 收图：读取路径发图到收图会话，无重复发送
- [ ] 显存：模型已卸载（/free），ComfyUI 进程保持运行
