# AGENTS.md · minimax-h3-image-turing

给 AI agent 的入口文件：在本仓工作、或用本仓产线出图时，按此执行。
完整分步 SOP（含体检表/救火表/特化档案）：**[docs/SOP.zh.md](docs/SOP.zh.md)** · English: [docs/en/SOP.md](docs/en/SOP.md)

## 这个仓是什么

在 2080Ti 22G（Turing / sm_75）上跑通 MiniMax-H3-Image（33.1B DiT）的**真机实测手册**。方法论纪律（姊妹仓 minimax-h3-turing 同规矩）：**结论必须真机实测，走过一步才能写一步，不许纸面推演**。

## 三步出图

```bash
# 1. 模型三件（~41GB，断点续传，sha256 全检；国内 mirror / 海外 hf）
python scripts/download_models.py --dest <ComfyUI>/models --source mirror
# 2. 启动 ComfyUI ≥ v0.45.0（Turing 安全参数）
<ComfyUI python> main.py --listen 127.0.0.1 --port 8188 --reserve-vram 2.5 --vram-headroom 0.5 --disable-pinned-memory
# 3. 一键出图（官方参数内置：6 步 euler/simple cfg=1）
python scripts/t2i.py --prompt "..." --width 1024 --height 1024 --seed 42
```

脚本纯 stdlib，加 `-I` 跑更稳。遇阻先读 SOP 第 5 节救火表，再动手修。

## 硬约束（违反必炸，背下来）

1. **ComfyUI ≥ v0.45.0**（PR #17655）。判据唯一可信：`/object_info` 含 `MiniMaxH3ImageConditioning`——版本文件/启动日志会说谎
2. **TE 配对铁律**：33.1B 正主只能配 `qwen3vl_32b_minimax_h3_int8_convrot`（hidden 5120）；`qwen3.5_9b_w4a8_gptq` 是 p-h3-image 变体专用（4096）。配错报 `mat1(Nx4096) mat2(5120x5376)`
3. **依赖三钉**：`comfy-kitchen==0.2.41` + `comfy-aimdo==0.6.0`（动态分页功臣，旧版报 `ModelVBAR pageout_callback` TypeError）+ `comfyui-frontend-package==1.59.1`
4. **torch 2.9.1+cu130**：sm_75 反量化红利的钥匙，低版本走软路径慢数倍
5. **显存 ≥22G**：动态分页峰值 19.5GB（1024²）/ 21.2GB（2048²），staged 合计 ≈41GB 是假象不用怕
6. **Windows 杀软**：下载/模型加载前关闭、跑完开回（12GB 级 staging 被实时扫描会卡 27 分钟级）
7. **jsdelivr tag 不可信**（re-tag 缓存分裂）：升级/补文件一律锚 commit sha，用 data API 拿权威清单

## 作者实测机速查（2026-11-16 已验证，可直接复用）

- ComfyUI：`D:/tools/ComfyUI-aki-v3/ComfyUI`（master@`e9afbccc` 已同步）；启动 `bash /d/tools/ComfyUI-aki-v3/h3_launch.sh`；关停=杀 8188 端口进程
- Python：`D:/tools/ComfyUI-aki-v3/python/python.exe`（PATH 里的 `python` 是商店空壳，勿用）
- 模型三件已就位 `models/{diffusion_models,text_encoders,vae}/`；视频仓 TE 直接复用
- 首跑基线：1024² 1.5min / 2048² 2.6min，seed=42 样图 `docs/assets/first_t2i_1024.png`
- 混合树升级备份：`D:/tools/ComfyUI-aki-v3/ComfyUI_backup_pre_h3image_1116/`（10 文件，回滚用）

## 仓库工作规范

- **双语成对改**：`README.md`（英）+ `README.zh-CN.md`（中）；docs 中文为主、`docs/en/` 英文镜像
- **勘误格式**：推翻旧结论时用删除线保留原文 + 修正（见 `docs/00-recon` 的 9B TE 段），不静默改写
- **发布路径**：本地 → `git push gitee main`（Gitee 权威）→ ECS 中继自动镜像 GitHub；git 身份用全局 IvenKooLab，勿 `-c` 临时覆盖
- **大文件红线**：模型权重不入库；生成的图落根目录自动 ignore，要展示的进 `docs/assets/` 且单张 ≤2MB
- **脚本纪律**：`scripts/` 保持纯 stdlib 零依赖；跑通才提交，提交信息写实测数据

## 已结案（勿重复研究）

- T8 双时钟：**不迁**——6 步蒸馏后 ~10s/step，无收益空间，且是视频链路专用 hack
- 图像版 PDD：**无事可做**——已烘进 6 步蒸馏发布权重
- SageAttention：**不碰**——sm_75 管线内原生崩溃（视频仓 docs/03 定论）
- 量化选型：w4a8 是 Turing 唯一解（bf16 放不下 / nvfp4 无硬件 / int8 无必要）

## 未开垦（领活从这里挑）

- [ ] edit / 参考图模式实测（`<Picture 1>` 语法 + `images`/`vae` 入参）
- [ ] w4a8 vs int8_convrot 量化对比（误差 + 速度）
- [ ] p-h3-image（9B TE 配套小模型）线
- [ ] 跨机器 SOP 验证（非作者机的复现记录）
