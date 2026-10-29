#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Transcribe an audio file locally with faster-whisper, or reuse existing subtitles.

Usage:
    python transcribe.py <audio> --out <dir> [--model small] [--lang zh] [--prompt "..."]

Writes <out>/transcript.txt with one `[mm:ss] text` line per segment.

Notes:
  * requires faster-whisper and av<14 (see references/troubleshooting.md)
  * first run downloads the model; HF mirror + xet-disabled are set automatically
  * subsequent runs switch to offline mode when the model is already cached
"""
import argparse
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_PROMPT = (
    "以下是一段中文教学视频的语音转写，内容涉及专业术语，"
    "请尽量使用规范的中文书面表达。"
)


def model_cached(root, model):
    tag = "models--Systran--faster-whisper-%s" % model
    return os.path.isdir(os.path.join(root, tag))


def check_av():
    try:
        import av
    except ImportError:
        raise SystemExit("PyAV missing: pip install 'av==13.1.0'")
    major = int(str(av.__version__).split(".")[0])
    if major >= 14:
        raise SystemExit(
            "PyAV %s is too new for faster-whisper (metadata_errors removed).\n"
            "Run: pip install 'av==13.1.0'" % av.__version__
        )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="small")
    ap.add_argument("--lang", default="zh")
    ap.add_argument("--prompt", default=DEFAULT_PROMPT)
    ap.add_argument("--model-dir", default=os.path.expanduser("~/.cache/video-kit/models"))
    ap.add_argument("--beam", type=int, default=2)
    ap.add_argument("--threads", type=int, default=0)
    args = ap.parse_args()

    check_av()
    os.makedirs(args.out, exist_ok=True)
    os.makedirs(args.model_dir, exist_ok=True)

    if model_cached(args.model_dir, args.model):
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        print("[model] cached, offline mode")
    else:
        os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
        os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
        print("[model] downloading %s via hf-mirror" % args.model)

    from faster_whisper import WhisperModel

    threads = args.threads or (os.cpu_count() or 4)
    t0 = time.time()
    model = WhisperModel(args.model, device="cpu", compute_type="int8",
                         cpu_threads=threads, download_root=args.model_dir)
    print("[model] loaded in %.1fs" % (time.time() - t0))

    t1 = time.time()
    segments, info = model.transcribe(
        args.audio, language=args.lang, beam_size=args.beam, vad_filter=True,
        initial_prompt=args.prompt, condition_on_previous_text=False,
    )
    lines = []
    for seg in segments:
        start = int(seg.start)
        lines.append("[%d:%02d] %s" % (start // 60, start % 60, seg.text.strip()))

    path = os.path.join(args.out, "transcript.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    dur = getattr(info, "duration", None)
    print("[ok] %d segments, %.1fs elapsed, audio %.1fs -> %s"
          % (len(lines), time.time() - t1, dur or 0, path))
    print("[hint] read this file once; do not re-read it in chunks")


if __name__ == "__main__":
    main()
