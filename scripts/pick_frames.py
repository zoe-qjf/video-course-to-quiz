#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Sample a low-res video and keep only the frames that actually changed.

Slides and chart annotations change slowly, so a plain "one frame per minute"
wastes image tokens on 20 near-identical pictures. This script compares
consecutive frames and keeps at most N distinct ones.

Usage:
    python pick_frames.py <video> --out <dir> [--max 12] [--gap 25] [--width 1100]

Writes <out>/frame_000.jpg ... and <out>/index.json (time, score per frame).
Prints the saved paths, cheapest-first for the caller to read.
"""
import argparse
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def thumb_bytes(frame, size=(64, 36)):
    img = frame.to_image().convert("L").resize(size)
    return img.tobytes()


def diff_score(a, b):
    if a is None:
        return 999.0
    return sum(abs(x - y) for x, y in zip(a, b)) / float(len(a))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--out", required=True)
    ap.add_argument("--max", type=int, default=12, dest="max_frames")
    ap.add_argument("--gap", type=float, default=25.0, help="min seconds between kept frames")
    ap.add_argument("--sample-fps", type=float, default=1.0)
    ap.add_argument("--width", type=int, default=1100)
    ap.add_argument("--threshold", type=float, default=6.0, help="min change score to keep")
    args = ap.parse_args()

    try:
        import av
    except ImportError:
        raise SystemExit("PyAV missing: pip install 'av==13.1.0'")
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        raise SystemExit("Pillow missing: pip install pillow")

    os.makedirs(args.out, exist_ok=True)

    # ---- pass 1: score consecutive sampled frames -------------------------
    container = av.open(args.video)
    step = 1.0 / max(args.sample_fps, 0.1)
    prev, last_t, scored = None, -1e9, []
    for frame in container.decode(video=0):
        t = float(frame.time or 0.0)
        if t - last_t < step:
            continue
        cur = thumb_bytes(frame)
        scored.append((t, diff_score(prev, cur)))
        prev, last_t = cur, t
    container.close()

    if not scored:
        raise SystemExit("no frames decoded")

    # ---- selection: biggest changes, respecting min gap -------------------
    scored[0] = (scored[0][0], 999.0)  # always keep the opening frame
    picked = []
    for t, score in sorted(scored, key=lambda x: -x[1]):
        if score < args.threshold and picked:
            break
        if all(abs(t - p[0]) >= args.gap for p in picked):
            picked.append((t, score))
        if len(picked) >= args.max_frames:
            break
    picked.sort()

    # ---- pass 2: seek and save -------------------------------------------
    container = av.open(args.video)
    saved = []
    for i, (t, score) in enumerate(picked):
        container.seek(int(t * 1_000_000), any_frame=False, backward=True)
        got = False
        for frame in container.decode(video=0):
            img = frame.to_image()
            w, h = img.size
            if w > args.width:
                img = img.resize((args.width, int(h * args.width / w)))
            name = "frame_%03d_%04ds.jpg" % (i, int(t))
            path = os.path.join(args.out, name)
            img.save(path, quality=85)
            saved.append({"path": path, "time": round(t, 1), "score": round(score, 1)})
            got = True
            break
        if not got:
            print("[warn] seek failed at %ss" % int(t))
    container.close()

    with open(os.path.join(args.out, "index.json"), "w", encoding="utf-8") as fh:
        json.dump({"count": len(saved), "frames": saved}, fh, ensure_ascii=False, indent=2)

    print("[ok] kept %d/%d sampled frames (gap=%.0fs, max=%d)"
          % (len(saved), len(scored), args.gap, args.max_frames))
    for item in saved:
        print("%s  t=%ss  score=%.1f" % (item["path"], int(item["time"]), item["score"]))


if __name__ == "__main__":
    main()
