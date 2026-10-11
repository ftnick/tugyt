<p align="center">
  <img src="https://raw.githubusercontent.com/ftnick/tugyt/refs/heads/main/icon.ico" width="160">
</p>
<p align="center">
  <sub>Fetch (icon) by <a href="https://thenounproject.com/browse/icons/term/fetch/" target="_blank" title="highlight Icons">Gregor Cresnar</a> from <a href="https://thenounproject.com/browse/icons/term/fetch/" target="_blank" title="highlight Icons">Noun Project</a> (CC BY 3.0)</sub>
</p>

<h1 align="center">tugyt</h1>

<p align="center">
    is a lightweight command-line YouTube downloader powered by <a href="https://github.com/yt-dlp/yt-dlp" target="_blank">yt-dlp</a>, with support for videos, playlists, audio extraction, subtitles, metadata, and download archives.
</p>

<p align="center">
  <a href="https://github.com/ftnick/tugyt/actions/workflows/python-package.yml"><img src="https://github.com/ftnick/tugyt/actions/workflows/python-package.yml/badge.svg" alt="CI"></a>
</p>

<p align="center">
  <a href="https://github.com/ftnick/tugyt/blob/main/LICENSE"><img src="https://img.shields.io/github/license/ftnick/tugyt" alt="License"></a>
  <a href="https://github.com/ftnick/tugyt/commits/main"><img src="https://img.shields.io/github/last-commit/ftnick/tugyt" alt="Last commit"></a>
</p>

## Install

Install the latest standalone release on macOS or Linux:

```sh
curl -fsSL https://raw.githubusercontent.com/ftnick/tugyt/main/install.sh | sh
```

On Windows, run this in PowerShell:

```powershell
irm https://raw.githubusercontent.com/ftnick/tugyt/main/install.ps1 | iex
```

Restart the terminal after installation, then run `tugyt --help`.

## Examples

Download a single video to the current folder:

```sh
tugyt "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

Download to a specific folder:

```sh
tugyt --output ./downloads "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

Download a playlist, but only a subset of items:

```sh
tugyt --output ./downloads --playlist-start 2 --playlist-end 10 "https://www.youtube.com/playlist?list=PL..."
```

Extract audio as MP3:

```sh
tugyt --extract-audio --audio-format mp3 --audio-quality 192K "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

List available formats without downloading:

```sh
tugyt --list-formats "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

Read URLs from a text file (one URL per line):

```sh
echo "https://www.youtube.com/watch?v=dQw4w9WgXcQ" > urls.txt
tugyt urls.txt
```

## Uninstall

To uninstall on macOS or Linux:

```sh
curl -fsSL https://raw.githubusercontent.com/ftnick/tugyt/main/install.sh | sh -s -- --uninstall
```

On Windows, run:

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/ftnick/tugyt/main/install.ps1))) -Uninstall
```
