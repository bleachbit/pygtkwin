#Requires -Version 7.4
# Write the versions of the main components as a Markdown table, for the
# release notes and the job summary. Run it after build-vcpkg.ps1.
# Usage: ./write-versions.ps1 -Triplet x64-windows -Out versions.md

param(
    [Parameter(Mandatory)]
    [string]$Triplet,
    [Parameter(Mandatory)]
    [string]$Out
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true

$installed = & (Join-Path $PSScriptRoot 'vcpkg/vcpkg') list --x-json | ConvertFrom-Json -AsHashtable

$requirement = Get-Content (Join-Path $PSScriptRoot 'requirements-pygobject.txt') -Raw
if ($requirement -notmatch '(?mi)^pygobject==(\S+)') {
    throw 'No pygobject pin in requirements-pygobject.txt'
}
$pygobjectVersion = $Matches[1]

# PyGObject is the only one not built by vcpkg
$components = [ordered]@{
    Python     = 'python3'
    GTK        = 'gtk3'
    PyGObject  = $null
    Cairo      = 'cairo'
    Pango      = 'pango'
    Fontconfig = 'fontconfig'
    HarfBuzz   = 'harfbuzz'
}

$lines = @(
    '## Versions'
    ''
    '| Component | Version |'
    '| --- | --- |'
)
foreach ($name in $components.Keys) {
    $port = $components[$name]
    if ($port) {
        $package = $installed["${port}:$Triplet"]
        if (-not $package) {
            throw "$port is not installed for $Triplet"
        }
        $version = $package.version
    }
    else {
        $version = $pygobjectVersion
    }
    $lines += "| $name | $version |"
}
Set-Content -LiteralPath $Out -Value $lines
