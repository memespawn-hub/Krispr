"""Local web UI: `yt4k-web`, then open http://127.0.0.1:8000."""

from __future__ import annotations

import argparse
import os
import threading
import uuid
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_file

from . import downloader

app = Flask(__name__)
OUTPUT_DIR = Path(os.environ.get("YT4K_OUTPUT", "downloads")).resolve()

_jobs: dict[str, dict] = {}
_lock = threading.Lock()


def _update(job_id: str, **fields) -> None:
    with _lock:
        _jobs[job_id].update(fields)


def _run(job_id: str, url: str, options: dict) -> None:
    def hook(d: dict) -> None:
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            pct = d.get("downloaded_bytes", 0) / total * 100 if total else 0
            _update(job_id, state="downloading", percent=round(pct, 1),
                    speed=(d.get("_speed_str") or "").strip(), eta=(d.get("_eta_str") or "").strip(),
                    stream=d.get("info_dict", {}).get("format_note") or "")
        elif d["status"] == "finished":
            _update(job_id, percent=100.0)
        elif d["status"] == "processing":
            _update(job_id, state="processing")

    try:
        files = downloader.download(url, output_dir=OUTPUT_DIR, progress_hook=hook, **options)
        _update(job_id, state="done", percent=100.0,
                files=[str(Path(f).resolve().relative_to(OUTPUT_DIR)) for f in files])
    except Exception as e:  # surface any failure to the UI
        _update(job_id, state="error", error=str(e))


@app.get("/")
def index():
    return render_template("index.html", presets=downloader.QUALITY_PRESETS,
                           containers=downloader.CONTAINERS, audio_formats=downloader.AUDIO_FORMATS,
                           ffmpeg=downloader.ffmpeg_available())


@app.post("/api/info")
def info():
    url = (request.json or {}).get("url", "").strip()
    if not url:
        return jsonify(error="Paste a YouTube link first."), 400
    try:
        v = downloader.fetch_info(url)
    except downloader.DownloadError as e:
        return jsonify(error=str(e)), 400
    return jsonify(title=v.title, uploader=v.uploader, duration=v.duration, thumbnail=v.thumbnail,
                   heights=v.heights, is_playlist=v.is_playlist, entry_count=v.entry_count)


@app.post("/api/download")
def start_download():
    body = request.json or {}
    url = body.get("url", "").strip()
    if not url:
        return jsonify(error="Missing URL."), 400
    options = {
        "quality": str(body.get("quality", "2160")),
        "container": body.get("container", "mp4"),
        "audio_format": body.get("audio_format", "m4a"),
        "playlist": bool(body.get("playlist")),
        "subtitles": bool(body.get("subtitles")),
    }
    try:
        downloader.build_options(**options)  # validate before starting a thread
    except ValueError as e:
        return jsonify(error=str(e)), 400

    job_id = uuid.uuid4().hex
    with _lock:
        _jobs[job_id] = {"state": "queued", "percent": 0.0, "files": [], "error": None}
    threading.Thread(target=_run, args=(job_id, url, options), daemon=True).start()
    return jsonify(id=job_id)


@app.get("/api/jobs/<job_id>")
def job_status(job_id: str):
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            abort(404)
        return jsonify(job)


@app.get("/files/<path:name>")
def get_file(name: str):
    path = (OUTPUT_DIR / name).resolve()
    if not path.is_relative_to(OUTPUT_DIR) or not path.is_file():
        abort(404)
    return send_file(path, as_attachment=True)


def main() -> None:
    p = argparse.ArgumentParser(prog="yt4k-web", description="Run the yt4k web UI.")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"yt4k running at http://{args.host}:{args.port}  (saving to {OUTPUT_DIR})")
    app.run(host=args.host, port=args.port, threaded=True)


if __name__ == "__main__":
    main()
