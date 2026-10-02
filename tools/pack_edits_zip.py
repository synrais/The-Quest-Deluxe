"""Packs what was added in the editor into a dated zip, to send on.

Double-click "Make Edits Zip.bat" (in the main folder, next to TheQuestClassic and TheQuestDeluxe). It makes
QuestEdits_<date>_<time>.zip beside it, holding:

  - every file of packs/TheQuest that is new or different from the shipped pack (new pictures, the changed
    items.json, creatures.json, tiles.json, spells.json, maps, scripts ...),
  - every file of any other pack in TheQuestDeluxe/packs (a pack made new in the editor),
  - WHAT_CHANGED.txt, which lists them.

The paths inside the zip start at TheQuestDeluxe/..., so unzipping it over a copy of the repository puts every
file where it belongs. Nothing is changed or deleted in the packs: the zip is only a copy.

    python tools/pack_edits_zip.py             make the zip
    python tools/pack_edits_zip.py --all       put every pack's every file in it
    python tools/pack_edits_zip.py --baseline  record the shipped packs/TheQuest as it is now (tools/pack_baseline.json:
                                               what "different from the shipped pack" is compared with; whoever changes
                                               the shipped pack runs this, and the tests fail until they do)

Needs only Python: no extra packages.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                                   # the main folder
PACKS = os.path.join('TheQuestDeluxe', 'packs')
SHIPPED = 'TheQuest'                                           # the pack that ships with the game
BASELINE = os.path.join(HERE, 'pack_baseline.json')
TEXT = ('.json', '.txt', '.qs', '.md', '.ini')                 # compared without their line endings (Windows adds CRs)
SKIP_DIRS = {'__pycache__', '.git'}
SKIP_FILES = {'Thumbs.db', '.DS_Store', 'desktop.ini'}


def file_hash(path: str) -> str:
    with open(path, 'rb') as fh:
        data = fh.read()
    if path.lower().endswith(TEXT):
        data = data.replace(b'\r\n', b'\n')
    return hashlib.sha1(data).hexdigest()


def scan(folder: str) -> dict:
    """{path inside the folder, with /: hash} of every file in it."""
    out = {}
    for here, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if f in SKIP_FILES or f.endswith('.pyc'):
                continue
            full = os.path.join(here, f)
            out[os.path.relpath(full, folder).replace(os.sep, '/')] = file_hash(full)
    return out


def write_baseline(root: str = ROOT, path: str = BASELINE) -> int:
    now = scan(os.path.join(root, PACKS, SHIPPED))
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump({'pack': SHIPPED, 'files': now}, fh, indent=0, sort_keys=True)
        fh.write('\n')
    return len(now)


def read_baseline(path: str = BASELINE) -> dict:
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)['files']


def compare(now: dict, base: dict):
    added = sorted(f for f in now if f not in base)
    changed = sorted(f for f in now if f in base and now[f] != base[f])
    removed = sorted(f for f in base if f not in now)
    return added, changed, removed


def build(root: str = ROOT, include_all: bool = False, when: float | None = None, baseline: str = BASELINE):
    """Make the zip. Returns (path of the zip or None, the report text)."""
    packs = os.path.join(root, PACKS)
    if not os.path.isdir(packs):
        return None, f'There is no {PACKS} folder in {root}. Run this from the main folder of the game.'
    stamp = time.localtime(when)
    lines = [f'Quest edits, made {time.strftime("%Y-%m-%d %H:%M", stamp)}', '']
    files = []                                                  # (path on disk, path in the zip)
    base = read_baseline(baseline) if os.path.exists(baseline) else None
    for name in sorted(os.listdir(packs)):
        folder = os.path.join(packs, name)
        if not os.path.isdir(folder) or name.startswith('.'):
            continue
        now = scan(folder)
        if name == SHIPPED and base is not None and not include_all:
            added, changed, removed = compare(now, base)
            lines.append(f'packs/{name} (the shipped pack): {len(added)} new, {len(changed)} changed, '
                         f'{len(removed)} removed files')
            for label, group in (('new', added), ('changed', changed), ('removed', removed)):
                lines += [f'    {label}: {f}' for f in group]
            for f in added + changed:
                files.append((os.path.join(folder, *f.split('/')), f'TheQuestDeluxe/packs/{name}/{f}'))
        else:
            lines.append(f'packs/{name}: {"a pack of its own" if name != SHIPPED else "everything"}, '
                         f'{len(now)} files')
            for f in sorted(now):
                files.append((os.path.join(folder, *f.split('/')), f'TheQuestDeluxe/packs/{name}/{f}'))
    if not files:
        return None, 'Nothing has been added or changed since the game came: there is nothing to pack.'
    lines += ['', f'{len(files)} files in all.']
    report = '\n'.join(lines) + '\n'
    out = os.path.join(root, time.strftime('QuestEdits_%Y-%m-%d_%H%M.zip', stamp))
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('WHAT_CHANGED.txt', report)
        for disk, arc in files:
            z.write(disk, arc)
    return out, report


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if '--baseline' in argv:
        n = write_baseline()
        print(f'Recorded {n} files of packs/{SHIPPED} in {os.path.relpath(BASELINE, ROOT)}.')
        return 0
    path, report = build(include_all='--all' in argv)
    print(report)
    if path is None:
        return 1
    print('Made:', path)
    print('Send this zip on.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
