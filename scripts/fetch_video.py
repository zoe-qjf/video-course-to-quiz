#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Fetch a video: metadata + audio + optional low-res video + subtitles.

Usage:
    python fetch_video.py <url> --out <dir> [--video] [--langs zh-Hans,zh]

Writes:
    <out>/meta.json       metadata (title, duration, chapters, subtitle langs, description...)
    <out>/audio.m4a       audio track (always)
    <out>/video.mp4       low-res video (only with --video), used for frame sampling
    <out>/subs.<lang>.vtt subtitles (only when the video actually has them)

Proxy handling: tries every proxy found in env / common local ports (7890 etc.)
and finally a direct connection, keeping the first one that answers.
"""
import argparse
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def proxy_candidates():
    seen, out = set(), []

    def add(v):
        if v and v not in seen:
            seen.add(v)
            out.append(v)

    for k in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"):
        add(os.environ.get(k))
    for p in (
        "http://127.0.0.1:7890", "http://127.0.0.1:7891", "http://127.0.0.1:7897",
        "http://127.0.0.1:10809", "http://127.0.0.1:1080", "http://127.0.0.1:8889",
    ):
        add(p)
    out.append(None)  # direct
    return out


def pick_proxy(ydl_mod, url):
    """Return (proxy, info) for the first proxy that can reach the site."""
    last_err = None
    for proxy in proxy_candidates():
        opts = {
            "quiet": True, "no_warnings": True, "skip_download": True,
            "socket_timeout": 15, "extract_flat": False,
        }
        if proxy:
            opts["proxy"] = proxy
        try:
            with ydl_mod.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            label = proxy or "direct"
            print("[proxy] using %s" % label)
            return proxy, info
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            print("[proxy] %s failed: %s" % (proxy or "direct", str(exc)[:120]))
    raise SystemExit("all proxies failed, last error: %s" % last_err)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--out", required=True)
    ap.add_argument("--video", action="store_true", help="also download a <=480p video for frame sampling")
    ap.add_argument("--langs", default="zh-Hans,zh,zh-CN,en",
                    help="preferred subtitle languages, comma separated")
    args = ap.parse_args()

    try:
        import yt_dlp
    except ImportError:
        raise SystemExit("yt-dlp missing. Install it into the venv first (see SKILL.md).")

    os.makedirs(args.out, exist_ok=True)
    proxy, info = pick_proxy(yt_dlp, args.url)

    subs = info.get("subtitles") or {}
    auto = info.get("automatic_captions") or {}
    meta = {
        "id": info.get("id"),
        "title": info.get("title"),
        "uploader": info.get("uploader") or info.get("channel"),
        "duration": info.get("duration"),
        "duration_hms": _hms(info.get("duration")),
        "upload_date": info.get("upload_date"),
        "view_count": info.get("view_count"),
        "webpage_url": info.get("webpage_url") or args.url,
        "description": (info.get("description") or "")[:4000],
        "chapters": info.get("chapters"),
        "subtitle_langs": sorted(subs.keys()),
        "auto_caption_langs": sorted(auto.keys()),
        "proxy": proxy or "direct",
    }
    with open(os.path.join(args.out, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)

    print("[meta] %s | %s | %s" % (meta["title"], meta["uploader"], meta["duration_hms"]))
    if subs:
        print("[subs] found: %s" % ", ".join(meta["subtitle_langs"]))
    else:
        print("[subs] none (no CC). ASR will be required.")

    base = {"quiet": True, "no_warnings": True, "socket_timeout": 30, "retries": 3}
    if proxy:
        base["proxy"] = proxy

    # audio
    audio_opts = dict(base, format="bestaudio[ext=m4a]/bestaudio",
                      outtmpl=os.path.join(args.out, "audio.%(ext)s"))
    with yt_dlp.YoutubeDL(audio_opts) as ydl:
        ydl.download([args.url])
    print("[audio] done")

    # subtitles (if any)
    if subs:
        langs = [x.strip() for x in args.langs.split(",") if x.strip()]
        want = [x for x in langs if x in subs] or list(subs.keys())[:1]
        sub_opts = dict(base, skip_download=True, writesubtitles=True,
                        subtitleslangs=want, subtitlesformat="vtt",
                        outtmpl=os.path.join(args.out, "subs.%(ext)s"))
        with yt_dlp.YoutubeDL(sub_opts) as ydl:
            ydl.download([args.url])
        print("[subs] downloaded: %s" % ", ".join(want))

    # low-res video
    if args.video:
        vid_opts = dict(base, format="18/bv*[height<=480][ext=mp4]/bv*[height<=480]",
                        outtmpl=os.path.join(args.out, "video.%(ext)s"))
        with yt_dlp.YoutubeDL(vid_opts) as ydl:
            ydl.download([args.url])
        print("[video] done")

    print("[ok] out=%s" % os.path.abspath(args.out))


def _hms(seconds):
    if not seconds:
        return "?"
    seconds = int(seconds)
    return "%d:%02d:%02d" % (seconds // 3600, seconds % 3600 // 60, seconds % 60)


if __name__ == "__main__":
    main()
