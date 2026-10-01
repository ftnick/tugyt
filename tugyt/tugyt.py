"""Command-line YouTube downloader powered by yt-dlp."""

import argparse
import logging
import sys
from contextlib import nullcontext
from pathlib import Path
from typing import Any, Iterable, List, Optional

from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

_YT_DLP_IMPORT_ERROR: Optional[ImportError] = None

try:
    import yt_dlp
except ImportError as error:  # pragma: no cover
    yt_dlp = None
    _YT_DLP_IMPORT_ERROR = error

__version__ = "0.2.4"
__author__ = "ftnick"
__license__ = "MIT"

MODULE_NAME = "tugyt"
DEFAULT_OUTPUT = "%(title)s [%(id)s].%(ext)s"
logger = logging.getLogger(MODULE_NAME)


class DownloadError(Exception):
    """Raised when yt-dlp cannot complete a requested operation."""


class YtdlpLogger:
    """Bridge yt-dlp messages into the standard logger and CLI output."""

    def __init__(self, quiet: bool = False):
        self.quiet = quiet

    def debug(self, message: str) -> None:
        if message.startswith("[debug]"):
            logger.debug(message)
        elif not self.quiet:
            print(message)

    def info(self, message: str) -> None:
        if not self.quiet:
            print(message)

    def warning(self, message: str) -> None:
        print(f"WARNING: {message}", file=sys.stderr)

    def error(self, message: str) -> None:
        print(f"ERROR: {message}", file=sys.stderr)


class DownloadProgress:
    """Render yt-dlp download events as a single Rich progress display."""

    def __init__(self):
        self.progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
        )
        self.tasks = {}

    def __enter__(self):
        self.progress.start()
        return self

    def __exit__(self, exception_type, exception, traceback):
        self.progress.stop()

    def update(self, status: dict) -> None:
        if status["status"] == "downloading":
            source_filename = status.get("filename", "download")
            filename = Path(source_filename).name
            task_id = self.tasks.get(source_filename)
            total = status.get("total_bytes") or status.get("total_bytes_estimate")
            if task_id is None:
                task_id = self.progress.add_task(filename, total=total)
                self.tasks[source_filename] = task_id
            self.progress.update(
                task_id,
                total=total,
                completed=status.get("downloaded_bytes", 0),
            )
        elif status["status"] == "finished":
            source_filename = status.get("filename", "download")
            task_id = self.tasks.get(source_filename)
            if task_id is not None:
                self.progress.update(task_id, completed=status.get("total_bytes"))


def _read_inputs(inputs: Iterable[str]) -> List[str]:
    """Expand text files into URLs while preserving command-line order."""
    expanded = []
    for value in inputs:
        path = Path(value).expanduser()
        if path.is_file():
            with path.open("r", encoding="utf-8") as input_file:
                expanded.extend(
                    line.strip() for line in input_file
                    if line.strip() and not line.lstrip().startswith("#")
                )
        elif path.exists():
            raise DownloadError(f"Input path is not a file: {path}")
        else:
            expanded.append(value)
    return expanded


def _add_optional(options: dict, key: str, value: Any) -> None:
    if value is not None:
        options[key] = value


def _normalize_subtitle_languages(value: str) -> List[str]:
    """Convert yt-dlp's CLI all-languages alias to its API regex form."""
    return [".*" if language == "all" else language for language in value.split(",")]


