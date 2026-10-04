# yt4k: free 4K YouTube downloader

A free, open, self-hosted YouTube downloader that grabs videos in their **highest available quality (4K, 8K, HDR, 60fps)** with the best audio track, merged into one file. It runs on your own computer, so there are no ads, no sign-up, and no limits.

It has two interfaces:

- **Web UI**: paste a link, pick a quality, click Download
- **CLI**: `yt4k <url>`

Under the hood it uses [yt-dlp](https://github.com/yt-dlp/yt-dlp) to fetch streams and [ffmpeg](https://ffmpeg.org) to merge them.

## Why you need ffmpeg

YouTube only serves 1080p and below as a single file. Anything higher (1440p, 4K, 8K) comes as a separate video-only stream (VP9 or AV1) plus an audio-only stream. yt4k downloads the best of each and uses ffmpeg to merge them **without re-encoding the video**, so you get the original quality.

## Install

1. Install **Python 3.10+** and **ffmpeg**:
   - macOS: `brew install python ffmpeg`
   - Windows: `winget install Python.Python.3.12 Gyan.FFmpeg`
   - Ubuntu/Debian: `sudo apt install python3 python3-venv ffmpeg`
2. *(Recommended)* Install a JavaScript runtime. YouTube now needs one to unlock its full format list, including 4K. yt4k auto-detects [Deno](https://deno.com) (`brew install deno` / `winget install DenoLand.Deno`), Node.js or Bun.
3. Install yt4k:

```bash
cd yt4k
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .
```

## Use the web UI

```bash
yt4k-web
```

Open <http://127.0.0.1:8000>, paste a YouTube link, and click **Get video**. A badge shows the best quality available (4K, 8K, and so on). Pick your options and click **Download**. Files are saved to `./downloads` (set `YT4K_OUTPUT=/some/folder` to change this) and can also be saved from the browser.

## Use the CLI

```bash
yt4k "https://www.youtube.com/watch?v=VIDEO_ID"              # best quality up to 4K, as MP4
yt4k -q 4320 URL                                              # allow up to 8K
yt4k -q 1440 -f mkv URL                                       # cap at 1440p, MKV container
yt4k -q audio -a mp3 URL                                      # audio only, MP3 (saved to downloads/audio/)
yt4k -p "https://www.youtube.com/playlist?list=LIST_ID"       # whole playlist
yt4k -s URL                                                   # embed English subtitles
yt4k -i URL                                                   # list available resolutions only
yt4k -o ~/Videos URL1 URL2                                    # several videos, custom folder
```

| Option | Default | Meaning |
|---|---|---|
| `-q, --quality` | `2160` | Max height: `4320`, `2160`, `1440`, `1080`, `720`, or `audio` |
| `-f, --format` | `mp4` | Video container: `mp4`, `mkv`, `webm` |
| `-a, --audio-format` | `m4a` | For `-q audio`: `m4a`, `mp3`, `opus`, `flac` |
| `-o, --output` | `downloads` | Output folder |
| `-p, --playlist` | off | Download the whole playlist |
| `-s, --subs` | off | Embed English subtitles |
| `-i, --info` | off | Only show available resolutions |

## How quality is chosen

yt4k asks for the best video at or below your chosen height, ranked by **resolution → frame rate → HDR → bitrate**, plus the best audio. When a video tops out at 1080p, you get 1080p; it never upscales.

**MP4 vs MKV:** In MP4 mode the audio is converted to 320 kbps AAC so the file plays everywhere, including QuickTime, iPhone and Windows' built-in player. The video is never re-encoded. If you want the untouched original Opus audio, choose `mkv`. Note that YouTube 4K video is VP9 or AV1, which some older players and devices can't decode. VLC and mpv play everything.

## Troubleshooting

- **Only 1080p or lower shows up:** install Deno (see Install, step 2) and update yt-dlp with `pip install -U "yt-dlp[default]"`. YouTube changes often, and an up-to-date yt-dlp fixes most problems.
- **"Sign in to confirm you're not a bot":** you're being rate-limited. Wait a while, or pass browser cookies by running yt-dlp directly with `--cookies-from-browser`.
- **"ffmpeg is required":** install ffmpeg and make sure `ffmpeg -version` works in your terminal.

## Legal

yt4k is for downloading videos you own, videos with a permissive license (for example Creative Commons), or videos you otherwise have permission to save. Downloading copyrighted content without permission may break YouTube's Terms of Service and copyright law where you live. Please respect creators.

The web UI listens on `127.0.0.1` only by default. Don't expose it to the public internet.
