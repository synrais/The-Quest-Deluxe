"""Build the Windows release zips: one for each edition, each standing on its own.

    python tools/build_release.py 7            ->  dist/TheQuest-Classic-7.zip   (the faithful port)
                                                   dist/QuestDeluxe-7.zip         (engine, editor, packs, docs)
    python tools/build_release.py 7 --play     ->  dist/TheQuest-Classic-7.zip
                                                   dist/QuestDeluxe-7-play.zip    (engine and packs only)
    python tools/build_release.py 7 notes.txt  ->  the same, with "what is new" in each READ ME FIRST.txt
    --classic / --deluxe                           only that edition

Each zip holds one folder: TheQuest-Classic/ (run_quest2.py, quest2/, sprites/, TheQuest.zip) or
QuestDeluxe/ (run_deluxe.py, deluxe/, packs/, and in the full zip run_editor.py, editor/, docs/).
Quest Deluxe needs nothing of the classic edition. Double-clicking a launcher finds Python (or
offers to install it with winget), sets up pygame-ce from the bundled wheels the first time, and
starts the program. The wheels are downloaded from PyPI once and cached in build/wheels/.
"""
from __future__ import annotations

import os
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WHEELS = os.path.join(ROOT, 'build', 'wheels')
TEMPLATE = os.path.join(ROOT, 'tools', 'launcher.bat')
PYGAME = 'pygame-ce==2.5.8'
PY_VERSIONS = ('3.12', '3.13')         # 3.12 is what the launcher installs; others download on first run

# edition: (source folder, zip folder, files, dirs, files and dirs of the full zip only, launchers)
EDITIONS = {
    'classic': ('classic', 'TheQuest-Classic', ['run_quest2.py', 'TheQuest.zip'], ['quest2', 'sprites'], [], {
        'Play The Quest.bat': ('The Quest', 'run_quest2.py', False)}),
    'deluxe': ('deluxe', 'QuestDeluxe', ['run_deluxe.py'], ['deluxe', 'packs'], ['run_editor.py', 'editor', 'docs'], {
        'Play Quest Deluxe.bat': ('Quest Deluxe', 'run_deluxe.py', False),
        'Quest Editor.bat': ('Quest Editor', 'run_editor.py', True)}),
}
TK_CHECK = '''%PY% -c "import tkinter" >nul 2>&1
if errorlevel 1 (
    echo The editor needs tkinter, which this Python doesn't have.
    echo Reinstall Python from https://www.python.org/downloads/ with "tcl/tk and IDLE" ticked.
    pause
    exit /b 1
)
'''

KEYS = """Keys (as in the original):
  arrows          move, attack, open doors, talk        Enter      pick up
  1-8             drink a potion                        Space/Tab  shoot / choose a target
  s               spell book                            F1-F9      cast a bound spell
  i               inventory                             c          character sheet
  k               killer switch                         v / Home   save
  l / Insert      load                                  Esc        quit to the title"""

SETUP = """The first time, it looks for Python 3.10 or newer. If Python isn't installed, it offers to install
Python 3.12 for you (with winget, which comes with Windows 10 and 11). Then it sets up pygame-ce
in the .deps folder here. After that it starts straight away."""

README = {
    'classic': f"""THE QUEST (CLASSIC)
===================

The original game, remade exactly: double-click "Play The Quest.bat".

{SETUP}

{KEYS}

Sound: PC-speaker tones like the original. To turn them off, create sound.txt in this folder
containing 0.

Saves are the original's own files, data\\save01.dat to save20.dat, so saves from the original
The Quest load here too (copy them into the data folder). The game reads the original's data
from TheQuest.zip.
{{extra}}""",
    'deluxe': f"""QUEST DELUXE
============

To play: double-click "Play Quest Deluxe.bat". It plays a quest pack; packs\\quest1 is the original
quest, converted, and it plays the same as the original.
To make quests (full zip): double-click "Quest Editor.bat" - see docs\\QUEST_PACKS.md.

{SETUP}

{KEYS}

Quest Deluxe adds:
  F               FPS mode: the world through the hero's eyes. Up/Down walk, Left/Right turn,
                  Q/E or , and . step sideways, M shows or hides the map in the corner
  D               the combat log: who hit whom for how much, what you pick up, locked doors

Sound: PC-speaker tones like the original. To turn them off, create sound.txt in this folder
containing 0. Saves: saves\\<pack>\\save01.dat to save20.dat.
{{extra}}""",
}


def launcher(title: str, program: str, tk: bool) -> bytes:
    text = crlf(TEMPLATE).decode()
    text = text.replace('title The Quest II', f'title {title}').replace('The Quest II', title)
    run = '%PY% run_quest2.py %*'
    assert run in text
    text = text.replace(run, (TK_CHECK.replace('\n', '\r\n') if tk else '') + f'%PY% {program} %*')
    return text.encode()


def wheels() -> list[str]:
    os.makedirs(WHEELS, exist_ok=True)
    for v in PY_VERSIONS:
        tag = 'cp' + v.replace('.', '')
        if not any(f'-{tag}-' in f for f in os.listdir(WHEELS)):
            subprocess.check_call([sys.executable, '-m', 'pip', 'download', PYGAME, '--platform', 'win_amd64',
                                   '--python-version', v, '--only-binary=:all:', '--no-deps', '-d', WHEELS, '-q'])
    return sorted(os.path.join(WHEELS, f) for f in os.listdir(WHEELS)
                  if f.endswith('.whl') and any(f'-cp{v.replace(".", "")}-' in f for v in PY_VERSIONS))


def crlf(path: str) -> bytes:
    with open(path, 'rb') as fh:
        return fh.read().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')


def build(edition: str, name: str, notes: str = '', play: bool = False) -> str:
    src, top, files, dirs, full, launchers = EDITIONS[edition]
    src = os.path.join(ROOT, src)
    trimmed = play and bool(full)
    if not play:
        files = files + [f for f in full if os.path.isfile(os.path.join(src, f))]
        dirs = dirs + [d for d in full if os.path.isdir(os.path.join(src, d))]
    out = os.path.join(ROOT, 'dist', f'{top}-{name}{"-play" if trimmed else ""}.zip')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(os.path.join(src, f), f'{top}/{f}')
        for d in dirs:
            for base, subdirs, names in os.walk(os.path.join(src, d)):
                subdirs[:] = [s for s in subdirs if s not in ('__pycache__', 'out')]
                for f in names:
                    if not f.endswith('.pyc'):
                        p = os.path.join(base, f)
                        z.write(p, f'{top}/{os.path.relpath(p, src)}'.replace(os.sep, '/'))
        for bat, (title, program, tk) in launchers.items():
            if program in files:
                z.writestr(f'{top}/{bat}', launcher(title, program, tk))
        extra = f'\nWhat is new in this build:\n{notes}\n' if notes else ''
        z.writestr(f'{top}/READ ME FIRST.txt', README[edition].format(extra=extra).replace('\n', '\r\n'))
        for w in wheels():
            z.write(w, f'{top}/windows/wheels/{os.path.basename(w)}', compress_type=zipfile.ZIP_STORED)
    return out


if __name__ == '__main__':
    flags = {a for a in sys.argv[1:] if a.startswith('--')}
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not args:
        sys.exit(__doc__)
    notes = open(args[1], encoding='utf-8').read() if len(args) > 1 else ''
    editions = [e for e in EDITIONS if f'--{e}' in flags] or list(EDITIONS)
    for e in editions:
        path = build(e, args[0], notes, play='--play' in flags)
        print(f'{path}  ({os.path.getsize(path) / 1e6:.1f} MB)')