def build_options(args: argparse.Namespace) -> dict:
    """Translate CLI arguments into yt-dlp options."""
    options = {
        "format": args.format,
        "outtmpl": args.output,
        "noplaylist": args.no_playlist,
        "quiet": args.quiet,
        "no_warnings": args.quiet,
        "ignoreerrors": args.ignore_errors,
        "continuedl": not args.no_continue,
        "retries": args.retries,
        "fragment_retries": args.retries,
        "concurrent_fragment_downloads": args.concurrent_fragments,
        "logger": YtdlpLogger(args.quiet),
        "writethumbnail": args.write_thumbnail,
        "writeinfojson": args.write_info_json,
        "writedescription": args.write_description,
        "writesubtitles": args.write_subs,
        "writeautomaticsub": args.write_auto_subs,
        "embedmetadata": args.embed_metadata,
        "embedthumbnail": args.embed_thumbnail,
        "embedsubtitles": args.embed_subs,
        "listformats": args.list_formats,
        "dump_single_json": args.dump_json,
        "skip_download": args.skip_download,
        "playliststart": args.playlist_start,
        "playlistend": args.playlist_end,
        "playlist_items": args.playlist_items,
        "flat_playlist": args.flat_playlist,
        "keepvideo": args.keep_video,
    }
    _add_optional(options, "proxy", args.proxy)
    _add_optional(options, "ratelimit", args.rate_limit)
    _add_optional(options, "download_archive", args.download_archive)
    _add_optional(options, "remote_components", args.remote_components)
    _add_optional(options, "subtitleslangs", _normalize_subtitle_languages(args.sub_langs))
    _add_optional(options, "subtitlesformat", args.sub_format)
    if args.extract_audio:
        options["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": args.audio_format,
            "preferredquality": args.audio_quality,
        }]
    if args.sponsorblock_remove:
        options["sponsorblock_remove"] = args.sponsorblock_remove
    if args.user_agent:
        options["http_headers"] = {"User-Agent": args.user_agent}
    if args.verbose:
        options["verbose"] = True
    return options


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=MODULE_NAME,
        description="Download YouTube videos, playlists, channels, and audio with yt-dlp.",
    )
    parser.add_argument("input", nargs="+", help="YouTube URLs or text files containing URLs")
    parser.add_argument("-v", "--version", action="version", version=__version__)
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument("-q", "--quiet", action="store_true", help="suppress yt-dlp output")
    output_group.add_argument("--verbose", action="store_true", help="show yt-dlp debug output")
    parser.add_argument("-k", "--keep-video", action="store_true",
                        help="keep the original downloaded fragments after merging")
    parser.add_argument("--ignore-errors", action="store_true", help="continue when an item fails")
    parser.add_argument("--no-continue", action="store_true", help="restart partial downloads")
    parser.add_argument("-o", "--output", "--output-path", default=DEFAULT_OUTPUT,
                        help="output template (default: %%(title)s [%%(id)s].%%(ext)s)")
    parser.add_argument("-f", "--format", default="bv*+ba/b",
                        help="yt-dlp format selector (default: bv*+ba/b)")
    parser.add_argument("-x", "--extract-audio", action="store_true", help="extract audio with ffmpeg")
    parser.add_argument(
        "--audio-format",
        choices=("best", "aac", "flac", "mp3", "m4a", "opus", "vorbis", "wav"),
        default="mp3",
    )
    parser.add_argument("--audio-quality", default="192K", help="audio bitrate passed to ffmpeg")
    parser.add_argument("-F", "--list-formats", action="store_true", help="list available formats without downloading")
    parser.add_argument("--dump-json", action="store_true", help="print metadata as JSON")
    parser.add_argument("--skip-download", action="store_true", help="process metadata without downloading media")
    parser.add_argument("--write-thumbnail", action="store_true", help="save the video thumbnail")
    parser.add_argument("--write-info-json", action="store_true", help="save metadata beside the media")
    parser.add_argument("--write-description", action="store_true", help="save the video description")
    parser.add_argument("--write-subs", action="store_true", help="download manually created subtitles")
    parser.add_argument("--write-auto-subs", action="store_true", help="download automatic subtitles")
    parser.add_argument("--sub-langs", default="en.*,ja.*,all", help="subtitle languages")
    parser.add_argument("--sub-format", default="best", help="subtitle format")
    parser.add_argument("--embed-metadata", action="store_true", help="embed metadata in the media")
    parser.add_argument("--embed-thumbnail", action="store_true", help="embed the thumbnail in the media")
    parser.add_argument("--embed-subs", action="store_true", help="embed downloaded subtitles")
    parser.add_argument("--no-playlist", action="store_true", help="download only the supplied video")
    parser.add_argument("--flat-playlist", action="store_true", help="do not resolve playlist entries")
    parser.add_argument("--playlist-start", type=int, metavar="N", help="playlist item to start at")
    parser.add_argument("--playlist-end", type=int, metavar="N", help="playlist item to stop at")
    parser.add_argument("--playlist-items", metavar="ITEMS", help="playlist items, e.g. 1,3,5-7")
    parser.add_argument("--download-archive", metavar="FILE", help="skip IDs already recorded in FILE")
    parser.add_argument(
        "--remote-components",
        action="append",
        choices=("ejs:github", "ejs:npm"),
        help="download yt-dlp components such as the YouTube challenge solver",
    )
    parser.add_argument("--sponsorblock-remove", metavar="CATEGORIES",
                        help="remove SponsorBlock categories, e.g. sponsor,intro")
    parser.add_argument("-y", "--proxy", help="HTTP/SOCKS proxy URL")
    parser.add_argument("--user-agent", help="custom HTTP User-Agent")
    parser.add_argument("--concurrent-fragments", type=int, default=1, metavar="N",
                        help="number of fragments to download concurrently")
    parser.add_argument("--retries", type=int, default=10, metavar="N", help="retry count")
    parser.add_argument("--rate-limit", type=int, metavar="BYTES",
                        help="maximum download rate in bytes per second")
    return parser


cmdl_parser = create_parser()


def main(args: Optional[argparse.Namespace] = None) -> int:
    """Download all supplied URLs and return a process exit code."""
    args = args or cmdl_parser.parse_args()
    if yt_dlp is None:
        raise DownloadError("yt-dlp is not installed. Run `python -m pip install yt-dlp`.") from _YT_DLP_IMPORT_ERROR
    urls = _read_inputs(args.input)
    if not urls:
        raise DownloadError("No URLs were found in the supplied input.")
    yt_dlp_module: Any = yt_dlp
    try:
        progress_context = nullcontext() if args.quiet else DownloadProgress()
        with progress_context as progress:
            options = build_options(args)
            if not args.quiet:
                assert progress is not None
                options["noprogress"] = True
                options["progress_hooks"] = [progress.update]
            with yt_dlp_module.YoutubeDL(options) as downloader:
                return downloader.download(urls)
    except yt_dlp_module.utils.DownloadError as error:
        raise DownloadError(str(error)) from error


def execute(*args: str) -> int:
    """Programmatic entrypoint compatible with the original package."""
    return main(cmdl_parser.parse_args(list(args)))


def cli() -> None:
    """Console-script entrypoint."""
    logging.basicConfig(level=logging.DEBUG if "--verbose" in sys.argv else logging.INFO)
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        raise SystemExit(130)
    except DownloadError as error:
        print(f"tugyt: {error}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    cli()
