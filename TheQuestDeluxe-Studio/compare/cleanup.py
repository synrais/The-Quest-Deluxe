"""Ending what an earlier comparison left running: its DOSBox (started with a scratch folder named quest_dos_...) and its compare program (run_compare.py).

A program that is still running keeps its files in use, which on Windows is why a folder cannot be deleted afterwards. This is run before every comparison,
from the Studio's "Close leftovers" button, and by hand:   python -m compare.cleanup"""
from __future__ import annotations

import os
import subprocess
import sys

WINDOWS = sys.platform.startswith('win')


def stop_leftovers() -> list:
    """Stop every leftover compare program and DOSBox of ours (never this process); the list of what was stopped, as text."""
    return _stop_windows() if WINDOWS else _stop_posix()


def _stop_posix() -> list:
    import signal
    me = {os.getpid(), os.getppid()}
    out = []
    for pid in (int(p) for p in os.listdir('/proc') if p.isdigit()):
        if pid in me:
            continue
        try:
            with open(f'/proc/{pid}/cmdline', 'rb') as fh:
                cmd = fh.read().replace(b'\0', b' ').decode('utf-8', 'replace')
        except OSError:
            continue
        if ('run_compare.py' in cmd and 'cleanup' not in cmd) or ('quest_dos_' in cmd and 'dosbox' in cmd.lower()):
            try:
                os.kill(pid, signal.SIGKILL)
                out.append(f'{pid}: {cmd.strip()[:90]}')
            except OSError:
                pass
    return out


def _stop_windows() -> list:
    from core import proc
    script = (f"$me = $PID; $mine = {os.getpid()}; $parent = {os.getppid()}; Get-CimInstance Win32_Process | Where-Object "
              "{ $_.ProcessId -ne $me -and $_.ProcessId -ne $mine -and $_.ProcessId -ne $parent -and $_.CommandLine -and "
              "($_.CommandLine -match 'quest_dos_|run_compar[e]\\.py') -and $_.CommandLine -notmatch 'Get-CimInstance' } | "
              "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; \"$($_.ProcessId): $($_.Name)\" }")
    try:
        r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', script], capture_output=True, text=True, timeout=60, **proc.quiet())
    except (OSError, subprocess.SubprocessError):
        return []
    return [line.strip() for line in r.stdout.splitlines() if line.strip()]


if __name__ == '__main__':
    stopped = stop_leftovers()
    print('\n'.join(stopped) if stopped else 'Nothing was left running.')
