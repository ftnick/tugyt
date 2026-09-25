# ytget

A YouTube video downloader built on [yt-dlp](https://github.com/yt-dlp/yt-dlp). It provides a small Python API and convenient defaults for video, playlist, audio, metadata, subtitle, and archive workflows.

## Requirements

- Python 3.9 or newer
- `yt-dlp`
- `ffmpeg` on `PATH`

## Installation

```bash
python -m pip install -r requirements.txt
python -m pip install .
```

## Usage

```bash
ytget https://www.youtube.com/watch?v=VIDEO_ID
ytget https://www.youtube.com/playlist?list=PLAYLIST_ID
```

The default output is `%(title)s [%(id)s].%(ext)s`. Templates use yt-dlp metadata fields:

```bash
ytget -o "downloads/%(uploader)s/%(title)s.%(ext)s" URL
```

Useful workflows:

```bash
ytget --no-playlist URL
ytget -F URL
ytget -f "bv*[height<=1080]+ba/b" URL
ytget -x --audio-format mp3 --audio-quality 192K URL
ytget --write-info-json --write-thumbnail --write-subs --sub-langs en URL
ytget --download-archive downloaded.txt urls.txt
```

`input` accepts URLs or text files. Text files contain one URL per line; blank lines and lines beginning with `#` are ignored. Format selectors and post-processing options follow yt-dlp's conventions. Run `ytget --help` for the complete option list.

## Python API

```python
import ytget

ytget.execute(
    "--no-playlist",
    "-o", "downloads/%(title)s.%(ext)s",
    "https://www.youtube.com/watch?v=VIDEO_ID",
)
```
