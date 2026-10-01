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

try:
    import pyfiglet
except ImportError:  # pragma: no cover
    pyfiglet = None

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
    def __init__(self, message: str, logged: bool = False):
        super().__init__(message)
        self.logged = logged


def _remove_log_prefix(message: str, level: str) -> str:
    prefix = f"{level}:"
    while message.startswith(prefix):
        message = message[len(prefix):].lstrip()
    return message


class YtdlpLogger:
    def __init__(self, quiet: bool = False, verbose: bool = False):
        self.quiet = quiet
        self.verbose = verbose
        self.error_reported = False

    def debug(self, message: str) -> None:
        if message.startswith("[debug]"):
            logger.debug(message)
        elif not self.quiet:
            print(message)

    def info(self, message: str) -> None:
        if not self.quiet:
            print(message)

    def warning(self, message: str) -> None:
        logger.warning(_remove_log_prefix(message, "WARNING"))

    def error(self, message: str) -> None:
        self.error_reported = True
        message = _remove_log_prefix(message, "ERROR")
        if "\n" in message:
            if self.verbose:
                logger.debug("yt-dlp details:\n%s", message)
            return
        logger.error(message)


class DownloadProgress:
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
    return [".*" if language == "all" else language for language in value.split(",")]


def build_options(args: argparse.Namespace) -> dict:
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
        "logger": YtdlpLogger(args.quiet, args.verbose),
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
    parser.add_argument("--log-file", metavar="FILE", help="write warnings and debug details to FILE")
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


def _version_requested(arguments: Iterable[str]) -> bool:
    return any(
        argument in ("-v", "--version")
        or (argument.startswith("-") and not argument.startswith("--") and "v" in argument[1:])
        for argument in arguments
    )


def _print_banner(show_version: bool = True) -> None:
    if pyfiglet is not None:
        try:
            print(pyfiglet.figlet_format(MODULE_NAME, font="standard"), end="")
        except (OSError, UnicodeError):
            pass
    if show_version:
        print(__version__)


def _configure_logging(args: argparse.Namespace) -> None:
    handlers: List[logging.Handler] = [logging.StreamHandler()]
    if args.log_file:
        handlers.append(logging.FileHandler(args.log_file, encoding="utf-8"))
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
        handlers=handlers,
        force=True,
    )


def main(args: Optional[argparse.Namespace] = None) -> int:
    args = args or cmdl_parser.parse_args()
    if yt_dlp is None:
        raise DownloadError("yt-dlp is not installed. Run `python -m pip install yt-dlp`.") from _YT_DLP_IMPORT_ERROR
    urls = _read_inputs(args.input)
    if not urls:
        raise DownloadError("No URLs were found in the supplied input.")
    logger.debug("Starting download for %d input(s)", len(urls))
    yt_dlp_module: Any = yt_dlp
    options = build_options(args)
    download_logger = options["logger"]
    try:
        progress_context = nullcontext() if args.quiet else DownloadProgress()
        with progress_context as progress:
            if not args.quiet:
                assert progress is not None
                options["noprogress"] = True
                options["progress_hooks"] = [progress.update]
            with yt_dlp_module.YoutubeDL(options) as downloader:
                result = downloader.download(urls)
                logger.debug("Download completed with exit code %d", result)
                return result
    except yt_dlp_module.utils.DownloadError as error:
        message = _remove_log_prefix(str(error), "ERROR")
        if not download_logger.error_reported:
            logger.error(message)
        raise DownloadError(message, logged=True) from error


def execute(*args: str) -> int:
    return main(cmdl_parser.parse_args(list(args)))


def cli() -> None:
    arguments = sys.argv[1:]
    _print_banner(show_version=not _version_requested(arguments))
    args = cmdl_parser.parse_args()
    _configure_logging(args)
    try:
        raise SystemExit(main(args))
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        raise SystemExit(130)
    except DownloadError as error:
        if not error.logged:
            print(f"tugyt: {error}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    cli()
