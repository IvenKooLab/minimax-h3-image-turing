# SOP · MiniMax-H3-Image 从零到出图（2080Ti 22G / Turing sm_75）

> 读者：AI agent（ZCode / Claude Code 等）或人类操作者。每步 = 确切命令 + 预期输出 + 失败分支。
> 本 SOP 全部命令于 **2026-11-16** 在 2080Ti 22G + Windows + ComfyUI master@`e9afbccc`（≥ v0.45.0）实测通过。
> 英文版：[en/SOP.md](en/SOP.md) · 量化与显存勘误：[00-recon.zh.md](00-recon.zh.md)

## 0 · 前置体检（全过才继续）

| 检查 | 命令 | 必须看到 | 不过怎么办 |
|---|---|---|---|
| 显存 | `nvidia-smi --query-gpu=memory.total --format=csv` | ≥ 22000 MiB | 16G 卡带不动本栈，到此为止 |
| torch | `<python> -c "import torch;print(torch.__version__,torch.version.cuda)"` | `2.9.1+cu130 13.0` | cu121/cu124 能跑但反量化走软路径、慢数倍（视频仓 docs/01 的核心结论） |
| 磁盘 | - | ≥ 60 GB 空闲 | 模型 41 GB + 下载断点临时双份 |
| 杀软 | - | 实时防护**已关闭** | 12 GB 级模型 staging 被实时扫描会拖到 27 分钟级卡死（火绒实测），下载/加载前必关、跑完开回 |

## 1 · ComfyUI 要求：≥ v0.45.0（含 PR #17655）

- **就绪判据**（唯一可信）：服务启动后 `curl http://127.0.0.1:8188/object_info` 的 JSON 里能找到 `MiniMaxH3ImageConditioning`。
- 全新安装：`git clone https://github.com/comfyanonymous/ComfyUI` + `pip install -r requirements.txt`（Python 3.13）。
- 旧装升级（混合树经验）：不要信 tag——锚定 commit sha，用 jsdelivr data API 拉权威清单全量同步 `.py`，然后做**导入三连**：

```bash
<python> -c "import sys; sys.path.insert(0,'.'); import comfy.model_base; print('ok')"
<python> -c "import sys; sys.path.insert(0,'.'); import execution; print('ok')"
<python> -c "import sys; sys.path.insert(0,'.'); import comfy_extras.nodes_minimax_h3; print('ok')"
```

- 缺模块打地鼠（解析 `No module named 'x'` → 从同一 sha 补文件 → 重试，封顶 25 轮）——本仓 2026-11-16 用此法把 aki 混合树抬到 master@`e9afbccc`，1048 文件零失败。

### 依赖三钉（requirements 自带；手动排障时核对）

| 包 | 版本 | 作用 |
|---|---|---|
| `comfy-kitchen` | 0.2.41 | w4a8 CUDA 反量化内核 |
| `comfy-aimdo` | 0.6.0 | 动态分页加载（40GB 级权重轮流上场） |
| `comfyui-frontend-package` | 1.59.1 | 前端（headless 用不到，防启动警告） |

## 2 · 模型三件套（Turing 选型）

| 用途 | 文件（放 `<ComfyUI>/models/` 下同名子目录） | 大小 | 说明 |
|---|---|---|---|
| DiT | `diffusion_models/minimax_h3_image_pruned_w4a8.safetensors` | 12.55 GB | Turing 唯一选型（bf16 40GB 放不下；nvfp4 无硬件） |
| TE | `text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors` | 27.14 GB | 与视频仓同款——视频用户可直接复用，0 下载 |
| VAE | `vae/minimax_h3_image_vae_fp16.safetensors` | 1.17 GB | |

⚠️ **配对铁律**：`qwen3.5_9b_w4a8_gptq`（7.34 GB）是 **p-h3-image 变体**的 TE。配 33.1B 正主会报
`mat1 and mat2 shapes cannot be multiplied (Nx4096 and 5120x5376)`——4096 ≠ 5120，一眼识别。

下载（断点续传：中断后重跑同一条命令即可续）：

