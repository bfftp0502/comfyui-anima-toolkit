# comfyui-anima-toolkit — ComfyUI Anima 生图工具包（直出 + 跑图 + 抽卡）

基于 **ComfyUI Good Anima** 工作流改进的 **Anima 动漫生图流水线**：直出（图发当前会话）、跑图（分步问答 + 收图会话领图）、抽卡连抽（角色固定、其余逐张随机）。配套画师/角色/姿势/服装/背景索引、提示词组装脚本与收图链路。Web 界面（如 hermes-webui 8787）可作为局域网内收图的例子。

> **⚠️ 效果提示**：自动化流程追求的是「能出、能收、不用守着」；**想要精细效果（构图、手部、光影），还是建议自己人工调整提示词/参数**——本流水线定位是省事，不是取代手工调图。

---

## 一、这是什么

一套把「本地 ComfyUI 生图」串成完整闭环的方案：

```
┌─────────────┐   三文件    ┌──────────────┐  提交   ┌──────────┐
│ Agent 会话  │ ──────────▶ │ run_latest.py │ ─────▶ │ ComfyUI  │
│ (直出/跑图) │  角色/描述/  │ 组装+提交      │        │ 8188 端口 │
└─────────────┘   负面词    └──────────────┘  出图   └──────────┘
                                   │
                                   ▼
                          WebUI 收图会话 (8787)
```

- **Agent**（Hermes / Claude Code / Codex 等）负责：听懂需求 → 拆成角色/场景/负面词 → 调脚本
- **run_latest.py** 负责：读三文件 → 组装工作流参数 → 提交 ComfyUI → 轮询出图
- **WebUI** 负责：收图会话（图不出现在任何聊天平台，见「图片不出本机」）
- **gacha_batch.py** 负责：把上面这条链路循环 N 次，每次换一套服装/画师/姿势/背景

## 二、快速开始

> 目标：一台装了 ComfyUI 的电脑（N 卡 ≥8G 显存；RTX 可用 2x 超分），克隆本仓库后手动配好，即可命令行直接出图。

### 前置依赖

| 依赖 | 要求 | 获取 |
|---|---|---|
| **ComfyUI** | 已能正常运行（端口 8188） | https://github.com/comfyanonymous/ComfyUI |
| **显卡** | NVIDIA ≥8G 显存；RTX 20/30/40/50 系可用超分 | — |
| **Python** | ≥ 3.10 | ComfyUI 自带 venv 即可 |
| **Node.js** | ≥ 18（跑 run_workflow_args.js） | https://nodejs.org |
| **comfyui-skill-cli** | 提交工作流的核心 CLI | `pip install comfyui-skill-cli` |
| **自定义节点插件** | 工作流引用的节点类：**3 必需 + 1 可选（RTX 用）** | 见「部署步骤 2」git clone 列表 |
| **模型文件** | 见下表 | Civitai / HuggingFace |

> 工作流、标签索引、画师/角色/姿势/服装数据库**已内置**在本仓库 `workspace/` 与 `data/`，无需再装任何技能包。`comfyui-skill-cli` 是整条链路的桥梁（提交/查询 ComfyUI 都靠它），装完用 `comfyui-skill --help` 验证；**装进 ComfyUI 的 venv 时要确保 `comfyui-skill` 命令在 PATH 里**，否则脚本提交那步会直接报错。

### 本仓库需要的模型文件

放到 ComfyUI 对应目录（工作流按文件名引用，位置如下）：

| 文件 | 放入目录 | 说明 |
|---|---|---|
| `anima_aestheticV11.safetensors`（或 `anima-base-v1.0.safetensors`） | `ComfyUI/models/diffusion_models/` | 主模型（AnimaBoosterLoader 读此目录） |
| `anima-base-1-masterpiece-v51.safetensors` | `ComfyUI/models/loras/` | 美学质量修饰 LoRA |
| `anima-highres-aesthetic-boost.safetensors` | `ComfyUI/models/loras/` | 高分辨率稳定 LoRA |
| `qwen_3_06b_base.safetensors` | `ComfyUI/models/text_encoders/` | 文本编码（CLIPLoader 读此目录） |
| `qwen_image_vae.safetensors` | `ComfyUI/models/vae/` | 图像解码（VAELoader 读此目录） |

