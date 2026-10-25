<#
.SYNOPSIS
    Convenience wrapper to stop Docker environment.
#>
[CmdletBinding()]
param (
    [switch]$Volumes,
    [int]$TimeoutSeconds = 15,
    [string]$LogDir = "logs"
)

$ScriptPath = Join-Path $PSScriptRoot "scripts\stop.ps1"
& $ScriptPath @PSBoundParameters
exit $LASTEXITCODE
