#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MiniMax-H3-Image model downloader — Turing (sm_75) hand-book edition.

stdlib only (urllib + threading), zero dependencies.

- Sources: hf-mirror.com (CN-friendly, default probe order) / huggingface.co
- Parallel range chunks with per-chunk resume (.parts) — safe against flaky CN links
- sha256 verified against HuggingFace LFS oid after assembly

Usage:
  python download_models.py --list                      # show official files & sizes
  python download_models.py --dest <ComfyUI>/models     # Turing trio (~21GB), recommended
  python download_models.py --dest ... --only dit,vae   # subset
  python download_models.py --dest ... --source hf      # force huggingface.co

Turing pick (sm_75, 22G): w4a8 DiT + qwen3.5_9b GPTQ TE + fp16 VAE.
nvfp4 needs FP4 tensor cores (no on Turing); bf16 DiT 40GB and int8 32B TE
do not fit a 22G budget with activation headroom.
"""
import argparse
import hashlib
import json
import os
import sys
import threading
import time
import urllib.request
import urllib.error

REPO = "Comfy-Org/MiniMax-H3-Image"

# key -> repo-relative path (already mirrors ComfyUI models/ subdirs)
FILES = {
    "dit": "diffusion_models/minimax_h3_image_pruned_w4a8.safetensors",
    "te":  "text_encoders/qwen3.5_9b_w4a8_gptq.safetensors",
    "vae": "vae/minimax_h3_image_vae_fp16.safetensors",
}

APIS = {
    "mirror": "https://hf-mirror.com/api/models/%s/tree/main?recursive=true" % REPO,
    "hf":     "https://huggingface.co/api/models/%s/tree/main?recursive=true" % REPO,
}
BASES = {
    "mirror": "https://hf-mirror.com/%s/resolve/main/" % REPO,
    "hf":     "https://huggingface.co/%s/resolve/main/" % REPO,
}
UA = {"User-Agent": "Mozilla/5.0 (H3-Image-Turing-handbook downloader)"}
BLOCK = 8 * 1024 * 1024  # 8MB read block


def log(msg):
    print("[%s] %s" % (time.strftime("%H:%M:%S"), msg), flush=True)


def http_get(url, headers=None, timeout=60):
    req = urllib.request.Request(url, headers=dict(UA, **(headers or {})))
    return urllib.request.urlopen(req, timeout=timeout)


def fetch_tree(source):
    with http_get(APIS[source], timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def pick_tree(prefer):
    order = [prefer] if prefer in ("mirror", "hf") else ["mirror", "hf"]
    last_err = None
    for s in order:
        try:
            tree = fetch_tree(s)
            log("file list fetched via %s (%d entries)" % (s, len(tree)))
            return tree, s
        except Exception as e:  # noqa: BLE001
            last_err = e
            log("file list via %s failed: %s" % (s, e))
    raise SystemExit("cannot fetch file list from any source: %s" % last_err)


def remote_size(url):
    """HEAD content-length; falls back to a 1-byte Range probe."""
    for _ in range(6):
        try:
            with http_get(url, timeout=30) as r:
                cl = r.headers.get("Content-Length")
                if cl:
                    return int(cl)
        except Exception:  # noqa: BLE001
            time.sleep(2)
    req = urllib.request.Request(url, headers=dict(UA, **{"Range": "bytes=0-0"}))
    with urllib.request.urlopen(req, timeout=30) as r:
        return int(r.headers.get("Content-Range").split("/")[-1])


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(BLOCK)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


class PartWriter(threading.Thread):
    """One Range chunk -> .parts/part_NNN, resumable by existing part size."""

    def __init__(self, idx, url, part_path, start, end, progress, lock):
        super().__init__(daemon=True)
        self.idx, self.url = idx, url
        self.part_path, self.r0, self.r1 = part_path, start, end
        self.progress, self.lock = progress, lock
        self.error = None

    def run(self):
        total = self.r1 - self.r0 + 1
        try:
            have = os.path.getsize(self.part_path) if os.path.exists(self.part_path) else 0
        except OSError:
            have = 0
        if have >= total:
            with self.lock:
                self.progress[self.idx] = total
            return
        if have:
            with self.lock:
                self.progress[self.idx] = have
        for attempt in range(8):
            try:
                hdrs = {"Range": "bytes=%d-%d" % (self.r0 + have, self.r1)}
                with http_get(self.url, hdrs) as r, open(self.part_path, "ab") as f:
                    while True:
                        b = r.read(BLOCK)
                        if not b:
                            break
                        f.write(b)
                        have += len(b)
                        with self.lock:
                            self.progress[self.idx] = have
                if have >= total:
                    return
                raise IOError("stream ended early (%d/%d)" % (have, total))
            except Exception as e:  # noqa: BLE001
                self.error = e
                time.sleep(min(2 * (attempt + 1), 15))
        self.error = self.error or IOError("part %d exhausted retries" % self.idx)


def download_file(rel_path, dest_dir, size, sha, base, connections):
    final = os.path.join(dest_dir, rel_path)
    os.makedirs(os.path.dirname(final), exist_ok=True)

    if os.path.exists(final):
        if os.path.getsize(final) == size:
            log("%s: exists, verifying sha256 ..." % rel_path)
            if sha256_file(final) == sha:
                log("%s: OK (cached)" % rel_path)
                return True
            log("%s: sha mismatch on cached file, re-downloading" % rel_path)
        else:
            log("%s: size mismatch on disk (%d != %d), re-downloading"
                % (rel_path, os.path.getsize(final), size))

    url = BASES[base] + rel_path
    parts_dir = final + ".parts"
    os.makedirs(parts_dir, exist_ok=True)

    nparts = max(1, min(connections, size // (64 * 1024 * 1024) + 1))
    bounds = []
    step = size // nparts
    for i in range(nparts):
        s = i * step
        e = (size - 1) if i == nparts - 1 else (s + step - 1)
        bounds.append((s, e))

    t0 = time.time()
    for round_ in range(3):
        progress, lock = {}, threading.Lock()
        parts = []
        for i, (s, e) in enumerate(bounds):
            parts.append(PartWriter(i, url, os.path.join(parts_dir, "part_%03d" % i),
                                    s, e, progress, lock))
        reporter = threading.Thread(target=_report, daemon=True,
                                    args=(rel_path, size, progress, lock, t0))
        reporter.start()
        for p in parts:
            p.start()
        for p in parts:
            p.join()

        def part_ok(i):
            try:
                return os.path.getsize(os.path.join(parts_dir, "part_%03d" % i)) == \
                    bounds[i][1] - bounds[i][0] + 1
            except OSError:
                return False

        if all(p.error is None and part_ok(i) for i, p in enumerate(parts)):
            break
        failed = [i for i, p in enumerate(parts) if p.error is not None or not part_ok(i)]
        log("%s: round %d failed parts %s, retrying" % (rel_path, round_ + 1, failed))
    else:
        return False

    log("%s: assembling + sha256 ..." % rel_path)
    h = hashlib.sha256()
    tmp = final + ".assembling"
    with open(tmp, "wb") as out:
        for i in range(nparts):
            with open(os.path.join(parts_dir, "part_%03d" % i), "rb") as f:
                while True:
                    b = f.read(BLOCK)
                    if not b:
                        break
                    out.write(b)
                    h.update(b)
    if h.hexdigest() != sha:
        log("%s: SHA256 MISMATCH, cleaning up" % rel_path)
        os.remove(tmp)
        _rm(parts_dir)
        return False
    os.replace(tmp, final)
    _rm(parts_dir)
    log("%s: DONE %s in %.1f min" % (rel_path, _gb(size), (time.time() - t0) / 60))
    return True


def _report(rel_path, size, progress, lock, t0):
    last = -1
    while True:
        with lock:
            done = sum(progress.get(i, 0) for i in range(1024))
        mbps = done / max(time.time() - t0, 1) / 1e6
        if done != last:
            log("%s: %s / %s  (%.1f MB/s)" % (rel_path, _gb(done), _gb(size), mbps))
            last = done
        time.sleep(15)


def _gb(n):
    return "%.2fGB" % (n / 1e9)


def _rm(path):
    import shutil
    shutil.rmtree(path, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dest", help="ComfyUI models directory (contains diffusion_models/ etc.)")
    ap.add_argument("--only", help="comma keys: dit,te,vae (default all)")
    ap.add_argument("--source", choices=["mirror", "hf", "auto"], default="auto")
    ap.add_argument("--connections", type=int, default=24)
    ap.add_argument("--list", action="store_true", help="list official files and exit")
    args = ap.parse_args()

    tree, base = pick_tree(args.source)
    meta = {}
    for f in tree:
        if f.get("type") == "file" and f.get("lfs"):
            meta[f["path"]] = (f["lfs"]["size"], f["lfs"]["oid"])

    if args.list:
        print("\n%-62s %10s  sha256(prefix)" % ("file", "size"))
        for p, (sz, oid) in sorted(meta.items()):
            print("%-62s %9s  %s" % (p, _gb(sz), oid[:16]))
        return

    keys = [k.strip() for k in args.only.split(",")] if args.only else list(FILES)
    unknown = [k for k in keys if k not in FILES]
    if unknown:
        raise SystemExit("unknown --only keys: %s (valid: %s)" % (unknown, list(FILES)))
    if not args.dest:
        raise SystemExit("--dest is required (point it at your ComfyUI models directory)")

    todo = []
    for k in keys:
        rel = FILES[k]
        if rel not in meta:
            raise SystemExit("%s not found in %s (upstream layout changed?)" % (rel, REPO))
        sz, oid = meta[rel]
        todo.append((rel, args.dest, sz, oid))
        print("plan: %-58s %8s -> %s" % (rel, _gb(sz), os.path.join(args.dest, rel)))

    ok = True
    for rel, dest_dir, sz, oid in todo:
        ok &= download_file(rel, dest_dir, sz, oid, base, args.connections)
    if not ok:
        sys.exit(1)
    log("ALL DONE")


if __name__ == "__main__":
    main()
