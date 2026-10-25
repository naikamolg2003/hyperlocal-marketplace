<#
.SYNOPSIS
    Convenience wrapper to start Docker environment.
#>
[CmdletBinding()]
param (
    [switch]$NoBuild,
    [string]$LogDir = "logs",
    [int]$TimeoutSeconds = 60
)

$ScriptPath = Join-Path $PSScriptRoot "scripts\start.ps1"
& $ScriptPath @PSBoundParameters
exit $LASTEXITCODE
