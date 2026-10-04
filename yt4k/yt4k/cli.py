"""Command-line interface: `yt4k URL [URL ...]`."""

from __future__ import annotations

import argparse
import sys

from . import downloader


def _progress(d: dict) -> None:
    if d["status"] == "downloading":
        pct = d.get("_percent_str", "").strip()
        speed = d.get("_speed_str", "").strip()
        eta = d.get("_eta_str", "").strip()
        sys.stderr.write(f"\r  {pct:>7}  {speed:>12}  ETA {eta:<8}")
        sys.stderr.flush()
    elif d["status"] == "finished":
        sys.stderr.write("\r  100.0%  downloaded, merging...            \n")
    elif d["status"] == "processing":
        sys.stderr.write(f"  post-processing ({d.get('postprocessor', '')})\n")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="yt4k",
        description="Download YouTube videos in up to 4K/8K quality (free, uses yt-dlp + ffmpeg).",
    )
    p.add_argument("urls", nargs="+", help="video or playlist URL(s)")
    p.add_argument("-q", "--quality", default="2160", choices=list(downloader.QUALITY_PRESETS),
                   help="max resolution, or 'audio' for audio only (default: 2160 = 4K)")
    p.add_argument("-o", "--output", default="downloads", help="output directory (default: ./downloads)")
    p.add_argument("-f", "--format", dest="container", default="mp4", choices=downloader.CONTAINERS,
                   help="video container (default: mp4)")
    p.add_argument("-a", "--audio-format", default="m4a", choices=downloader.AUDIO_FORMATS,
                   help="audio format when --quality audio (default: m4a)")
    p.add_argument("-p", "--playlist", action="store_true", help="download the whole playlist")
    p.add_argument("-s", "--subs", action="store_true", help="embed English subtitles when available")
    p.add_argument("-i", "--info", action="store_true", help="only show available resolutions")
    args = p.parse_args(argv)

    failed = 0
    for url in args.urls:
        try:
            info = downloader.fetch_info(url)
            if info.is_playlist:
                print(f"Playlist: {info.title} ({info.entry_count} videos)")
            else:
                best = f"{info.max_height}p" if info.max_height else "unknown"
                print(f"{info.title}  [best available: {best}]")
                if args.info:
                    print("  resolutions:", ", ".join(f"{h}p" for h in info.heights))
            if args.info:
                continue
            files = downloader.download(
                url,
                quality=args.quality,
                output_dir=args.output,
                container=args.container,
                audio_format=args.audio_format,
                playlist=args.playlist,
                subtitles=args.subs,
                progress_hook=_progress,
            )
            for f in files:
                print(f"  saved: {f}")
        except (downloader.DownloadError, ValueError) as e:
            failed += 1
            print(f"  error: {e}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
