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
| TE qwen3.5_9b_w4a8_gptq | 7.34 GB | GPTQ — ⚠️ pairs with the **p-h3-image** variant only (hidden 4096), NOT this 33.1B DiT |
| TE qwen3vl_32b_int8_convrot | 27.14 GB | |
| TE qwen3vl_32b_nvfp4_awq | 15.69 GB | nvfp4 — sm_75 lacks the tensor cores for this path |
| VAE fp16 | 1.17 GB | |

## Turing (sm_75) sizing

- ~~Minimum stack 21 GB with the 9B TE~~ **First-light correction (2026-11-16)**: the 9B TE's hidden size (4096) does not match the 33.1B DiT input projection (5120→5376) — KSampler fails with a shape error. The 9B file belongs to the **p-h3-image** variant. The real TE is `qwen3vl_32b` int8_convrot (27.1 GB — the same file the video repo already ships)
- **Measured stack**: w4a8 DiT 13.6 + 32B TE 25.9 + VAE 1.1 GB staged (≈40 GB total) — comfy-aimdo dynamic paging takes turns; **peak 19.5 GB on the 22G card**, no manual CPU offload needed
- The w4a8 path dequantizes through the kitchen CUDA backend — the exact mechanism our video repo proved working on sm_75 with torch 2.9.1+cu130 (see docs/01 there). First light confirms it: 1024² end-to-end in ~1.5 min
- nvfp4 TE is out on Turing (no FP4 tensor cores); convrot_w4a4 is out for the same reason the video repo documented

## Open questions — answered by first light (2026-11-16)

1. ✅ The w4a8 DiT runs on sm_75 cu130 — 1024x1024 end-to-end in ~1.5 min (load + 6-step sampling); see the [SOP](../SOP.zh.md)
2. ✅ Practical TE = qwen3vl_32b int8_convrot (the video repo's file); the 9B GPTQ belongs to p-h3-image
3. ⏳ t2i timings are landing in the SOP; edit mode untested so far
4. T8: not ported — the 6-step distilled release already samples in ~10 s/step, too little headroom to be worth a video-specific hack; PDD: already baked into the released 6-step weights, nothing to do
