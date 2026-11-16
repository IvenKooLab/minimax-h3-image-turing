# minimax-h3-image-turing

[English](README.md) | 简体中文

**在 2080Ti 22G 魔改卡（Turing / sm_75）上跑通 MiniMax H3-Image（33.1B）的实测手册。**

姊妹仓：[minimax-h3-turing](https://gitee.com/IvenKooLab/minimax-h3-turing)（视频线）。同一套方法论：所有结论来自真机实测——量化判决、基准数据、真金白银烧出来的坑，非纸面推演。

## TL;DR

BF16 权重 66 GB 跑不动——但 Comfy-Org 官方量化线已上线，**w4a8 DiT 仅 12.6 GB**，与视频仓已验证的 kitchen AsymW4A8Int8 布局同款（sm_75 走 torch cu130 反量化）。22G 卡最小可行组合：

| 组件 | 选择 | 大小 |
|---|---|---|
| DiT | `minimax_h3_image_pruned_w4a8` | 12.6 GB |
| 文本编码器 | `qwen3.5_9b_w4a8_gptq` | 7.3 GB |
| VAE | `minimax_h3_image_vae_fp16` | 1.2 GB |
| **合计** | | **≈21 GB → 22G 卡可跑**（TE 可 CPU offload 留余量） |

能力：文生图、图生图、多参考图编辑，且官方同步发布了**图像版 PDD**（`pdd_config.json` + fused heads）。

## 路线图

- [x] Phase 0 — 情报侦察：模型解剖、量化变体、显存测算（本 README）
- [ ] Phase 1 — 首跑：下载 w4a8 套装，2080Ti 首张 t2i
- [ ] Phase 2 — 量化判决：w4a8 vs int8_convrot vs bf16-pruned（误差+速度），Turing 内核兼容性
- [ ] Phase 3 — 基准：t2i / edit / PDD 计时；与视频仓的 TE 共享研究（同源 Qwen3-VL）
- [ ] Phase 4 — 踩坑 FAQ（T8 式加速？这个体量的 DiT 上 Sage on sm_75？AUTOGROW 模板坑）

## 模型下载清单

官方仓：[MiniMaxAI/MiniMax-H3-Image](https://huggingface.co/MiniMaxAI/MiniMax-H3-Image)（BF16 66 GB；**不含文本编码器**——从 MiniMax-H3 视频仓 `text_encoder/` 目录加载）。

量化线（推荐）：[Comfy-Org/MiniMax-H3-Image](https://huggingface.co/Comfy-Org/MiniMax-H3-Image)——2026-11-16 实测大小：

| 文件 | 大小 |
|---|---|
| diffusion_models/minimax_h3_image_pruned_w4a8.safetensors | 12.55 GB |
| diffusion_models/minimax_h3_image_pruned_int8_convrot.safetensors | 20.98 GB |
| diffusion_models/minimax_h3_image_pruned_bf16.safetensors | 40.23 GB |
| text_encoders/qwen3.5_9b_w4a8_gptq.safetensors | 7.34 GB |
| text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors | 27.14 GB |
| text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors | 15.69 GB |
| vae/minimax_h3_image_vae_fp16.safetensors | 1.17 GB |

国内镜像：huggingface.co 换 hf-mirror.com。ComfyUI 官方模板：[t2i](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/image_minimax_h3_image_t2i.json) / [edit](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/image_minimax_h3_image_edit.json)。

## 复现环境

- GPU：2080Ti 22G 魔改（Turing，sm_75）——cu130/反量化地基见[视频仓](https://gitee.com/IvenKooLab/minimax-h3-turing)
- 模型许可：MiniMax 社区协议（本仓库 MIT 只覆盖手册内容，不覆盖权重）

## License

MIT
