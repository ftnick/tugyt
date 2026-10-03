$ErrorActionPreference = "Stop"

$repository = "ftnick/tugyt"
$release = Invoke-RestMethod -Uri "https://api.github.com/repos/$repository/releases/latest" -Headers @{
    "User-Agent" = "tugyt-installer"
}
$archiveName = "tugyt-windows-latest-$($release.tag_name).zip"
$asset = $release.assets | Where-Object { $_.name -eq $archiveName } | Select-Object -First 1
if ($null -eq $asset) {
    throw "The latest release does not contain the expected asset: $archiveName"
}

$temporaryDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ([System.Guid]::NewGuid().ToString())
$installDirectory = Join-Path $env:LOCALAPPDATA "Programs\tugyt"
try {
    New-Item -ItemType Directory -Path $temporaryDirectory -Force | Out-Null
    $archivePath = Join-Path $temporaryDirectory $archiveName
    Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $archivePath
    Expand-Archive -Path $archivePath -DestinationPath $temporaryDirectory -Force

    $executablePath = Join-Path $temporaryDirectory "tugyt.exe"
    if (-not (Test-Path -LiteralPath $executablePath -PathType Leaf)) {
        throw "The release archive did not contain the expected tugyt.exe executable."
    }

    New-Item -ItemType Directory -Path $installDirectory -Force | Out-Null
    Copy-Item -LiteralPath $executablePath -Destination (Join-Path $installDirectory "tugyt.exe") -Force
}
finally {
    Remove-Item -LiteralPath $temporaryDirectory -Recurse -Force -ErrorAction SilentlyContinue
}

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$pathEntries = @($userPath -split ";" | Where-Object { $_ })
if (-not ($pathEntries | Where-Object { $_.TrimEnd("\") -ieq $installDirectory.TrimEnd("\") })) {
    $updatedPath = (@($pathEntries) + $installDirectory) -join ";"
    [Environment]::SetEnvironmentVariable("Path", $updatedPath, "User")
}
if (($env:Path -split ";") -notcontains $installDirectory) {
    $env:Path = "$installDirectory;$env:Path"
}

Write-Output "Installed tugyt $($release.tag_name) to $installDirectory"
Write-Output "Restart your terminal, then run: tugyt --help"