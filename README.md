# comfyui-anima-toolkit — ComfyUI Anima 生图工具包（直出 + 跑图）

基于 **ComfyUI Good Anima** 工作流改进的 **Anima 动漫生图流水线**：直出（图发当前会话）与跑图（分步问答 + 完成通知 + 收图会话领图）双流程，配套画师/角色/姿势/服装/背景索引、提示词组装脚本与收图链路。QQ、Web 端（hermes-webui 8787）可作为局域网内收图的例子。

> **⚠️ 效果提示**：自动化流程追求的是「能出、能收、不用守着」；**想要精细效果（构图、手部、光影），还是建议自己人工调整提示词/参数**——本流水线定位是省事，不是取代手工调图。

---

## 一、这是什么

一套把「本地 ComfyUI 生图」串成完整闭环的方案：

```
┌─────────────┐   三文件    ┌──────────────┐  提交   ┌──────────┐
│ Agent 会话  │ ──────────▶ │ run_latest.py │ ─────▶ │ ComfyUI  │
│ (直出/跑图) │  角色/描述/  │ 组装+提交+通知 │        │ 8188 端口 │
└─────────────┘   负面词    └──────────────┘  出图   └──────────┘
                                   │
                                   ▼
                          WebUI 收图会话 (8787)
```

- **Agent**（Hermes / Claude Code / Codex 等）负责：听懂需求 → 拆成角色/场景/负面词 → 调脚本
- **run_latest.py** 负责：读三文件 → 组装工作流参数 → 提交 ComfyUI → 轮询出图 → 通知
- **WebUI** 负责：收图会话（图不出现在任何聊天平台，见「完全不上网」）

## 二、快速开始

> 目标：一台装了 ComfyUI 的电脑（建议 N 卡 ≥8G 显存），克隆本仓库后手动配好，即可命令行直接出图。

### 前置依赖

| 依赖 | 要求 | 获取 |
|---|---|---|
| **ComfyUI** | 已能正常运行（端口 8188） | https://github.com/comfyanonymous/ComfyUI |
| **Python** | ≥ 3.10 | ComfyUI 自带 venv 即可 |
| **Node.js** | ≥ 18（跑 run_workflow_args.js） | https://nodejs.org |
| **comfyui-skill-cli** | 提交工作流的核心 CLI | `pip install comfyui-skill-cli` |
| **自定义节点插件** | 工作流引用的节点类：**3 必需 + 1 可选（RTX 用）** | 见「部署步骤 2」git clone 列表 |
| **模型文件** | 见下表 | Civitai / HuggingFace |

> 工作流、标签索引、画师/角色/姿势/服装数据库**已内置**在本仓库 `workspace/` 与 `data/`，无需再装任何技能包。`comfyui-skill-cli` 是整条链路的桥梁（提交/查询 ComfyUI 都靠它），装完用 `comfyui-skill --help` 验证。

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

> 具体文件名以 `workspace/data/local/<工作流>/workflow.json` 里 `model_name` / `lora_name` 为准；模型不齐时 `comfyui-skill` 提交会直接报错。若只跑 `-nortx` 工作流（无 RTX VSR），可跳过 RTX 相关节点依赖，但主模型/LoRA/CLIP/VAE 仍必需。

### 内置工作流（按显卡选）

| 工作流 | 用途 | RTX VSR 超分 | 适用显卡 |
|---|---|---|---|
| `anima-txt2img-aesthetic-lora` | 直出（主用） | ✅ 有（2x 超分） | **仅 N 卡 RTX** |
| `anima-txt2img-aesthetic-lora-run` | 跑图（主用） | ✅ 有（2x 超分） | **仅 N 卡 RTX** |
| `anima-txt2img-aesthetic-lora-nortx` | 直出（A 卡/无 RTX 备用） | ❌ 无 | 任意显卡 |
| `anima-txt2img-aesthetic-lora-run-nortx` | 跑图（A 卡/无 RTX 备用） | ❌ 无 | 任意显卡 |
| `anima-txt2img-base-nortx` | **测试用**（验证环境是否装好） | ❌ 无 | 任意显卡 |

> ⚠️ **RTXVideoSuperResolution 节点仅限 N 卡 RTX 系列**（RTX 20/30/40/50 系）。**A 卡 / Intel 核显 / 无 RTX 的 N 卡请用 `-nortx` 后缀的工作流**（无超分，出图分辨率即模型原生输出）。部署好后建议先跑 `anima-txt2img-base-nortx` 验证链路（节点最少、出图最快、不依赖 RTX）。

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
comfyui-skill list   # 应列出 5 个工作流（anima 系列）
curl http://127.0.0.1:8188/system_stats   # 有 JSON 返回 = ComfyUI 就绪
```

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
```