**模型下载**：
- 主模型与 CLIP/VAE：[circlestone-labs/Anima](https://huggingface.co/circlestone-labs/Anima)（HF 官方仓库，含 `anima-base-v1.0.safetensors` / `qwen_3_06b_base.safetensors` / `qwen_image_vae.safetensors`；`anima_aestheticV11` 为 base 的美学微调版，可从 Civitai 模型页 2458426 获取）
- LoRA：[anima-highres-aesthetic-boost](https://civitai.red/models/2540444/anima-highresaesthetic-boost)、[aesthetic-quality-modifiers-masterpiece](https://civitai.red/models/929497/aesthetic-quality-modifiers-masterpiece?modelVersionId=2961717)

> 具体文件名以 `workspace/data/local/<工作流>/workflow.json` 里 `model_name` / `lora_name` 为准；模型不齐时 `comfyui-skill` 提交会直接报错。文件名对不上就按工作流里的名字改，别反过来改工作流。

### 内置工作流（按显卡选）

| 工作流 | 用途 | RTX VSR 超分 | 适用显卡 |
|---|---|---|---|
| `anima-txt2img-aesthetic-lora` | 直出（主用） | ✅ 有（2x 超分） | **仅 N 卡 RTX** |
| `anima-txt2img-aesthetic-lora-run` | 跑图（主用） | ✅ 有（2x 超分） | **仅 N 卡 RTX** |
| `anima-txt2img-aesthetic-lora-nortx` | 直出（A 卡/无 RTX 备用） | ❌ 无 | 任意显卡 |
| `anima-txt2img-aesthetic-lora-run-nortx` | 跑图（A 卡/无 RTX 备用） | ❌ 无 | 任意显卡 |
| `anima-txt2img-base-nortx` | **测试用**（验证环境是否装好） | ❌ 无 | 任意显卡 |

> ⚠️ **RTXVideoSuperResolution 节点仅限 N 卡 RTX 系列**（RTX 20/30/40/50 系）。**A 卡 / Intel 核显 / 无 RTX 的 N 卡请用 `-nortx` 后缀的工作流**（无超分，出图分辨率即模型原生输出）。部署好后建议先跑 `anima-txt2img-base-nortx` 验证链路（节点最少、出图最快、不依赖 RTX）。
>
> 切换工作流不用改代码，环境变量覆盖即可（`run_latest.py` 的 TEMPLATES 支持覆盖）：
>
> ```powershell
> $env:ANIMA_WORKFLOW     = "anima-txt2img-aesthetic-lora-nortx"      # 直出
> $env:ANIMA_WORKFLOW_RUN = "anima-txt2img-aesthetic-lora-run-nortx"  # 跑图
> ```

### 部署步骤

```powershell
# 1. 安装 ComfyUI（官方流程，参考 https://docs.comfy.org/get_started）
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI
python -m venv venv
venv\Scripts\pip install -r requirements.txt
# 启动验证：venv\Scripts\python main.py --listen 127.0.0.1 --port 8188

# 2. 装 comfyui-skill-cli（装进 ComfyUI 的 venv，确保 comfyui-skill 命令可用）
venv\Scripts\pip install comfyui-skill-cli

# 3. 装自定义节点插件（克隆到 ComfyUI/custom_nodes/）
#    —— 必需 3 个（全部工作流都依赖）——
cd ComfyUI/custom_nodes
git clone https://github.com/BlackSnowSkill/ANIMA_BOOSTER.git            # AnimaBoosterLoader
git clone https://github.com/BlackSnowSkill/ComfyUI-BSS_FLSampler.git   # FLS_SamplerV4
git clone https://github.com/daraskme/comfy_anima_tea_cache.git         # AnimaTeaCache
#    —— 可选 1 个（仅 N 卡 RTX 用带超分的工作流时需要；A 卡跳过）——
git clone https://github.com/Comfy-Org/Nvidia_RTX_Nodes_ComfyUI.git     # RTXVideoSuperResolution
cd ../..   # 回到上级

# 4. 克隆本仓库（工作流/数据/脚本全在里面）
git clone <本仓库地址> comfyui-anima-toolkit
cd comfyui-anima-toolkit

# 5. 放模型（见上表，下载后放到 ComfyUI/models/ 对应目录）

# 6. 启动 ComfyUI（已手动启动可跳过；comfy_detach.py 是 detached 常驻启动）
python scripts/comfy_detach.py

# 7. 验证链路（在 ComfyUI 启动后执行；若 comfyui-skill 不在 PATH，用 venv\Scripts\comfyui-skill）
cd workspace
comfyui-skill list   # 应列出 5 个工作流（anima 系列）
cd ..
curl http://127.0.0.1:8188/system_stats   # 有 JSON 返回 = ComfyUI 就绪
```

> 第 6 步的常驻启动是有意为之：生图是长任务，放在窗口里跑，窗口一关出图就断。`comfy_detach.py` 用 pythonw 无窗口拉起、日志写文件，关终端也不影响；要停就去任务管理器结束进程，或调 `http://127.0.0.1:8188/free` 只卸模型不关进程。

### 手动出一张图

```powershell
# ① 写提示词文件 workspace/args_prompt.json（直出格式：整段正面，角色+画师+场景+质量词融合）
#    例如：
#    {
#      "prompt": "masterpiece, very aesthetic, best quality, 1girl, furina_(genshin_impact) @dairi, long hair, blue eyes, standing, looking at viewer, city street at night, natural language: a girl in an elegant dress standing under streetlights, soft lighting"
#    }

# ② 提交（anima 直出；尺寸 --width/--height 可选）
python scripts/run_latest.py --target anima --mode direct --no-grab --width 864 --height 1536

# ③ 出图在 ComfyUI 输出目录（默认 ~/ComfyUI/output/），日志打印路径

# ④ 成功的日志长这样（认这一行，不要只看「没报错」）：
#    ▶ 模板: anima [direct] → 工作流 anima-txt2img-aesthetic-lora
#    ▶ 已提交，等出图...
#    ✅ 出图完成: E:\ComfyUI\output\anima\2026-11-06\anima_00001_.png
#    ✅ 已卸载 ComfyUI 模型（/free），显存已释放
```

跑图（run）模式：`--mode run`，需另写 `workspace/args_character.json`（`{"character": "角色 @画师"}`）、`workspace/args_description.json`（`{"description": "场景描述"}`）、`workspace/args_negative.json`（`{"negative": "负面词"}`），三个文件齐了再提交。

**run_latest.py 常用参数**：

| 参数 | 作用 |
|---|---|
| `--mode direct / run` | 直出（读整段 `args_prompt.json`）/ 跑图（读三文件） |
| `--no-grab` | 跳过从 WebUI 会话自动抓提示词（agent 自己写文件时用） |
| `--no-free` | 不逐张 `/free`（批量抽卡用，整批结束统一释放） |
| `--seed N` | 固定 seed（复现、对比同一张；默认每张随机） |
| `--width` / `--height` | 覆盖尺寸（竖 864×1536、横 1536×864） |

### 可选环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `COMFY_API` | `http://127.0.0.1:8188` | 脚本访问 ComfyUI 的地址；端口不是 8188 时必改 |
| `ANIMA_WORKFLOW` / `ANIMA_WORKFLOW_RUN` | `anima-txt2img-aesthetic-lora` / `-run` | 直出 / 跑图用哪个工作流（无 RTX 改成 `-nortx` 版） |
| `COMFY_OUTPUT_DIR` | `~/ComfyUI/output` | 出图目录（run_latest 查找输出图用）；抽卡的改名图落在 `<它>/change_name/` |
| `COMFY_DIR` / `COMFY_PY` / `COMFY_LOG` / `COMFY_PORT` | `~/ComfyUI` | comfy_detach.py 启动用的 ComfyUI 路径/解释器/日志/端口 |
| `COMFY_OUT_DIR` / `COMFY_IN_DIR` | 空 | comfy_detach.py 透传 `--output-directory` / `--input-directory`（多实例并存时用） |
| `WEBUI_SESSIONS` | 空 | 配了才启用「自动抓取 WebUI 会话提示词」（可选功能） |
| `DANBOORU_USER` / `DANBOORU_API_KEY` | 空 | 抽卡画师池、artist_rank.py 用；不配则画师退化为全量随机 |
| `DANBOORU_ENV` | `~/.env` | danbooru 凭据文件（DANBOORU_USER/API_KEY/USER_ID，一行一个 KEY=VALUE） |
| `HTTPS_PROXY` | 空 | 访问 danbooru 的代理（国内网络基本要配） |

### 常见问题

**`git clone` 报 `schannel: AcquireCredentialsHandle failed: SEC_E_NO_CREDENTIALS`**：系统代理和 Windows schannel 打架，命令前加 `-c http.sslBackend=openssl`。

**提交时提示找不到 `comfyui-skill`**：没进 PATH。直接用 `<ComfyUI>\venv\Scripts\comfyui-skill.exe`，或把 `<ComfyUI>\venv\Scripts` 加进环境变量。

**`comfyui-skill list` 是空的 / 只列出几个**：没在 `workspace/` 目录下执行，或者 `workspace/data/local/*/workflow.json` 缺文件。

**报 `model_name` / `lora_name` / `vae_name` 找不到**：文件名和「模型文件」表格对不上，或放错目录。

**报 `RTXVideoSuperResolution` 节点不存在**：用了带超分的工作流但没装第四个节点，换成 `-nortx` 版。

**`CUDA out of memory`**：降分辨率、别开 batch、先 `/free` 再跑，或用 `-nortx`。

**提交成功但一直没图**：看 ComfyUI 控制台是否在跑（RTX 2x 超分放大很慢）；脚本等 10 分钟会取消任务，日志在 `comfy_detached.log`。

**出图了脚本却说没找到**：`COMFY_OUTPUT_DIR` 和 ComfyUI 实际输出目录不是同一个，对齐。

**抽卡开始前卡十几秒、提示画师池不可用**：没配 danbooru 凭据或网络不通，会自动退回全量随机画师，不影响出图。

**控制台中文乱码 / `UnicodeEncodeError`**：脚本已强制 UTF-8；仍报则设 `PYTHONIOENCODING=utf-8`。

### 给 AI agent 用

本仓库同时是 skill 包：把 `SKILL.md` 拷进 agent 的 skills 目录（Hermes：`hermes skills install` 或拷贝到 `~/skills/`），agent 就会按文档自动走「直出/跑图/抽卡」流程。

agent 照着这份 README 自动部署时，需要额外知道的几条：

1. **硬依赖**：「自定义节点插件」的 3 个 + 「模型文件」的 5 个 + `comfyui-skill-cli`，缺任何一项都出不了图/提交不了。
2. **验收标准**是「手动出一张图」那节打出 `✅ 出图完成: <路径>`，不是命令没报错。
3. **抽卡第 3 参是画师位**，只传角色和画师、别塞别的参数进去。
4. **别改用户的 ComfyUI 安装/模型/节点**，也别把本地绝对路径、token、代理地址写进仓库；这些走环境变量或命令行参数。
5. 切工作流用 `ANIMA_WORKFLOW` / `ANIMA_WORKFLOW_RUN`，不要改脚本源码。
6. 单张出图默认 `/free` 卸载模型；批量抽卡整批结束统一释放，别逐张手动调。

---

## 三、模型与工作流

| 模型 | 定位 | 工作流 |
|---|---|---|
| **Anima**（动漫/二次元，danbooru 标签体系，吃画师 tag） | `anima-txt2img-aesthetic-lora`（直出）/ `anima-txt2img-aesthetic-lora-run`（跑图），A 卡用 `-nortx` 版 | 模型文件见「快速开始」模型表 |

- 文本编码：双 CLIP（qwen3-vl-4b）
- 尺寸：横 1536×864 / 竖 864×1536（RTX 工作流自动 2x 超分）
- 采样（工作流内置）：FLS_SamplerV4，steps 40 / cfg 4.5 / dpmpp_2m_sde_gpu / denoise 1.0

## 四、三种用法

### 直出（direct）
对 Agent 说「来张 xxx 的图」→ 直接生成，**图发当前会话**。适合顺手要一张。

### 跑图（run-image）
对 Agent 说「**跑图**」→ 分步问答（场景 → 角色画师）→ 出图后去收图会话领图。图不进聊天平台，适合正经出图。

> 角色支持指定/随机/按系列随机（genshin、touhou、arknights、wuthering 等），画师支持指定/随机——随机画师风格不可控，抽到不合适的换一个就是。

### 抽卡连抽（gacha_batch.py）
对 Agent 说「**抽卡**」→ 固定角色批量出图，服装/画师/姿势/背景每张独立随机。适合连续出图挑满意的。

```bash
python scripts/gacha_batch.py <N> <角色tag> [固定画师@名]
python scripts/gacha_batch.py 5 nahida_(genshin_impact)
```

| 位置 | 作用 |
|---|---|
| 第 1 个 | 抽几张 |
| 第 2 个 | 角色 canonical tag（下划线式、带系列，如 `nahida_(genshin_impact)`） |
| 第 3 个 | 可选：固定画师 `@名字`（不指定就走画师池/随机） |

出图自动复制改名到 `<输出目录>/change_name/`（原图保留在输出目录，ComfyUI 前端 history 仍可见），每张带 `--no-free`、批末统一释放显存。

**服装 / 姿势 / 背景都从完整库里随机抽，不区分 SFW 与 R18，也不做内容分级**——库里的条目只按「结构上对不对」过滤，不按尺度过滤：

- **画师池**：固定角色且未指定画师时，自动从 danbooru 拉「画过该角色的画师」频次榜 **top100**（`order:score` 高分优先，18s 硬截止），按频次加权随机、同批不重复；`LOW_WEIGHT_ARTISTS` 命中的画师权重 ×0.3（降权不排除，用于常出多人的画师）；无网络/未配凭据/超时 → 自动回退全量随机
- **服装互斥**：条目拆 `&` 后随机二选一（鞋袜↔光脚、naked↔服装），选中的进正面、另一侧去权进负面，矛盾词不浪费
- **服装条目过滤**：`CLOTH_EXTRA_BAD` 剔除混进服装表的非服装条目（持械/机械/角色主题/动作），命中重抽
- **姿势过滤**：`POSE_BAD` 剔除需要第二个人才成立的姿势（双人互动、拥抱、亲吻、性行为类），另过滤非英文/符号垃圾条目——单人图抽到这些必错
- **背景过滤**：`BAD_BG` 剔除猎奇（断头/内脏/血/卫生间）、混进来的服装条目、拼音残留条目
- **角色外观自动锚定**：characters 表**精确匹配** `name`（下划线→空格）取 hair/eye，查不到不填——模糊匹配会串到同名角色（同名不同系列）
- 依赖 `anima_tools.py` 的 `cloth-rand` / `pose-rand` / `background-rand` 三个子命令（本仓库已内置）

内置库规模（`data/anima_tools.sqlite`）：画师 **40600**、角色 **8001**、服装 **425**、姿势 **303**、背景 **1086**。

> **库是全的，出什么类型靠「分类 + 权重」控制**：按分类挑提示词、给标签加权重（danbooru 的 `(tag:1.2)` / `(tag:0.8)` 语法）就能把出图往某个方向推，不用改脚本。
>
> 加权位置在 `gacha_batch.py` 顶部的 `WEIGHTS` 表，覆盖 **质量词 / 人数 / 外观 / 服装 / 姿势 / 背景 / 画师** 七个槽位，默认全是 `1.0`（原样写入、不加括号）：`>1` 强化、`<1` 弱化，比如姿势 `1.2`、背景 `0.8`、画师 `0.5`。库里自带权重的 53 件服装（如 `(Fedora:1.1)`）会保留自带权重；改槽位权重时这些条目不受影响、不会叠成 `(x:1.1:1.2)`。画师池的「按热度加权 / `LOW_WEIGHT_ARTISTS` 降权」那段默认注释掉，想按画师热度抽再放开。

## 五、访问方式：局域网 + 远程

- **局域网**：同一 Wi-Fi 下，手机/平板浏览器直接开 Web 界面和 ComfyUI 前端（8188），操作/收图全在移动端完成——这是本方案的主场景，实测稳定
- **远程（远控方法，未实践 ⚠️）**：以下思路理论上可行，但**本仓库作者没有实际跑通过，不构成承诺**：
  - VPN 组网（Tailscale / ZeroTier）：加密隧道回家里网，安全但依赖第三方服务
  - 公网 IPv6 直连：本机若有运营商公网 IPv6，可直连——**注意**：公网 IPv6 是默认裸奔，无 NAT 兜底，必须先做好防火墙白名单 + HTTPS，否则等于把服务扔公网上
  - 远控类软件（如各类远程桌面）：能看屏幕操作，但带宽/延迟体验一般，且同样有暴露面问题
- **推荐组合**：局域网为主 + VPN 组网为辅；不建议裸奔公网端口

## 六、图片不出本机的用法

这套流程最「干净」的用法：**图片从生成到接收，全程不经过任何消息平台服务器**。

- **Web 界面**：任何本地跑的前端都行（本仓库作者用 hermes-webui，8787 端口），局域网浏览器直接访问，收图会话就在这里，出图后去那里拿
- 图片只在「你的设备 → 你的电脑 → 你的浏览器」之间流转，第三方平台接触不到图
- 脚本出图后只打印路径（不再往任何消息平台推送），由 agent 在会话里告诉你「好了」

## 七、免责声明

1. **生成模型的第三方属性**：出图由本地 ComfyUI + 第三方模型（Anima 等）完成，Agent 推理接云端 API——**模型输出的任何内容与内容审查行为，均与本仓库/skill 无关**，模型是第三方训练产物，仓库只提供调用流程。
2. **关于内容审核的边界**：本仓库只提供调用流程，不内置、也不替代任何内容审查机制。图片由本地 ComfyUI 与第三方模型生成，是否经过审核取决于你的部署环境（模型、接入方式、网络链路），本仓库对此不作任何验证或承诺。不同模型、不同接入方式的行为差异巨大，请自行评估。
3. **图片上传消息平台有法律风险**：把图片发到任何消息平台（Telegram、Discord、微信等），图片会明文经过平台服务器，涉黄等内容可能触犯当地法律（传播淫秽物品等），并面临封号风险。**本仓库强烈建议：图片只在本地/局域网流转，不要上传任何消息平台。** 使用者的行为与责任自负，与本仓库无关。
4. **合规提示**：请遵守你所在地区的法律法规与平台条款。未成年人内容无论本地还是云端都绝对禁止，没有任何借口。本仓库不划分 SFW / R18 池，模型输出是否合规由使用者自行判断与负责。

## 八、致谢

- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) — 开源图生图工作流引擎
- [ComfyUI Good Anima](https://github.com/ShiroEirin/comfyui-good-anima) — 面向 AI 编程助手的 ComfyUI + Anima 二次元生图技能包（`comfyui-animatool` / `comfyui-manager` / `danbooru-tags`），本仓库的工作流组装与提交链路直接基于它，特此致谢（GPL-3.0，本项目整体按 GPL-3.0 发布）
- [Comfyui-Anima-Tools](https://github.com/nregret/Comfyui-Anima-Tools) — 角色/画师/姿势/场景/服装索引（`anima_tools.sqlite` 5 表）的数据来源（MIT；按协议保留原作者版权声明与完整致谢：AnimaDex / Anima-Style-Explorer / CircleStone Labs，见其仓库 README「鸣谢与致敬」节）
- [hermes-webui](https://github.com/nesquena/hermes-webui) — 开源的 Hermes Web 界面，收图会话的载体（示例）
- [Hermes Agent](https://github.com/NousResearch/hermes-agent) — Nous Research 的开源 agent 框架
- 各模型作者（Anima / qwen3-vl / 各 LoRA 作者）与 danbooru 标签社区

## 九、文件来源说明

| 文件 | 来源 | License |
|---|---|---|
| `SKILL.md` / `README.md` / `COPYING` / `.gitignore` | **本仓库原创**（skill 流程文档与发布说明） | GPL-3.0 |
| `scripts/`（11 个 .py） | **本仓库原创**编排脚本（工作流组装/提交链路基于 comfyui-good-anima 的 comfyui-manager） | GPL-3.0 |
| `data/anima_tools.sqlite` | [Comfyui-Anima-Tools](https://github.com/nregret/Comfyui-Anima-Tools)（nregret）——画师/角色/服装/姿势/背景索引库 | MIT |
| `data/danbooru-tags.exe` | [comfyui-good-anima](https://github.com/ShiroEirin/comfyui-good-anima)（ShiroEirin）的 `danbooru-tags` 组件——canonical tag 查询工具 | GPL-3.0 |
| `data/tags_index.sqlite` | [comfyui-good-anima](https://github.com/ShiroEirin/comfyui-good-anima)（ShiroEirin）的 `danbooru-tags` 组件——danbooru 标签索引 | GPL-3.0 |

其余文件均为本仓库自研。第三方文件保持原样分发，未作修改；其各自许可证与版权声明见对应上游仓库。

---

**License**: GPL-3.0（本 skill 融合了 GPL-3.0 的 comfyui-good-anima，整体按 GPL-3.0 发布，见 COPYING）；其中 Comfyui-Anima-Tools 相关部分遵循其 MIT 声明（保留版权与致谢）；各模型/工具遵循其各自许可证。
