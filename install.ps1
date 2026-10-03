param(
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"

$repository = "ftnick/tugyt"
$installDirectory = Join-Path $env:LOCALAPPDATA "Programs\tugyt"
$executablePath = Join-Path $installDirectory "tugyt.exe"

function Get-TugytPipPython {
    foreach ($candidate in @("python", "python3", "py")) {
        if (-not (Get-Command $candidate -ErrorAction SilentlyContinue)) {
            continue
        }
        & $candidate -m pip show tugyt *> $null
        if ($LASTEXITCODE -eq 0) {
            return $candidate
        }
    }
    return $null
}

if ($Uninstall) {
    $pathComparer = { $_.TrimEnd([char[]]@('\')) -ine $installDirectory.TrimEnd([char[]]@('\')) }
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $originalUserPathEntries = @($userPath -split ";" | Where-Object { $_ })
    $userPathEntries = @($originalUserPathEntries | Where-Object $pathComparer)
    $hasUserPathEntry = $userPathEntries.Count -ne $originalUserPathEntries.Count
    if (-not (Test-Path -LiteralPath $executablePath) -and -not $hasUserPathEntry) {
        $pipPython = Get-TugytPipPython
        if ($pipPython) {
            Write-Output "No standalone tugyt installation was found. A pip installation exists. Remove it with: $pipPython -m pip uninstall tugyt"
        }
        else {
            $existingCommand = Get-Command tugyt -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($existingCommand) {
                Write-Output "No installation managed by this installer was found. An existing command is at: $($existingCommand.Source)"
            }
            else {
                Write-Output "tugyt is not installed."
            }
        }
        return
    }

    if (Test-Path -LiteralPath $executablePath) {
        Remove-Item -LiteralPath $executablePath -Force
    }
    if ($hasUserPathEntry) {
        [Environment]::SetEnvironmentVariable("Path", ($userPathEntries -join ";"), "User")
    }
    $env:Path = (@($env:Path -split ";" | Where-Object { $_ } | Where-Object $pathComparer) -join ";")

    if ((Test-Path -LiteralPath $installDirectory) -and -not (Get-ChildItem -LiteralPath $installDirectory -Force | Select-Object -First 1)) {
        Remove-Item -LiteralPath $installDirectory -Force
    }
    Write-Output "Uninstalled tugyt and removed its PATH entry. Restart your terminal to apply the change."
    $pipPython = Get-TugytPipPython
    if ($pipPython) {
        Write-Output "A separate pip installation remains. Remove it with: $pipPython -m pip uninstall tugyt"
    }
    return
}

$pipPython = Get-TugytPipPython
if ($pipPython) {
    if (Test-Path -LiteralPath $executablePath) {
        Write-Output "tugyt is already installed via pip and as a standalone binary. No changes made."
    }
    else {
        Write-Output "tugyt is already installed via pip. No standalone binary was installed."
    }
    Write-Output "To uninstall the pip version, run: $pipPython -m pip uninstall tugyt"
    return
}

if (Test-Path -LiteralPath $executablePath) {
    Write-Output "tugyt is already installed at $executablePath. No changes made."
    return
}

$existingCommand = Get-Command tugyt -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
if ($existingCommand -and $existingCommand.Source -ine $executablePath) {
    Write-Output "tugyt is already available at $($existingCommand.Source). No changes made."
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

    $downloadedExecutablePath = Join-Path $temporaryDirectory "tugyt.exe"
    if (-not (Test-Path -LiteralPath $downloadedExecutablePath -PathType Leaf)) {
        throw "The release archive did not contain the expected tugyt.exe executable."
    }

    New-Item -ItemType Directory -Path $installDirectory -Force | Out-Null
    Copy-Item -LiteralPath $downloadedExecutablePath -Destination $executablePath -Force
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