跑图（run）模式：`--mode run`，需另写 `workspace/args_character.json`（`{"character": "角色 @画师"}`）、`workspace/args_description.json`（`{"description": "场景描述"}`）、`workspace/args_negative.json`（`{"negative": "负面词"}`），三个文件齐了再提交。

### 可选环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `QQ_OPENID` | 空 | 配了则跑图完成后自动发 QQ 通知；不配则只打印（由 agent 播报） |
| `COMFY_OUTPUT_DIR` | `~/ComfyUI/output` | 出图目录（run_latest 查找输出图用） |
| `COMFY_DIR` / `COMFY_PY` / `COMFY_LOG` | `~/ComfyUI` | comfy_detach.py 启动用的 ComfyUI 路径/解释器/日志 |
| `WEBUI_SESSIONS` | 空 | 配了才启用「自动抓取 WebUI 会话提示词」（可选功能） |
| `DANBOORU_ENV` | `~/.env` | artist_rank.py 的 danbooru 凭据文件（DANBOORU_USER/API_KEY/USER_ID） |
| `HTTPS_PROXY` | 空 | artist_rank.py 访问 danbooru 的代理（国内网络可能需要） |

### 给 AI agent 用

本仓库同时是 skill 包：把 `SKILL.md` 拷进 agent 的 skills 目录（Hermes：`hermes skills install` 或拷贝到 `~/skills/`），agent 就会按文档自动走「直出/跑图」流程。

---

## 三、模型与工作流

| 模型 | 定位 | 工作流 |
|---|---|---|
| **Anima**（动漫/二次元，danbooru 标签体系，吃画师 tag） | `anima-txt2img-aesthetic-lora`（直出）/ `anima-txt2img-aesthetic-lora-run`（跑图），A 卡用 `-nortx` 版 | 模型文件见「快速开始」模型表 |

- 文本编码：双 CLIP（qwen3-vl-4b）
- 尺寸：横 1536×864 / 竖 864×1536（RTX 工作流自动 2x 超分）

## 四、两种用法

### 直出（direct）
对 Agent 说「来张 xxx 的图」→ 直接生成，**图发当前会话**。适合顺手要一张。

### 跑图（run-image）
对 Agent 说「**跑图**」→ 分步问答（场景 → 角色画师）→ 出图后**通知你去收图会话领图**。图不进聊天平台，适合正经出图。

> 角色支持指定/随机/按系列随机（genshin、touhou、arknights、wuthering 等），画师支持指定/随机——随机画师风格不可控，抽到不合适的换一个就是。

## 五、访问方式：局域网 + 远程

- **局域网**：同一 Wi-Fi 下，手机/平板浏览器直接开 **Hermes Web 界面**（hermes-webui，8787 端口）和 ComfyUI 前端（8188），操作/收图全在移动端完成——这是本方案的主场景，实测稳定
- **远程（远控方法，未实践 ⚠️）**：以下思路理论上可行，但**本仓库作者没有实际跑通过，不构成承诺**：
  - VPN 组网（Tailscale / ZeroTier）：加密隧道回家里网，安全但依赖第三方服务
  - 公网 IPv6 直连：本机若有运营商公网 IPv6，可直连——**注意**：公网 IPv6 是默认裸奔，无 NAT 兜底，必须先做好防火墙白名单 + HTTPS，否则等于把服务扔公网上
  - 远控类软件（如各类远程桌面）：能看屏幕操作，但带宽/延迟体验一般，且同样有暴露面问题
- **推荐组合**：局域网为主 + VPN 组网为辅；不建议裸奔公网端口

## 六、完全不上网的图片生成与接收（以 Hermes 为例）

这套流程最「干净」的用法：**图片从生成到接收，全程不经过任何消息平台服务器**。以下各端都属于 Hermes 生态：

- **Agent 端**：Hermes（Nous Research 的开源 agent 框架），本地跑，Agent 模型接云端 API——收需求、走问答、调脚本都靠它
- **Web 界面（8787）**：**`hermes-webui`（nesquena/hermes-webui）**——Hermes 的官方开源 Web 界面，跑在 8787 端口，局域网浏览器直接访问，收图会话就在这里
- **消息平台（QQ 等）**：Hermes 自带网关，可接 QQ/Telegram/Discord 等——**但本方案默认不上消息平台**，图只在本地/局域网流转；只有「跑图完成」这类纯文本通知（`hermes send`）才走网关，图片本身不经过平台服务器

