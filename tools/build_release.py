"""Build the Windows release zip of The Quest II.

    python tools/build_release.py phase4          ->  dist/TheQuestII-phase4.zip
    python tools/build_release.py phase4 --play   ->  dist/TheQuestII-phase4-play.zip

The zip holds one folder, TheQuestII/, with the game, the original's data (TheQuest.zip, data/,
sprites/), the docs and the level editor. With --play it holds only what the game needs to run:
run_quest2.py, quest2/, sprites/ and TheQuest.zip (data/ is left out: its level files are the
ones in TheQuest.zip, and the game makes data/ when it first saves). Double-clicking "Play The Quest II.bat" finds Python (or
offers to install it with winget), sets up pygame-ce from the bundled wheels the first time, and
starts the game. The wheels are downloaded from PyPI once and cached in build/wheels/.
"""
from __future__ import annotations

import os
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WHEELS = os.path.join(ROOT, 'build', 'wheels')
PYGAME = 'pygame-ce==2.5.8'
PY_VERSIONS = ('3.12', '3.13')         # 3.12 is what the launcher installs; others download on first run
TOP = 'TheQuestII'

FILES = ['run_quest2.py', 'TheQuest.zip', 'README.md', 'requirements.txt', 'level_editor.py', 'icon.ico']
DIRS = ['quest2', 'data', 'sprites', 'docs']
PLAY_FILES = ['run_quest2.py', 'TheQuest.zip']
PLAY_DIRS = ['quest2', 'sprites']

README = """THE QUEST II
============

To play: double-click "Play The Quest II.bat".

The first time, it looks for Python 3.10 or newer. If Python isn't installed, it offers to install
Python 3.12 for you (with winget, which comes with Windows 10 and 11). Then it sets up pygame-ce
in the .deps folder here. After that the game starts straight away.

Keys (as in the original):
  arrows          move, attack, open doors, talk        Enter      pick up
  1-8             drink a potion                        Space/Tab  shoot / choose a target
  s               spell book                            F1-F9      cast a bound spell
  i               inventory                             c          character sheet
  k               killer switch                         v / Home   save
  l / Insert      load                                  Esc        quit to the title

Sound: PC-speaker tones like the original. To turn them off, create sound.txt in this folder
containing 0.

Saves are the original's own files, data\\save01.dat to save20.dat, so saves from the original
The Quest load here too (copy them into the data folder). The game reads the original's data
from TheQuest.zip and data/.
{extra}"""


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


def build(name: str, notes: str = '', play: bool = False) -> str:
    out = os.path.join(ROOT, 'dist', f'TheQuestII-{name}{"-play" if play else ""}.zip')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in PLAY_FILES if play else FILES:
            if os.path.exists(os.path.join(ROOT, f)):
                z.write(os.path.join(ROOT, f), f'{TOP}/{f}')
        for d in PLAY_DIRS if play else DIRS:
            for base, subdirs, files in os.walk(os.path.join(ROOT, d)):
                subdirs[:] = [s for s in subdirs if s != '__pycache__']
                for f in files:
                    if f.endswith('.pyc'):
                        continue
                    p = os.path.join(base, f)
                    z.write(p, f'{TOP}/{os.path.relpath(p, ROOT)}'.replace(os.sep, '/'))
        z.writestr(f'{TOP}/Play The Quest II.bat', crlf(os.path.join(ROOT, 'windows', 'Play The Quest II.bat')))
        extra = f'\nWhat is new in this build:\n{notes}\n' if notes else ''
        z.writestr(f'{TOP}/READ ME FIRST.txt', README.format(extra=extra).replace('\n', '\r\n'))
        for w in wheels():
            z.write(w, f'{TOP}/windows/wheels/{os.path.basename(w)}', compress_type=zipfile.ZIP_STORED)
    return out


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if a != '--play']
    if not args:
        sys.exit(__doc__)
    notes_file = args[1] if len(args) > 1 else None
    notes = open(notes_file, encoding='utf-8').read() if notes_file else ''
    path = build(args[0], notes, play='--play' in sys.argv)
    print(f'{path}  ({os.path.getsize(path) / 1e6:.1f} MB)')
