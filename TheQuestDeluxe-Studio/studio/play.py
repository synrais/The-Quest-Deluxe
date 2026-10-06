"""Test play: starts the game in its own window from the open quest."""
from __future__ import annotations

import os
import subprocess
import sys

from core import proc, side_save
from engine.pack import ROOT

from . import ui


def launch(app, level=None, at=None, from_start=False):
    """Save, then run the game: at a level's start, on a square (at=(x, y)), or from the title (from_start)."""
    s = app.session
    s.autosave()
    if s.status == 'error':
        app.say('Could not save, so the game would play the old version: ' + s.last_error, 'bad')
        return
    cls = 1
    try:
        cls = int(app.hero_pick.get().split()[0])
    except (ValueError, IndexError):
        pass
    cmd = [sys.executable, os.path.join(ROOT, 'run_deluxe.py'), '--pack', s.project.root]
    if not from_start:
        cmd += ['--quick', str(cls), '--level', str(level or 1)]
        if at:
            cmd += ['--at', f'{at[0]},{at[1]}']
    log_dir = side_save.home_dir()
    os.makedirs(log_dir, exist_ok=True)
    app.play_log = os.path.join(log_dir, 'play_log.txt')
    with open(app.play_log, 'w', encoding='utf-8') as log:
        log.write(' '.join(cmd) + '\n\n')
        log.flush()
        app.player = subprocess.Popen(cmd, cwd=ROOT, env=game_env(), stdout=log, stderr=subprocess.STDOUT, **proc.quiet())
    app.say('Starting the game… (its window can open behind this one)')
    app.root.after(3500, lambda: _check(app))


def _check(app):
    """A few seconds on: if the game has already crashed, say why (a game that was closed, or ended, is nothing to report)."""
    proc = getattr(app, 'player', None)
    code = proc.poll() if proc else None
    if code is None or code <= 0:
        return
    try:
        with open(app.play_log, encoding='utf-8', errors='replace') as fh:
            text = fh.read().strip().splitlines()
    except OSError:
        text = []
    why = '\n'.join(text[-8:]) if text else 'it wrote nothing'
    ui.inform(app.root, 'The game stopped', f'The game closed straight away (code {code}). What it said last:\n\n{why}\n\n'
              f'The whole log is {app.play_log}')


def game_env() -> dict:
    """The environment the test game runs in. The Studio sets SDL_VIDEODRIVER=dummy for itself (it only draws pictures off
    screen, studio/art.py), and a game started from it would inherit that and run with no window at all. The game gets the
    real video and sound drivers."""
    env = dict(os.environ)
    for name in ('SDL_VIDEODRIVER', 'SDL_AUDIODRIVER'):
        if env.get(name) == 'dummy':
            del env[name]
    return env
