<#
.SYNOPSIS
    Convenience wrapper to run setup & replication wizard.
#>
[CmdletBinding()]
param (
    [switch]$Repair,
    [switch]$ResetData,
    [switch]$NoCache,
    [switch]$Force,
    [string]$LogDir = "logs",
    [int]$TimeoutSeconds = 60
)

$ScriptPath = Join-Path $PSScriptRoot "scripts\setup.ps1"
& $ScriptPath @PSBoundParameters
exit $LASTEXITCODE
