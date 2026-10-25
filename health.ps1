<#
.SYNOPSIS
    Convenience wrapper to check Docker container health and server metrics.
#>
[CmdletBinding()]
param (
    [string]$LogDir = "logs"
)

$ScriptPath = Join-Path $PSScriptRoot "scripts\health.ps1"
& $ScriptPath @PSBoundParameters
exit $LASTEXITCODE
