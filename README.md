# minimax-h3-image-turing

English | [简体中文](README.zh-CN.md)

**A field-tested handbook for running MiniMax H3-Image (33.1B) on a 2080Ti 22G mod card (Turing / sm_75).**

Sister repo of [minimax-h3-turing](https://github.com/IvenKooLab/minimax-h3-turing) (video). Same methodology: every conclusion comes from real runs on real hardware — quantization verdicts, measured benchmarks, and pitfalls paid for in GPU-hours, not paper math.

## TL;DR

**First light, 2026-11-16**: 1024² end-to-end in ~1.5 min on the 2080Ti 22G (2048²: 2.6 min) — w4a8 DiT + cu130 hardware dequant, peak VRAM 19.5–21.2 GB:

<p align="center"><img src="docs/assets/first_t2i_1024.png" width="360" alt="first t2i on the 2080Ti 22G" /></p>

The model weighs 66 GB in BF16 — but Comfy-Org ships an official quantized line, and the **w4a8 DiT is only 12.6 GB**, the same kitchen AsymW4A8Int8 layout our video repo already validated on sm_75 (via torch cu130). The working stack for a 22G card:

| Component | Pick | Size |
|---|---|---|
| DiT | `minimax_h3_image_pruned_w4a8` | 12.6 GB |
| Text encoder | `qwen3vl_32b_minimax_h3_int8_convrot` | 27.1 GB |
| VAE | `minimax_h3_image_vae_fp16` | 1.2 GB |

≈41 GB staged in total — comfy-aimdo dynamic paging takes turns, so the 22G card peaks at 19.5 GB (1024²) / 21.2 GB (2048²). ⚠️ The 7.3 GB `qwen3.5_9b_w4a8_gptq` TE pairs with the **p-h3-image variant only** (hidden 4096 ≠ the 33.1B DiT's 5120) — don't repeat our mistake.

Capabilities: text-to-image, image-to-image, multi-reference editing (9-image style). Image PDD is already baked into the 6-step distilled release — nothing extra to install.

## Quick start

```bash
# 1. models (~41 GB, resumable, sha256-verified; hf-mirror for CN)
python scripts/download_models.py --dest <ComfyUI>/models --source mirror
# 2. launch ComfyUI >= v0.45.0 with the Turing-safe flags
<ComfyUI python> main.py --listen 127.0.0.1 --port 8188 --reserve-vram 2.5 --vram-headroom 0.5 --disable-pinned-memory
# 3. one-shot t2i (official params baked in: 6 steps, euler/simple, cfg 1)
python scripts/t2i.py --prompt "a fluffy orange cat in a blacksmith apron" --width 1024 --height 1024 --seed 42
```

Full setup SOP with failure branches: **[docs/SOP.zh.md](docs/SOP.zh.md)** · [English](docs/en/SOP.md)

## Roadmap

- [x] Phase 0 — Recon: model anatomy, quantized variants, sizing (this README)
- [x] Phase 1 — First light (2026-11-16): w4a8 DiT + 32B TE on sm_75 cu130 — 1024² ~1.5 min, 2048² ~2.6 min (see [docs/SOP](docs/en/SOP.md))
- [ ] Phase 2 — Quantization verdict: w4a8 vs int8_convrot vs bf16-pruned (error + speed), Turing kernel compatibility
- [ ] Phase 3 — Benchmarks: t2i / edit / PDD timings; TE sharing study with the video repo (same Qwen3-VL lineage)
- [ ] Phase 4 — Pitfall FAQ (T8-style acceleration? Sage on sm_75 for a DiT this size? AUTOGROW template quirks)

## Model Download List

Official repo: [MiniMaxAI/MiniMax-H3-Image](https://huggingface.co/MiniMaxAI/MiniMax-H3-Image) (BF16, 66 GB DiT; the text encoder is **not** included — it loads from the MiniMax-H3 video repo, folder `text_encoder/`).

Quantized line (recommended): [Comfy-Org/MiniMax-H3-Image](https://huggingface.co/Comfy-Org/MiniMax-H3-Image) — exact sizes measured 2026-11-16:

| File | Size |
|---|---|
| diffusion_models/minimax_h3_image_pruned_w4a8.safetensors | 12.55 GB |
| diffusion_models/minimax_h3_image_pruned_int8_convrot.safetensors | 20.98 GB |
| diffusion_models/minimax_h3_image_pruned_bf16.safetensors | 40.23 GB |
| text_encoders/qwen3.5_9b_w4a8_gptq.safetensors | 7.34 GB |
| text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors | 27.14 GB |
| text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors | 15.69 GB |
| vae/minimax_h3_image_vae_fp16.safetensors | 1.17 GB |

China mirror: swap `huggingface.co` for `hf-mirror.com`. ComfyUI official templates: [t2i](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/image_minimax_h3_image_t2i.json) / [edit](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/image_minimax_h3_image_edit.json).

## Reproduction Environment

- GPU: 2080Ti 22G mod (Turing, sm_75) — see the [video repo](https://github.com/IvenKooLab/minimax-h3-turing) for the cu130/dequant groundwork this builds on
- Model license: MiniMax community license (this repo's MIT covers the handbook, not the weights)

## License

MIT
