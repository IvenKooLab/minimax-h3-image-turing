# 00 · 侦察笔记（模型解剖）

> 2026-11-16 发布日。以下事实直接读自官方仓库（大小经 HF API 实测），零猜测。

## 模型是什么

- **DiT**：33.1B 参数，dense 单流 transformer，50 层，hidden 5376 / 56 heads / FFN 14336，3D multimodal RoPE——与视频模型同款 H3-Omni-Transformer 架构转图像
- **文本编码器**：MiniMax-H3（视频）的完整 Qwen3-VL，未改动；DiT 读**第 50 层 hidden states**。图像仓不含 TE——从视频仓 `text_encoder/` 加载
- **图像 VAE**：CNN encoder + 2D ViT decoder（24 层），16x 空间下采样，24 latent 通道；2x2 patch → 每 token 覆盖 32x32 像素
- **图像版 PDD**：官方仓自带 `pdd_config.json` + `pdd_fused_heads.safetensors`

## 官方量化线（Comfy-Org），2026-11-16 实测

见 [英文版](en/00-recon.md) 完整表格。要点：**w4a8 DiT 12.55GB**（与视频 W4A8 同 kitchen 布局）；**qwen3.5_9b_w4a8_gptq 7.34GB 是 p-h3-image 变体的 TE**（⚠️ 与 33.1B 正主不配对，见显存账一节的实测修正）；nvfp4 在 Turing 不可用（无 FP4 张量核心）。

## Turing (sm_75) 显存账（⚠️ 首跑后修正）

- ~~最小组合 ≈21GB（w4a8 DiT + 9B TE + VAE）~~ **实测修正**：qwen3.5_9b 的 hidden=4096，与 33.1B DiT 输入投影 5120×5376 不配对（KSampler 直接形状报错）——9B 是 p-h3-image 变体专用。正主 TE = qwen3vl_32b（视频仓同款 int8_convrot 27.14GB）
- **实测栈**：w4a8 DiT 13.6GB + 32B TE 25.9GB + VAE 1.1GB（staged 合计 ≈40GB）——靠 comfy-aimdo 动态分页轮流上场，22G 卡**峰值 19.5GB** 实测可跑，无需手动 CPU offload
- w4a8 走 kitchen CUDA 反量化——视频仓已验证 sm_75 + torch cu130 可用（见视频仓 docs/01）；图像首跑同样中奖：1024² 全链路 1.5 分钟
- 官方 t2i 模板用**子图封装**（主体是一个 subgraph UUID 节点）——API 直连不需要扁平化，见 SOP

## 本仓库要回答的问题

1. w4a8 DiT 在 sm_75 cu130 上能否首跑点亮？
2. TE 实用选择——新 9B GPTQ vs 视频仓的 qwen3vl_4b_fp8（若第 50 层兼容）？
3. t2i / edit / PDD 在这张卡上的真实耗时？
4. 视频仓的 T8/Sage 教训能否迁移到 33B 图像 DiT？
