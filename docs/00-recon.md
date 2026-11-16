# 00 · Model Anatomy & Recon Notes

> 2026-11-16, release day. Facts below read straight from the official repos (sizes measured via the HF API); nothing here is guesswork.

## What the model is

- **DiT**: 33.1B params, dense single-stream transformer, 50 layers, hidden 5376, 56 heads, FFN 14336, 3D multimodal RoPE — the same H3-Omni-Transformer architecture as the video model, repurposed for images
- **Text encoder**: the *full* Qwen3-VL encoder from MiniMax-H3 (video), unchanged. The DiT consumes the **50th layer's hidden states**. Not shipped in the image repo — loads from the video repo's `text_encoder/` folder (66.7 GB full; quantized options below)
- **Image VAE**: CNN encoder + 2D ViT decoder (24 layers), 16x spatial downsampling, 24 latent channels; DiT patchifies with 2x2 patches → each token covers 32x32 px
- **PDD for images**: `pdd_config.json` + `pdd_fused_heads.safetensors` ship in the official repo — the image edition of the parallel-decoding distillation we know from the video line

## Official quantized line (Comfy-Org), sizes measured 2026-11-16

| File | Size | Notes |
|---|---|---|
| pruned_w4a8 | 12.55 GB | kitchen AsymW4A8Int8 — same layout as the video W4A8 we validated on sm_75 |
| pruned_int8_convrot | 20.98 GB | |
| pruned_bf16 | 40.23 GB | |
| TE qwen3.5_9b_w4a8_gptq | 7.34 GB | new Qwen3.5-9B option, GPTQ — smallest TE |
| TE qwen3vl_32b_int8_convrot | 27.14 GB | |
| TE qwen3vl_32b_nvfp4_awq | 15.69 GB | nvfp4 — sm_75 lacks the tensor cores for this path |
| VAE fp16 | 1.17 GB | |

## Turing (sm_75) sizing

- **Minimum stack**: w4a8 DiT (12.6) + 9B TE (7.3) + VAE (1.2) ≈ **21 GB** — fits 22G with zero headroom; CPU-offload the TE for breathing room
- The w4a8 path dequantizes through the kitchen CUDA backend — the exact mechanism our video repo proved working on sm_75 with torch 2.9.1+cu130 (see docs/01 there). Expect the same "runtime decides the speed" behavior
- nvfp4 TE is out on Turing (no FP4 tensor cores); convrot_w4a4 is out for the same reason the video repo documented

## Open questions this repo will answer

1. Does the w4a8 DiT actually run on sm_75 cu130 (first light)?
2. Which TE is the practical pick — the new 9B GPTQ vs the video repo's qwen3vl_4b_fp8 (if layer-50 compatible)?
3. Real timings for t2i / edit / PDD on this card
4. Do the T8/Sage lessons from the video repo transfer to a 33B image DiT?