```
手机/平板浏览器 ──局域网──▶ hermes-webui (8787) ──▶ 本地 ComfyUI (8188)
                             收图会话               ──▶ 出图显示在浏览器
        └──（可选）Hermes QQ 网关 ──▶ 只发文字通知「跑图完成✅」，图不走平台
```

这样图片只在「你的设备 → 你的电脑 → 你的浏览器」之间流转，第三方平台接触不到图。

## 七、免责声明

1. **生成模型的第三方属性**：出图由本地 ComfyUI + 第三方模型（Anima 等）完成，Agent 推理接云端 API——**模型输出的任何内容与内容审查行为，均与本仓库/skill 无关**，模型是第三方训练产物，仓库只提供调用流程。
2. **关于内容审核的边界**：本仓库只提供调用流程，不内置、也不替代任何内容审查机制。图片由本地 ComfyUI 与第三方模型生成，是否经过审核取决于你的部署环境（模型、接入方式、网络链路），本仓库对此不作任何验证或承诺。不同模型、不同接入方式的行为差异巨大，请自行评估。
3. **图片上传消息平台有法律风险**：把图片发到任何消息平台（QQ、Telegram、Discord、微信等），图片会明文经过平台服务器，涉黄等内容可能触犯当地法律（传播淫秽物品等），并面临封号风险。**本仓库强烈建议：图片只在本地/局域网流转，不要上传任何消息平台。** 使用者的行为与责任自负，与本仓库无关。
4. **合规提示**：请遵守你所在地区的法律法规与平台条款。未成年人内容无论本地还是云端都绝对禁止，没有任何借口。

## 八、致谢

- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) — 开源图生图工作流引擎
- [ComfyUI Good Anima](https://github.com/ShiroEirin/comfyui-good-anima) — 面向 AI 编程助手的 ComfyUI + Anima 二次元生图技能包（`comfyui-animatool` / `comfyui-manager` / `danbooru-tags`），本仓库的工作流组装与提交链路直接基于它，特此致谢（GPL-3.0，本项目整体按 GPL-3.0 发布）
- [Comfyui-Anima-Tools](https://github.com/nregret/Comfyui-Anima-Tools) — 角色/画师/姿势/场景/服装索引（`anima_tools.sqlite` 5 表）的数据来源（MIT；按协议保留原作者版权声明与完整致谢：AnimaDex / Anima-Style-Explorer / CircleStone Labs，见其仓库 README「鸣谢与致敬」节）
- [hermes-webui](https://github.com/nesquena/hermes-webui) — 开源的 Hermes Web 界面，本方案收图会话的载体
- [Hermes Agent](https://github.com/NousResearch/hermes-agent) — Nous Research 的开源 agent 框架
- 各模型作者（Anima / qwen3-vl / 各 LoRA 作者）与 danbooru 标签社区

## 九、文件来源说明

| 文件 | 来源 | License |
|---|---|---|
| `SKILL.md` / `README.md` / `COPYING` / `.gitignore` | **本仓库原创**（skill 流程文档与发布说明） | GPL-3.0 |
| `scripts/`（10 个 .py） | **本仓库原创**编排脚本（工作流组装/提交链路基于 comfyui-good-anima 的 comfyui-manager） | GPL-3.0 |
| `data/anima_tools.sqlite` | [Comfyui-Anima-Tools](https://github.com/nregret/Comfyui-Anima-Tools)（nregret）——画师/角色/服装/姿势/背景索引库 | MIT |
| `data/danbooru-tags.exe` | [comfyui-good-anima](https://github.com/ShiroEirin/comfyui-good-anima)（ShiroEirin）的 `danbooru-tags` 组件——canonical tag 查询工具 | GPL-3.0 |
| `data/tags_index.sqlite` | [comfyui-good-anima](https://github.com/ShiroEirin/comfyui-good-anima)（ShiroEirin）的 `danbooru-tags` 组件——danbooru 标签索引 | GPL-3.0 |

其余文件均为本仓库自研。第三方文件保持原样分发，未作修改；其各自许可证与版权声明见对应上游仓库。

---

**License**: GPL-3.0（本 skill 融合了 GPL-3.0 的 comfyui-good-anima，整体按 GPL-3.0 发布，见 COPYING）；其中 Comfyui-Anima-Tools 相关部分遵循其 MIT 声明（保留版权与致谢）；各模型/工具遵循其各自许可证。