```bash
python scripts/download_models.py --dest <ComfyUI>/models --source mirror  # 国内 hf-mirror
python scripts/download_models.py --dest <ComfyUI>/models --source hf      # 海外
python scripts/download_models.py --list                                   # 只看清单
python scripts/download_models.py --dest <ComfyUI>/models --only dit,vae   # 视频仓用户复用 TE 时省 27GB
```

实测参考：21 GB 三件（w4a8+9B+VAE 的下载量）在 hf-mirror 上 90-107 MB/s，约 6.5 分钟；sha256 全检通过。

## 3 · 启动（Turing 内存安全参数）

```bash
<ComfyUI 内的 python> main.py --listen 127.0.0.1 --port 8188 \
  --reserve-vram 2.5 --vram-headroom 0.5 --disable-pinned-memory
```

- `--reserve-vram 2.5 --vram-headroom 0.5`：防桌面共享 GPU 时 TDR 黑屏
- `--disable-pinned-memory`：关掉 pinned memory 的 `read_file_slice` OOM 路径（视频仓 docs/01 定论）
- 就绪判据：`curl http://127.0.0.1:8188/system_stats` 返回 JSON

## 4 · 一键出图

```bash
python scripts/t2i.py --prompt "a fluffy orange cat in a blacksmith apron" --width 1024 --height 1024 --seed 42
```

- 官方参数已内置：**6 步 / euler / simple / cfg 1**（官方蒸馏设定），出图自动落盘当前目录
- 尺寸按面积预算自由取，官方调优点 2048²：

| 分辨率 | 全链路耗时 | 峰值显存 |
|---|---|---|
| 1024² | ~1.5 min（含加载） | 19.5 GB |
| 2048² | ~2.6 min（含加载） | 21.2 GB |

- 编辑/参考图模式（`<Picture 1>` 语法，`MiniMaxH3ImageConditioning` 的 `images`+`vae` 入参）：未实测，走官方 [edit 模板](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/image_minimax_h3_image_edit.json)。

## 5 · 失败分支速查（agent 救火表）

| 症状 | 根因 | 处方 |
|---|---|---|
| `ModelVBAR.__init__() got an unexpected keyword argument 'pageout_callback'` | comfy-aimdo 太旧 | `pip install comfy-aimdo==0.6.0` 后重启服务 |
| `mat1(Nx4096) mat2(5120x5376)` 形状错 | TE 配成 9B | 换 `qwen3vl_32b_minimax_h3_int8_convrot` |
| `ModuleNotFoundError: comfy.ldm.xxx` | core 混搭升级断链 | 打地鼠：解析缺模块名→同一 sha 补文件→循环到导入通过 |
| 模型加载卡 20 分钟+ | 杀软实时扫 staging | 关杀软重跑；平时加载完再开回 |
| 2048² OOM | 显存贴线 | 降到 1536²；确认三个启动参数都带 |

## 6 · Turing 特化档案（实测结论）

- **cu130 反量化中奖确认**：1024² 全链路 1.5 分钟（加载+6 步采样），GPU 100%——与视频仓同款红利，运行时版本决定速度
- **动态分页（comfy-aimdo）**：staged 合计 ≈40 GB，22G 卡峰值仅 19.5 GB（1024²）/ 21.2 GB（2048²），无需手动 CPU offload
- **T8 双时钟：不迁**。6 步蒸馏后 ~10 s/step 级，无收益空间；且 T8 是视频链路专用 hack
- **图像版 PDD：无事可做**——已烘进 6 步蒸馏发布权重
- **SageAttention：不碰**——视频仓已定论 sm_75 管线内原生崩溃
- 勘误记录：初版侦察"21 GB 极限可跑（9B TE）"是配对误判，正确显存账见 [00-recon.zh.md](00-recon.zh.md) 修正段

## 7 · 本 SOP 的验证环境

- 2080Ti 22G 魔改 / torch 2.9.1+cu130 / Windows / aki 包内嵌 Python 3.13
- ComfyUI master@`e9afbccc`（v0.45.0 后 5 天）+ 依赖三钉
- 首图（seed=42）：[assets/first_t2i_1024.png](assets/first_t2i_1024.png)
