# Stops every program that is running from this game folder (or from the folder beside it): the Studio, the game, the compare program, DOSBox, whatever
# a crashed run left behind and which keeps files in use so that the folders cannot be deleted. Nothing else is touched.
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here
$all = Get-CimInstance Win32_Process

# this script, and the programs that started it (the command window), are left alone
$keep = @{}
$id = $PID
while ($id -and -not $keep.ContainsKey($id)) {
    $keep[$id] = $true
    $p = $all | Where-Object { $_.ProcessId -eq $id } | Select-Object -First 1
    $id = if ($p) { $p.ParentProcessId } else { 0 }
}

$stopped = @()
foreach ($p in $all) {
    if ($keep.ContainsKey([int]$p.ProcessId)) { continue }
    if ($p.Name -eq 'explorer.exe') { continue }
    $text = "$($p.ExecutablePath) $($p.CommandLine)"
    $mine = $text.IndexOf($here, [StringComparison]::OrdinalIgnoreCase) -ge 0 -or
            $text.IndexOf($root, [StringComparison]::OrdinalIgnoreCase) -ge 0 -or
            $text -match 'quest_dos_'
    if ($mine) {
        try {
            Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop
            $stopped += "$($p.ProcessId)  $($p.Name)"
        } catch {
            Write-Host "Could not stop $($p.ProcessId) $($p.Name): $($_.Exception.Message)"
        }
    }
}
Start-Sleep -Seconds 2
if ($stopped.Count) {
    Write-Host 'Stopped:'
    $stopped | ForEach-Object { Write-Host "  $_" }
} else {
    Write-Host 'Nothing from this folder was running.'
}
Write-Host ''
Write-Host 'Now the folders can be deleted. (If one still will not go: close any File Explorer window open inside it, then try again.)'
