import pytest

import tugyt.tugyt as app


class FakeDownloader:
    instances = []
    result = 0
    error = None

    def __init__(self, options):
        self.options = options
        self.urls = []
        self.__class__.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback):
        return False

    def download(self, urls):
        if self.error is not None:
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


def test_cli_parses_basic_arguments():
    args = app.create_parser().parse_args([
        "https://example.test/video",
        "--output", "downloads",
        "--format", "best",
    ])

    assert args.input == ["https://example.test/video"]
    assert args.output == "downloads"
    assert args.format == "best"


def test_main_executes_download_path_and_creates_output(tmp_path):
    output_folder = tmp_path / "downloads"
    args = app.create_parser().parse_args([
        "https://example.test/video",
        "--output", str(output_folder),
    ])
    FakeDownloader.result = 7

    assert app.main(args) == 7
    assert output_folder.is_dir()
    assert FakeDownloader.instances[0].urls == ["https://example.test/video"]


def test_cli_reports_user_error(capsys, monkeypatch):
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
