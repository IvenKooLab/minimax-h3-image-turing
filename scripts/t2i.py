#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-shot t2i against a running ComfyUI (API mode) — MiniMax-H3-Image Turing handbook.

Builds a minimal official-parameter workflow (steps=6, cfg=1, euler/simple),
submits via POST /prompt, polls /history, saves the PNG locally.

Usage:
  python t2i.py --prompt "a cat in a blacksmith apron" --width 1024 --height 1024
  python t2i.py --prompt "..." --seed 42 --steps 6 --out my.png
  python t2i.py --prompt "..." --model minimax_h3_image_pruned_int8_convrot.safetensors
"""
import argparse
import json
import sys
import time
import urllib.request

DEFAULTS = {
    "unet": "minimax_h3_image_pruned_w4a8.safetensors",   # Turing 22G pick; int8_convrot for 24G+
    # 33.1B H3-Image expects Qwen3-VL-32B embeds (hidden 5120). The 7.3GB
    # qwen3.5_9b_w4a8_gptq pairs with the p-h3-image variant, NOT this DiT.
    "clip": "qwen3vl_32b_minimax_h3_int8_convrot.safetensors",  # same file the video repo uses
    "vae": "minimax_h3_image_vae_fp16.safetensors",
}


def build_graph(args):
    g = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": args.model, "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": args.clip, "type": "minimax", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": args.vae}},
        "4": {"class_type": "MiniMaxH3ImageConditioning",
              "inputs": {"clip": ["2", 0], "prompt": args.prompt,
                         "width": args.width, "height": args.height}},
        "5": {"class_type": "MiniMaxH3ImageConditioning",
              "inputs": {"clip": ["2", 0], "prompt": "", "width": args.width, "height": args.height}},
        "6": {"class_type": "KSampler",
              "inputs": {"model": ["1", 0], "positive": ["4", 0], "negative": ["5", 0],
                         "latent_image": ["4", 1], "seed": args.seed, "steps": args.steps,
                         "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple",
                         "denoise": 1.0}},
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["3", 0]}},
        "8": {"class_type": "SaveImage", "inputs": {"images": ["7", 0],
                                                    "filename_prefix": "h3image_t2i"}},
    }
    return g


def api(url, path, payload=None, timeout=30):
    req = urllib.request.Request(url + path,
                                 data=json.dumps(payload).encode() if payload is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--width", type=int, default=1024)
    ap.add_argument("--height", type=int, default=1024)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--steps", type=int, default=6)
    ap.add_argument("--model", default=DEFAULTS["unet"])
    ap.add_argument("--clip", default=DEFAULTS["clip"])
    ap.add_argument("--vae", default=DEFAULTS["vae"])
    ap.add_argument("--out", help="output png path (default h3image_t2i_<seed>.png)")
    ap.add_argument("--url", default="http://127.0.0.1:8188")
    args = ap.parse_args()

    wid = api(args.url, "/prompt", {"prompt": build_graph(args), "client_id": "t2i-handbook"})["prompt_id"]
    print("submitted prompt_id:", wid, flush=True)

    t0 = time.time()
    while True:
        time.sleep(3)
        h = api(args.url, "/history/%s" % wid, timeout=10)
        if wid not in h:
            continue
        st = h[wid].get("status", {})
        if st.get("status_str") == "error":
            print("WORKFLOW ERROR:", json.dumps(st.get("messages", []), ensure_ascii=False)[:2000])
            sys.exit(1)
        outs = h[wid].get("outputs", {})
        if outs:
            break
        if time.time() - t0 > 3600:
            raise SystemExit("timeout after 1h")

    for node_out in outs.values():
        for img in node_out.get("images", []):
            fn, sub = img["filename"], img.get("subfolder", "")
            q = "/view?filename=%s&subfolder=%s&type=%s" % (fn, sub, img.get("type", "output"))
            req = urllib.request.Request(args.url + q)
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            path = args.out or ("h3image_t2i_%d.png" % args.seed)
            with open(path, "wb") as f:
                f.write(data)
            print("saved: %s  (%.1f min total)" % (path, (time.time() - t0) / 60))


if __name__ == "__main__":
    main()
