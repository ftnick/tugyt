import logging
from typing import Optional

import pytest

import tugyt.tugyt as app

RealDownloadProgress = app.DownloadProgress


class FakeProgress:
    entered = 0

    def __enter__(self):
        self.__class__.entered += 1
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


class RecordingProgress:
    def __init__(self, *columns):
        self.tasks = []

    def start(self):
        pass

    def stop(self):
        pass

    def add_task(self, description, total=None):
        self.tasks.append((description, total))
        return len(self.tasks) - 1

    def update(self, task_id, **kwargs):
        pass


@pytest.fixture(autouse=True)
def reset_fake_downloader(monkeypatch):
    FakeDownloader.instances = []
    FakeDownloader.result = 0
    FakeDownloader.error = None
    FakeProgress.entered = 0
    monkeypatch.setattr(app, "yt_dlp", FakeYtdlp)
    monkeypatch.setattr(app, "DownloadProgress", FakeProgress)


def test_parser_defaults_and_input():
    args = app.create_parser().parse_args(["https://www.youtube.com/watch?v=example"])

    assert args.input == ["https://www.youtube.com/watch?v=example"]
    assert args.output == app.DEFAULT_OUTPUT
    assert args.format == "bv*+ba/b"
    assert args.retries == 10


def test_print_banner_uses_pyfiglet_and_shows_version(monkeypatch, capsys):
    class FakeFiglet:
        @staticmethod
        def figlet_format(text, font):
            assert text == app.MODULE_NAME
            assert font == "standard"
            return "ASCII BANNER\n"

    monkeypatch.setattr(app, "pyfiglet", FakeFiglet)

    app._print_banner()

    assert capsys.readouterr().out == f"ASCII BANNER\n{app.__version__}\n"


def test_print_banner_falls_back_to_version(monkeypatch, capsys):
    monkeypatch.setattr(app, "pyfiglet", None)

    app._print_banner()

    assert capsys.readouterr().out == f"{app.__version__}\n"


def test_print_banner_falls_back_when_font_resources_fail(monkeypatch, capsys):
    class BrokenFiglet:
        @staticmethod
        def figlet_format(text, font):
            raise ModuleNotFoundError("pyfiglet.fonts")

    monkeypatch.setattr(app, "pyfiglet", BrokenFiglet)

    app._print_banner()

    assert capsys.readouterr().out == f"{app.__version__}\n"


def test_print_banner_avoids_duplicate_version_for_version_option(monkeypatch, capsys):
    class FakeFiglet:
        @staticmethod
        def figlet_format(text, font):
            return "ASCII BANNER\n"

    monkeypatch.setattr(app, "pyfiglet", FakeFiglet)

    app._print_banner(show_version=False)

    assert capsys.readouterr().out == "ASCII BANNER\n"


def test_version_requested_detects_short_option_cluster():
    assert app._version_requested(["-vq"]) is True


def test_parser_rejects_quiet_and_verbose_together():
    with pytest.raises(SystemExit):
        app.create_parser().parse_args([
            "https://www.youtube.com/watch?v=example",
            "--quiet",
            "--verbose",
        ])


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


def test_read_inputs_rejects_directories(tmp_path):
    input_directory = tmp_path / "urls"
    input_directory.mkdir()

    with pytest.raises(app.DownloadError, match="Input path is not a file"):
        app._read_inputs([str(input_directory)])


def test_normalize_subtitle_languages_expands_all_alias():
    assert app._normalize_subtitle_languages("en.*,all,ja") == ["en.*", ".*", "ja"]


def test_progress_tasks_distinguish_same_basename(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "Progress", RecordingProgress)
    progress = RealDownloadProgress()

    progress.update({
        "status": "downloading",
        "filename": str(tmp_path / "first" / "video.mp4"),
        "total_bytes": 10,
        "downloaded_bytes": 1,
    })
    progress.update({
        "status": "downloading",
        "filename": str(tmp_path / "second" / "video.mp4"),
        "total_bytes": 20,
        "downloaded_bytes": 2,
    })

    assert len(progress.tasks) == 2


def test_build_options_translates_all_optional_flags():
    args = app.create_parser().parse_args([
        "https://www.youtube.com/watch?v=example",
        "--quiet",
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
    assert options["restrictfilenames"] is True
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
    assert FakeProgress.entered == 0
    assert "noprogress" not in options
    assert "progress_hooks" not in options


def test_main_parses_fresh_arguments_for_each_call(monkeypatch):
    first_args = app.create_parser().parse_args(["https://example.test/first"])
    second_args = app.create_parser().parse_args(["https://example.test/second"])
    parsed_args = iter([first_args, second_args])
    monkeypatch.setattr(app.cmdl_parser, "parse_args", lambda: next(parsed_args))

    assert app.main() == 0
    assert app.main() == 0

    assert [instance.urls for instance in FakeDownloader.instances] == [
        ["https://example.test/first"],
        ["https://example.test/second"],
    ]


def test_main_translates_downloader_error():
    FakeDownloader.error = FakeYtdlp.utils.DownloadError
    args = app.create_parser().parse_args(["https://example.test/video"])

    with pytest.raises(app.DownloadError, match="download failed") as error:
        app.main(args)

    assert error.value.logged is True


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


def test_logger_respects_quiet_mode(capsys, caplog):
    caplog.set_level("DEBUG", logger=app.MODULE_NAME)
    logger = app.YtdlpLogger(quiet=True)

    logger.debug("ordinary message")
    logger.info("info message")
    logger.warning("WARNING: WARNING: warning message")
    logger.error("ERROR: ERROR: error message")

    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == ""
    assert [(record.levelname, record.message) for record in caplog.records] == [
        ("WARNING", "warning message"),
        ("ERROR", "error message"),
    ]


def test_logger_moves_traceback_details_to_verbose_logging(caplog):
    caplog.set_level("DEBUG", logger=app.MODULE_NAME)
    logger = app.YtdlpLogger(verbose=True)

    logger.error("ERROR: bad input\n  File \"example.py\", line 1")

    assert [(record.levelname, record.message) for record in caplog.records] == [
        ("DEBUG", 'yt-dlp details:\nbad input\n  File "example.py", line 1'),
    ]


def test_configure_logging_writes_file(tmp_path):
    log_file = tmp_path / "tugyt.log"
    args = app.create_parser().parse_args([
        "https://example.test/video",
        "--verbose",
        "--log-file",
        str(log_file),
    ])

    app._configure_logging(args)
    app.logger.debug("debug details")
    app.logger.warning("warning details")
    logging.shutdown()

    output = log_file.read_text(encoding="utf-8")
    assert "DEBUG: debug details" in output
    assert "WARNING: warning details" in output


def test_cli_reports_download_errors(monkeypatch, capsys):
    def fail_main(args=None):
        raise app.DownloadError("bad input")

    monkeypatch.setattr(app, "main", fail_main)
    monkeypatch.setattr(app, "pyfiglet", None)
    monkeypatch.setattr(
        app.cmdl_parser,
        "parse_args",
        lambda: app.create_parser().parse_args(["https://example.test/video"]),
    )

    with pytest.raises(SystemExit) as error:
        app.cli()

    assert error.value.code == 1
    output = capsys.readouterr()
    assert output.out == f"{app.__version__}\n"
    assert output.err.endswith("tugyt: bad input\n")
