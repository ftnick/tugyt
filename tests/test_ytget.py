from typing import Optional

import pytest

import ytget.ytget as app


class FakeProgress:
    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback):
        return False

    def update(self, status):
        pass


class FakeDownloader:
    instances = []
    result = 0
    error: Optional[type[Exception]] = None

    def __init__(self, options):
        self.options = options
        self.__class__.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback):
        return False

    def download(self, urls):
        if self.error:
            raise self.error("download failed")
        self.urls = urls
        return self.result


class FakeYtdlp:
    class utils:
        class DownloadError(Exception):
            pass

    YoutubeDL = FakeDownloader


@pytest.fixture(autouse=True)
def reset_fake_downloader(monkeypatch):
    FakeDownloader.instances = []
    FakeDownloader.result = 0
    FakeDownloader.error = None
    monkeypatch.setattr(app, "yt_dlp", FakeYtdlp)
    monkeypatch.setattr(app, "DownloadProgress", FakeProgress)


def test_parser_defaults_and_input():
    args = app.create_parser().parse_args(["https://www.youtube.com/watch?v=example"])

    assert args.input == ["https://www.youtube.com/watch?v=example"]
    assert args.output == app.DEFAULT_OUTPUT
    assert args.format == "bv*+ba/b"
    assert args.retries == 10


def test_read_inputs_expands_files_and_preserves_order(tmp_path):
    input_file = tmp_path / "urls.txt"
    input_file.write_text(
        "# ignored\nhttps://example.test/one\n\n https://example.test/two \n",
        encoding="utf-8",
    )

    assert app._read_inputs(["https://example.test/direct", str(input_file)]) == [
        "https://example.test/direct",
        "https://example.test/one",
        "https://example.test/two",
    ]


def test_normalize_subtitle_languages_expands_all_alias():
    assert app._normalize_subtitle_languages("en.*,all,ja") == ["en.*", ".*", "ja"]


def test_build_options_translates_all_optional_flags():
    args = app.create_parser().parse_args([
        "https://www.youtube.com/watch?v=example",
        "--quiet",
        "--verbose",
        "--keep-video",
        "--ignore-errors",
        "--no-continue",
        "--output",
        "%(id)s.%(ext)s",
        "--format",
        "best",
        "--extract-audio",
        "--audio-format",
        "opus",
        "--audio-quality",
        "128K",
        "--list-formats",
        "--dump-json",
        "--skip-download",
        "--write-thumbnail",
        "--write-info-json",
        "--write-description",
        "--write-subs",
        "--write-auto-subs",
        "--embed-metadata",
        "--embed-thumbnail",
        "--embed-subs",
        "--no-playlist",
        "--flat-playlist",
        "--playlist-start",
        "2",
        "--playlist-end",
        "8",
        "--playlist-items",
        "2,4-6",
        "--download-archive",
        "archive.txt",
        "--sponsorblock-remove",
        "sponsor,intro",
        "--proxy",
        "http://proxy.test:8080",
        "--user-agent",
        "test-agent",
        "--concurrent-fragments",
        "4",
        "--retries",
        "3",
        "--rate-limit",
        "1000",
        "--sub-langs",
        "en,all",
        "--sub-format",
        "vtt",
    ])

    options = app.build_options(args)

    assert options["format"] == "best"
    assert options["outtmpl"] == "%(id)s.%(ext)s"
    assert options["quiet"] is True
    assert options["no_warnings"] is True
    assert options["continuedl"] is False
    assert options["concurrent_fragment_downloads"] == 4
    assert options["subtitleslangs"] == ["en", ".*"]
    assert options["subtitlesformat"] == "vtt"
    assert options["postprocessors"] == [{
        "key": "FFmpegExtractAudio",
        "preferredcodec": "opus",
        "preferredquality": "128K",
    }]
    assert options["http_headers"] == {"User-Agent": "test-agent"}
    assert options["proxy"] == "http://proxy.test:8080"
    assert options["verbose"] is True


def test_main_downloads_expanded_inputs_and_adds_progress_hook(tmp_path):
    input_file = tmp_path / "urls.txt"
    input_file.write_text("https://example.test/video\n", encoding="utf-8")
    args = app.create_parser().parse_args([str(input_file)])
    FakeDownloader.result = 7

    assert app.main(args) == 7

    downloader = FakeDownloader.instances[0]
    assert downloader.urls == ["https://example.test/video"]
    assert downloader.options["noprogress"] is True
    assert len(downloader.options["progress_hooks"]) == 1


def test_main_quiet_mode_does_not_register_progress_hook():
    args = app.create_parser().parse_args(["https://example.test/video", "--quiet"])

    assert app.main(args) == 0

    options = FakeDownloader.instances[0].options
    assert "noprogress" not in options
    assert "progress_hooks" not in options


def test_main_translates_downloader_error():
    FakeDownloader.error = FakeYtdlp.utils.DownloadError
    args = app.create_parser().parse_args(["https://example.test/video"])

    with pytest.raises(app.DownloadError, match="download failed"):
        app.main(args)


def test_main_rejects_missing_dependency(monkeypatch):
    monkeypatch.setattr(app, "yt_dlp", None)
    args = app.create_parser().parse_args(["https://example.test/video"])

    with pytest.raises(app.DownloadError, match="yt-dlp is not installed"):
        app.main(args)


def test_main_rejects_input_file_without_urls(tmp_path):
    input_file = tmp_path / "empty.txt"
    input_file.write_text("# no URLs\n\n", encoding="utf-8")
    args = app.create_parser().parse_args([str(input_file)])

    with pytest.raises(app.DownloadError, match="No URLs were found"):
        app.main(args)


def test_execute_passes_parsed_arguments_to_main(monkeypatch):
    captured = {}

    def fake_main(args):
        captured["args"] = args
        return 4

    monkeypatch.setattr(app, "main", fake_main)

    assert app.execute("https://example.test/video", "--quiet") == 4
    assert captured["args"].input == ["https://example.test/video"]
    assert captured["args"].quiet is True


def test_logger_respects_quiet_mode(capsys):
    logger = app.YtdlpLogger(quiet=True)

    logger.debug("ordinary message")
    logger.info("info message")
    logger.warning("warning message")
    logger.error("error message")

    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == "WARNING: warning message\nERROR: error message\n"


def test_cli_reports_download_errors(monkeypatch, capsys):
    def fail_main():
        raise app.DownloadError("bad input")

    monkeypatch.setattr(app, "main", fail_main)

    with pytest.raises(SystemExit) as error:
        app.cli()

    assert error.value.code == 1
    assert capsys.readouterr().err.endswith("ytget: bad input\n")
