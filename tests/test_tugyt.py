import logging
from pathlib import Path
from typing import Optional

import pytest

import tugyt.tugyt as app


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


class FakeProgress:
    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback):
        return False

    def update(self, status):
        pass


@pytest.fixture(autouse=True)
def reset_fakes(monkeypatch):
    FakeDownloader.instances = []
    FakeDownloader.result = 0
    FakeDownloader.error = None
    monkeypatch.setattr(app, "yt_dlp", FakeYtdlp)
    monkeypatch.setattr(app, "DownloadProgress", FakeProgress)


def test_parser_defaults_and_supported_options():
    args = app.create_parser().parse_args([
        "https://example.test/video",
        "--output", "downloads",
        "--format", "best",
        "--extract-audio",
        "--audio-format", "opus",
        "--playlist-start", "2",
    ])

    assert args.input == ["https://example.test/video"]
    assert args.output == "downloads"
    assert args.format == "best"
    assert args.extract_audio is True
    assert args.audio_format == "opus"
    assert args.playlist_start == 2


def test_parser_rejects_conflicting_output_modes():
    with pytest.raises(SystemExit):
        app.create_parser().parse_args([
            "https://example.test/video",
            "--quiet",
            "--verbose",
        ])


def test_read_inputs_expands_file_lines_and_preserves_order(tmp_path):
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


def test_build_options_translates_core_download_settings():
    args = app.create_parser().parse_args([
        "https://example.test/video",
        "--output", "downloads",
        "--format", "best",
        "--extract-audio",
        "--audio-format", "opus",
        "--audio-quality", "128K",
        "--no-continue",
        "--playlist-items", "2,4-6",
        "--sub-langs", "en,all",
        "--sub-format", "vtt",
        "--proxy", "http://proxy.test:8080",
    ])

    options = app.build_options(args)

    assert options["format"] == "best"
    assert options["merge_output_format"] == "mp4"
    assert options["outtmpl"] == str(Path("downloads") / app.DEFAULT_OUTPUT)
    assert options["continuedl"] is False
    assert options["playlist_items"] == "2,4-6"
    assert options["subtitleslangs"] == ["en", ".*"]
    assert options["subtitlesformat"] == "vtt"
    assert options["proxy"] == "http://proxy.test:8080"
    assert options["postprocessors"] == [{
        "key": "FFmpegExtractAudio",
        "preferredcodec": "opus",
        "preferredquality": "128K",
    }]


def test_main_downloads_expanded_inputs_and_creates_output(tmp_path):
    input_file = tmp_path / "urls.txt"
    input_file.write_text("https://example.test/video\n", encoding="utf-8")
    output_folder = tmp_path / "downloads"
    args = app.create_parser().parse_args([
        str(input_file),
        "--output", str(output_folder),
    ])
    FakeDownloader.result = 7

    assert app.main(args) == 7
    assert output_folder.is_dir()

    downloader = FakeDownloader.instances[0]
    assert downloader.urls == ["https://example.test/video"]
    assert downloader.options["outtmpl"] == str(output_folder / app.DEFAULT_OUTPUT)
    assert downloader.options["progress_hooks"]


def test_main_does_not_enable_progress_in_quiet_mode():
    args = app.create_parser().parse_args([
        "https://example.test/video",
        "--quiet",
    ])

    assert app.main(args) == 0
    assert "progress_hooks" not in FakeDownloader.instances[0].options


def test_main_translates_downloader_errors():
    FakeDownloader.error = FakeYtdlp.utils.DownloadError
    args = app.create_parser().parse_args(["https://example.test/video"])

    with pytest.raises(app.DownloadError, match="download failed") as error:
        app.main(args)

    assert error.value.logged is True


def test_cli_reports_user_errors(capsys, monkeypatch):
    def fail_main(args=None):
        raise app.DownloadError("bad input")

    monkeypatch.setattr(app, "main", fail_main)
    monkeypatch.setattr(
        app.cmdl_parser,
        "parse_args",
        lambda: app.create_parser().parse_args(["https://example.test/video"]),
    )

    with pytest.raises(SystemExit) as error:
        app.cli()

    assert error.value.code == 1
    assert capsys.readouterr().err == "tugyt: bad input\n"


def test_logging_writes_verbose_details(tmp_path):
    log_file = tmp_path / "tugyt.log"
    args = app.create_parser().parse_args([
        "https://example.test/video",
        "--verbose",
        "--log-file", str(log_file),
    ])

    app._configure_logging(args)
    app.logger.debug("debug details")
    logging.shutdown()

    assert "DEBUG: debug details" in log_file.read_text(encoding="utf-8")
