# SOP · MiniMax-H3-Image from zero to first image (2080Ti 22G / Turing sm_75)

> Audience: AI agents (ZCode / Claude Code etc.) or human operators. Every step = exact command + expected output + failure branch.
> Every command below was verified on **2026-11-16** on a 2080Ti 22G, Windows, ComfyUI master@`e9afbccc` (≥ v0.45.0).
> 中文版：[../SOP.zh.md](../SOP.zh.md) · quant & VRAM corrections: [00-recon.md](00-recon.md)

## 0 · Pre-flight checks (all must pass)

| Check | Command | Must see | If not |
|---|---|---|---|
| VRAM | `nvidia-smi --query-gpu=memory.total --format=csv` | ≥ 22000 MiB | 16G cards cannot carry this stack — stop here |
| torch | `<python> -c "import torch;print(torch.__version__,torch.version.cuda)"` | `2.9.1+cu130 13.0` | cu121/cu124 runs but dequantizes on the slow software path — multiples slower (video repo docs/01) |
| Disk | - | ≥ 60 GB free | models 41 GB + resumable download temps |
| Antivirus | - | real-time protection **OFF** | real-time scanning of 12 GB-scale model staging can stall for 27+ minutes (Huorong, measured). Off for download/load, back on after |

## 1 · ComfyUI requirement: ≥ v0.45.0 (contains PR #17655)

- **Readiness test** (the only one to trust): after startup, `curl http://127.0.0.1:8188/object_info` contains `MiniMaxH3ImageConditioning`.
- Fresh install: `git clone https://github.com/comfyanonymous/ComfyUI` + `pip install -r requirements.txt` (Python 3.13).
- Upgrading an existing hybrid tree: don't trust tags — pin a commit sha, bulk-sync all `.py` via the jsdelivr data API file list, then run the **import triple**:

```bash
<python> -c "import sys; sys.path.insert(0,'.'); import comfy.model_base; print('ok')"
<python> -c "import sys; sys.path.insert(0,'.'); import execution; print('ok')"
<python> -c "import sys; sys.path.insert(0,'.'); import comfy_extras.nodes_minimax_h3; print('ok')"
```

- Missing-module whack-a-mole: parse `No module named 'x'` → fetch that file from the same sha → retry, cap 25 rounds. This exact method lifted our mixed aki tree to master@`e9afbccc` on 2026-11-16 — 1048 files, zero failures.

### The three pinned deps (in requirements.txt; verify when debugging manually)

| Package | Version | Role |
|---|---|---|
| `comfy-kitchen` | 0.2.41 | w4a8 CUDA dequant kernels |
| `comfy-aimdo` | 0.6.0 | dynamic VRAM paging (40 GB-scale weights take turns) |
| `comfyui-frontend-package` | 1.59.1 | frontend (headless doesn't need it; keeps startup quiet) |

## 2 · The model trio (Turing pick)

| Role | File (under `<ComfyUI>/models/`) | Size | Notes |
|---|---|---|---|
| DiT | `diffusion_models/minimax_h3_image_pruned_w4a8.safetensors` | 12.55 GB | the only Turing-viable pick (bf16 40 GB won't fit; nvfp4 has no hardware) |
| TE | `text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors` | 27.14 GB | same file the video repo ships — reuse it, 0 GB download |
| VAE | `vae/minimax_h3_image_vae_fp16.safetensors` | 1.17 GB | |

⚠️ **Pairing rule**: `qwen3.5_9b_w4a8_gptq` (7.34 GB) is the TE of the **p-h3-image variant**. Paired with the 33.1B DiT it fails with
`mat1 and mat2 shapes cannot be multiplied (Nx4096 and 5120x5376)` — 4096 ≠ 5120, unmistakable.

Download (resumable: rerun the same command after an interruption):

```bash
python scripts/download_models.py --dest <ComfyUI>/models --source mirror  # CN: hf-mirror
python scripts/download_models.py --dest <ComfyUI>/models --source hf      # international
python scripts/download_models.py --list                                   # list only
python scripts/download_models.py --dest <ComfyUI>/models --only dit,vae   # video-repo users reuse their TE, save 27 GB
```

Reference: the 21 GB download set ran at 90-107 MB/s on hf-mirror, ~6.5 min, sha256 all verified.

## 3 · Launch (Turing memory-safe flags)

```bash
<ComfyUI's python> main.py --listen 127.0.0.1 --port 8188 \
  --reserve-vram 2.5 --vram-headroom 0.5 --disable-pinned-memory
```

- `--reserve-vram 2.5 --vram-headroom 0.5`: prevents TDR black screens on a desktop-shared GPU
- `--disable-pinned-memory`: kills the pinned-memory `read_file_slice` OOM path (video repo docs/01 verdict)
- Ready when: `curl http://127.0.0.1:8188/system_stats` returns JSON

## 4 · One-shot t2i

```bash
python scripts/t2i.py --prompt "a fluffy orange cat in a blacksmith apron" --width 1024 --height 1024 --seed 42
```

- Official parameters baked in: **6 steps / euler / simple / cfg 1** (the distilled release setting); the PNG lands in the working directory
- Resolution is area-budgeted, official tuning point 2048²:

| Resolution | End-to-end | Peak VRAM |
|---|---|---|
| 1024² | ~1.5 min (incl. load) | 19.5 GB |
| 2048² | ~2.6 min (incl. load) | 21.2 GB |

- Edit / reference mode (`<Picture 1>` syntax, `MiniMaxH3ImageConditioning`'s `images`+`vae` inputs): untested here — use the official [edit template](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/image_minimax_h3_image_edit.json).

## 5 · Failure branches (agent triage table)

| Symptom | Root cause | Fix |
|---|---|---|
| `ModelVBAR.__init__() got an unexpected keyword argument 'pageout_callback'` | comfy-aimdo too old | `pip install comfy-aimdo==0.6.0`, restart server |
| shape error `mat1(Nx4096) mat2(5120x5376)` | 9B TE wired in | swap to `qwen3vl_32b_minimax_h3_int8_convrot` |
| `ModuleNotFoundError: comfy.ldm.xxx` | mixed-version core upgrade | whack-a-mole: parse the missing module → fetch from same sha → loop until imports pass |
| model load stalls 20+ min | antivirus scanning staging | disable AV, rerun; re-enable after load |
| OOM at 2048² | VRAM at the edge | drop to 1536²; confirm all three launch flags |

## 6 · Turing specialization dossier (measured)

- **cu130 dequant pays off here too**: 1024² end-to-end 1.5 min (load + 6-step sampling), GPU at 100% — same dividend as the video repo; the runtime version decides the speed
- **Dynamic paging (comfy-aimdo)**: ≈40 GB staged total, peak only 19.5 GB (1024²) / 21.2 GB (2048²) on the 22G card — no manual CPU offload needed
- **T8 dual-clock: not ported.** After the 6-step distillation there's ~10 s/step left — no headroom worth a video-specific hack
- **Image PDD: nothing to do** — already baked into the released 6-step weights
- **SageAttention: hands off** — video repo verdict: native crash inside the sm_75 pipeline
- Errata: the original recon's "21 GB minimum (9B TE)" was a pairing misread; the corrected VRAM math lives in [00-recon.md](00-recon.md)

## 7 · Environment this SOP was verified on

- 2080Ti 22G mod / torch 2.9.1+cu130 / Windows / Python 3.13 (aki pack embedded)
- ComfyUI master@`e9afbccc` (5 days after v0.45.0) + the three pinned deps
- First image (seed=42): [assets/first_t2i_1024.png](../assets/first_t2i_1024.png)
