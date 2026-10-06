"""Build the Windows release zips: one for each edition, each standing on its own.

    python tools/build_release.py 7            ->  dist/TheQuestClassic-7.zip    (the faithful port)
                                                   dist/TheQuestDeluxe-7.zip      (engine, editor, packs, docs)
    python tools/build_release.py 7 --play     ->  dist/TheQuestClassic-7.zip
                                                   dist/TheQuestDeluxe-7-play.zip (engine and packs only)
    python tools/build_release.py 7 notes.txt  ->  the same, with "what is new" in each READ ME FIRST.txt
    --classic / --deluxe                           only that edition
    python tools/build_release.py --launchers  ->  only (re)write the launchers in the edition folders

Each zip holds one folder: TheQuestClassic/ (run_quest2.py, engine/, sprites/, packs/TheQuest/, the
original as released) or TheQuestDeluxe/ (run_deluxe.py, engine/, packs/, and in the full zip
run_editor.py, editor/, docs/).
The Quest Deluxe needs nothing of the classic edition. The launchers ("Play The Quest.bat", "Play The Quest
Deluxe.bat", "The Quest Deluxe Editor.bat") live in the edition folders too, made from
tools/launcher.bat by write_launchers(), so a copy of the repository plays on Windows as well (without
the bundled wheels, the launcher downloads pygame-ce). Double-clicking a launcher finds Python (or
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
    'classic': ('TheQuestClassic', 'TheQuestClassic', ['run_quest2.py'], ['engine', 'sprites', 'packs'], [], {
        'Play The Quest.bat': ('The Quest', 'run_quest2.py', False)}),
    'deluxe': ('TheQuestDeluxe', 'TheQuestDeluxe', ['run_deluxe.py', 'settings.ini'], ['engine', 'packs'], ['run_editor.py', 'editor', 'docs'], {
        'Play The Quest Deluxe.bat': ('The Quest Deluxe', 'run_deluxe.py', False),
        'The Quest Deluxe Editor.bat': ('The Quest Deluxe Editor', 'run_editor.py', True)}),
    'studio': ('TheQuestDeluxe-Studio', 'TheQuestDeluxe-Studio', ['run_deluxe.py', 'settings.ini'], ['engine', 'packs'],
               ['run_studio.py', 'run_compare.py', 'Stop everything.bat', 'core', 'studio', 'compare', 'dos', 'docs', 'tools'], {
        'Play The Quest Deluxe.bat': ('The Quest Deluxe', 'run_deluxe.py', False),
        'The Quest Studio.bat': ('The Quest Studio', 'run_studio.py', True)}),
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

The original game is in packs\\TheQuest, as it was released (TheQuest.exe, data, bgi, the manual);
the port reads its files from there. Saves go where the original keeps them, in
packs\\TheQuest\\data (save01.dat to save20.dat, the original's own format), so saves from the
original The Quest load here too.
{{extra}}""",
    'deluxe': f"""THE QUEST DELUXE
============

To play: double-click "Play The Quest Deluxe.bat". It plays a quest pack; packs\\TheQuest is the original
quest, converted, and it plays the same as the original.
To make quests (full zip): double-click "The Quest Deluxe Editor.bat" - see docs\\QUEST_PACKS.md.

{SETUP}

{KEYS}

The Quest Deluxe adds:
  F               FPS mode: the world through the hero's eyes. Up/Down walk, Left/Right turn,
                  Q/E or , and . step sideways; the Map box shows this screen from
                  above, M switches it to the level map
  D               the combat log: who hit whom for how much, what you pick up, locked doors

settings.ini (open it in Notepad):
  fixes = on      the original's bugs are fixed (the title screen says "Bug fixes: on"); off keeps
                  them, exactly as the original plays; pack does what each quest pack says
  sound = on      PC-speaker tones like the original; off for none
  items_on_top = on   gold and items drawn over whoever stands on them; off as the original
  floating_numbers = off   on: FPS mode's damage and misses also rise off whoever took them
Saves: saves\\<pack>\\save01.dat to save20.dat.
{{extra}}""",
    'studio': f"""THE QUEST DELUXE AND THE QUEST STUDIO
====================================

To play: double-click "Play The Quest Deluxe.bat". To make quests (full zip): double-click
"The Quest Studio.bat" - see docs\\STUDIO.md. To compare the game with the original in DOSBox
(and record what differs for the brothers' questionnaire): docs\\COMPARE.md.

{SETUP}

{KEYS}

The Quest Deluxe adds FPS mode (F), the combat log (D) and more: see README.md.
Saves: saves\\<pack>\\save01.dat to save20.dat. Your quests are in Custom Maps.
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


def write_launchers() -> list[str]:
    """Each edition folder's double-click launchers, from tools/launcher.bat."""
    written = []
    for name, (src, _, _, _, _, launchers) in EDITIONS.items():
        if name == 'studio':
            continue                                  # its launchers are its own (they start without a terminal window)
        for bat, (title, program, tk) in launchers.items():
            path = os.path.join(ROOT, src, bat)
            with open(path, 'wb') as fh:
                fh.write(launcher(title, program, tk))
            written.append(path)
    return written


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
                    saved = f.lower().startswith(('save', 'trash')) and f.lower().endswith('.dat')
                    if not f.endswith('.pyc') and not saved:                # nobody's saves in a release
                        p = os.path.join(base, f)
                        z.write(p, f'{top}/{os.path.relpath(p, src)}'.replace(os.sep, '/'))
        for bat, (title, program, tk) in launchers.items():
            if program in files:
                z.write(os.path.join(src, bat), f'{top}/{bat}')
        extra = f'\nWhat is new in this build:\n{notes}\n' if notes else ''
        z.writestr(f'{top}/READ ME FIRST.txt', README[edition].format(extra=extra).replace('\n', '\r\n'))
        for w in wheels():
            z.write(w, f'{top}/windows/wheels/{os.path.basename(w)}', compress_type=zipfile.ZIP_STORED)
    return out


if __name__ == '__main__':
    flags = {a for a in sys.argv[1:] if a.startswith('--')}
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    for path in write_launchers():
        print(f'{os.path.relpath(path, ROOT)}')
    if not args:
        sys.exit(0 if '--launchers' in flags else __doc__)
    notes = open(args[1], encoding='utf-8').read() if len(args) > 1 else ''
    editions = [e for e in EDITIONS if f'--{e}' in flags] or list(EDITIONS)
    for e in editions:
        path = build(e, args[0], notes, play='--play' in flags)
        print(f'{path}  ({os.path.getsize(path) / 1e6:.1f} MB)')
