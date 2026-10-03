param(
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"

$repository = "ftnick/tugyt"
$installDirectory = Join-Path $env:LOCALAPPDATA "Programs\tugyt"
if ($Uninstall) {
    $executablePath = Join-Path $installDirectory "tugyt.exe"
    if (Test-Path -LiteralPath $executablePath) {
        Remove-Item -LiteralPath $executablePath -Force
    }

    $pathComparer = { $_.TrimEnd([char[]]@('\')) -ine $installDirectory.TrimEnd([char[]]@('\')) }
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $originalUserPathEntries = @($userPath -split ";" | Where-Object { $_ })
    $userPathEntries = @($originalUserPathEntries | Where-Object $pathComparer)
    if ($userPathEntries.Count -ne $originalUserPathEntries.Count) {
        [Environment]::SetEnvironmentVariable("Path", ($userPathEntries -join ";"), "User")
    }
    $env:Path = (@($env:Path -split ";" | Where-Object { $_ } | Where-Object $pathComparer) -join ";")

    if ((Test-Path -LiteralPath $installDirectory) -and -not (Get-ChildItem -LiteralPath $installDirectory -Force | Select-Object -First 1)) {
        Remove-Item -LiteralPath $installDirectory -Force
    }
    Write-Output "Uninstalled tugyt and removed its PATH entry. Restart your terminal to apply the change."
    return
}

$release = Invoke-RestMethod -Uri "https://api.github.com/repos/$repository/releases/latest" -Headers @{
    "User-Agent" = "tugyt-installer"
}
$archiveName = "tugyt-windows-latest-$($release.tag_name).zip"
$asset = $release.assets | Where-Object { $_.name -eq $archiveName } | Select-Object -First 1
if ($null -eq $asset) {
    throw "The latest release does not contain the expected asset: $archiveName"
}

$temporaryDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ([System.Guid]::NewGuid().ToString())
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
if (-not ($pathEntries | Where-Object { $_.TrimEnd([char[]]@('\')) -ieq $installDirectory.TrimEnd([char[]]@('\')) })) {
    $updatedPath = (@($pathEntries) + $installDirectory) -join ";"
    [Environment]::SetEnvironmentVariable("Path", $updatedPath, "User")
}
if (($env:Path -split ";") -notcontains $installDirectory) {
    $env:Path = "$installDirectory;$env:Path"
}

Write-Output "Installed tugyt $($release.tag_name) to $installDirectory"
Write-Output "Restart your terminal, then run: tugyt --help"