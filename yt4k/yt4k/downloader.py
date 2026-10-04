"""Core download logic built on yt-dlp + ffmpeg.

YouTube serves anything above 1080p as separate video-only (VP9/AV1) and
audio-only streams, so a "4K download" means picking the best video stream
up to the requested height, the best audio stream, and merging them with
ffmpeg. yt-dlp does the heavy lifting; this module just picks good defaults.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import yt_dlp

QUALITY_PRESETS = {
    "4320": "8K (4320p)",
    "2160": "4K (2160p)",
    "1440": "2K (1440p)",
    "1080": "Full HD (1080p)",
    "720": "HD (720p)",
    "audio": "Audio only",
}

CONTAINERS = ("mp4", "mkv", "webm")
AUDIO_FORMATS = ("m4a", "mp3", "opus", "flac")

ProgressHook = Callable[[dict], None]


class DownloadError(Exception):
    pass


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _js_runtimes() -> dict:
    # Recent YouTube changes require a JavaScript runtime to unlock the full
    # format list (including 4K). Enable every runtime we can find.
    found = {name: {} for name in ("deno", "node", "bun") if shutil.which(name)}
    return found or {"deno": {}}


def _base_opts() -> dict:
    return {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "js_runtimes": _js_runtimes(),
        "retries": 10,
        "fragment_retries": 10,
        "concurrent_fragment_downloads": 4,
    }


@dataclass
class VideoInfo:
    id: str
    title: str
    uploader: str | None
    duration: int | None
    thumbnail: str | None
    heights: list[int] = field(default_factory=list)
    is_playlist: bool = False
    entry_count: int = 0

    @property
    def max_height(self) -> int | None:
        return max(self.heights) if self.heights else None


def fetch_info(url: str) -> VideoInfo:
    """Look up a video (or playlist) without downloading it."""
    opts = _base_opts() | {"skip_download": True, "extract_flat": "in_playlist"}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as e:
        raise DownloadError(str(e)) from e

    if info.get("_type") == "playlist":
        entries = list(info.get("entries") or [])
        return VideoInfo(
            id=info.get("id", ""),
            title=info.get("title") or "Playlist",
            uploader=info.get("uploader"),
            duration=None,
            thumbnail=(info.get("thumbnails") or [{}])[-1].get("url"),
            is_playlist=True,
            entry_count=len(entries),
        )

    heights = sorted(
        {f["height"] for f in info.get("formats") or [] if f.get("height") and f.get("vcodec") != "none"},
        reverse=True,
    )
    return VideoInfo(
        id=info.get("id", ""),
        title=info.get("title") or "video",
        uploader=info.get("uploader"),
        duration=info.get("duration"),
        thumbnail=info.get("thumbnail"),
        heights=heights,
    )


def build_options(
    quality: str = "2160",
    output_dir: str | Path = "downloads",
    container: str = "mp4",
    audio_format: str = "m4a",
    playlist: bool = False,
    subtitles: bool = False,
    progress_hook: ProgressHook | None = None,
) -> dict:
    """Translate user choices into yt-dlp options."""
    output_dir = Path(output_dir).expanduser()
    template = "%(playlist_title)s/%(playlist_index)03d - %(title)s [%(id)s].%(ext)s" if playlist \
        else "%(title)s [%(id)s].%(ext)s"

    if quality == "audio":
        # Separate folder: extracting audio deletes the intermediate file, which
        # would otherwise share a name with an earlier video download.
        template = "audio/" + template

    opts = _base_opts() | {
        "outtmpl": str(output_dir / template),
        "noplaylist": not playlist,
        "windowsfilenames": True,
        "postprocessors": [],
    }

    if quality == "audio":
        if audio_format not in AUDIO_FORMATS:
            raise ValueError(f"audio format must be one of {AUDIO_FORMATS}")
        opts["format"] = "ba/b"
        opts["postprocessors"].append({
            "key": "FFmpegExtractAudio",
            "preferredcodec": audio_format,
            "preferredquality": "0",
        })
    else:
        if quality not in QUALITY_PRESETS:
            raise ValueError(f"quality must be one of {list(QUALITY_PRESETS)}")
        if container not in CONTAINERS:
            raise ValueError(f"container must be one of {CONTAINERS}")
        height = int(quality)
        # Best video up to the requested height + best audio, falling back to
        # the best single file. Sorting prefers resolution, then frame rate,
        # then HDR, then bitrate, so 4K60 HDR wins over 4K30 SDR.
        opts["format"] = "bv*+ba/b"
        opts["format_sort"] = [f"res:{height}", "fps", "hdr:12", "vbr", "abr"]
        opts["merge_output_format"] = container
        if container == "mp4":
            # AAC audio plays everywhere; YouTube's Opus audio in MP4 doesn't.
            opts["postprocessor_args"] = {"merger": ["-c:a", "aac", "-b:a", "320k"]}

    if subtitles:
        opts |= {"writesubtitles": True, "subtitleslangs": ["en.*", "-live_chat"]}
        opts["postprocessors"].append({"key": "FFmpegEmbedSubtitle"})

    opts["postprocessors"].append({"key": "FFmpegMetadata", "add_metadata": True})

    if progress_hook:
        opts["progress_hooks"] = [progress_hook]
        opts["postprocessor_hooks"] = [lambda d: progress_hook({**d, "status": "processing"})
                                       if d.get("status") == "started" else None]
    return opts


def download(url: str, **kwargs) -> list[str]:
    """Download `url` and return the paths of the finished files."""
    if not ffmpeg_available():
        raise DownloadError("ffmpeg is required to merge 4K video and audio. Install it and try again.")

    finished: list[str] = []
    opts = build_options(**kwargs)
    opts["post_hooks"] = [finished.append]
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            code = ydl.download([url])
    except yt_dlp.utils.DownloadError as e:
        raise DownloadError(str(e)) from e
    if code:
        raise DownloadError("Download did not complete; see the log above.")
    return finished
