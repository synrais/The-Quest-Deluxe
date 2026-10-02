"""Packs what was added in the editor into a dated zip, to send on.

Double-click "Make Edits Zip.bat" (in the main folder, next to TheQuestClassic and TheQuestDeluxe). It makes
QuestEdits_<date>_<time>.zip beside it, holding:

  - every file of packs/TheQuest that is new or different from the shipped pack (new pictures, the changed
    items.json, creatures.json, tiles.json, spells.json, maps, scripts ...),
  - every file of any other pack in TheQuestDeluxe/packs (a pack made new in the editor),
  - WHAT_CHANGED.txt, which lists them and says what is in them: the new and changed items, creatures, spells,
    classes and tiles (their fields), every new picture with its size (and a warning if it is not 40 x 40, or
    is somewhere the editor does not look), and a note typed in the window when it ran (NOTES.txt too).

The paths inside the zip start at TheQuestDeluxe/..., so unzipping it over a copy of the repository puts every
file where it belongs. Nothing is changed or deleted in the packs: the zip is only a copy.

    python tools/pack_edits_zip.py             make the zip
    python tools/pack_edits_zip.py --all       put every pack's every file in it
    python tools/pack_edits_zip.py --note ...  add a note to say what was tried (the .bat asks for one)
    python tools/pack_edits_zip.py --baseline  record the shipped packs/TheQuest as it is now (tools/pack_baseline.json:
                                               what "different from the shipped pack" is compared with; whoever changes
                                               the shipped pack runs this, and the tests fail until they do)

Needs only Python: no extra packages.
"""
from __future__ import annotations

import hashlib
import json
import os
import struct
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
TABLES = ('items.json', 'creatures.json', 'spells.json', 'classes.json', 'skills.json', 'tiles.json', 'quest.json')
PICTURE_FOLDERS = ('floors', 'walls', 'decos', 'items', 'bag', 'creatures', 'spells', 'heroes')   # where the editor looks


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


def read_tables(folder: str) -> dict:
    out = {}
    for name in TABLES:
        path = os.path.join(folder, name)
        if os.path.exists(path):
            try:
                with open(path, encoding='utf-8') as fh:
                    out[name] = json.load(fh)
            except (OSError, ValueError):
                pass
    return out


def write_baseline(root: str = ROOT, path: str = BASELINE) -> int:
    folder = os.path.join(root, PACKS, SHIPPED)
    now = scan(folder)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump({'pack': SHIPPED, 'files': now, 'tables': read_tables(folder)}, fh, indent=0, sort_keys=True)
        fh.write('\n')
    return len(now)


def read_baseline(path: str = BASELINE) -> dict:
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)['files']


def read_baseline_tables(path: str = BASELINE) -> dict:
    with open(path, encoding='utf-8') as fh:
        return json.load(fh).get('tables', {})


def short(value, n=230) -> str:
    text = json.dumps(value, ensure_ascii=False)
    return text if len(text) <= n else text[:n - 3] + '...'


def diff_tables(base: dict, now: dict) -> list:
    """Lines saying which entries of the pack's tables are new, changed or gone, and which fields changed."""
    lines = []
    for name in TABLES:
        a, b = base.get(name), now.get(name)
        if a is None or b is None or a == b:
            continue
        lines.append(f'{name}:')
        keys = [k for k in dict.fromkeys(list(a) + list(b))] if isinstance(b, dict) else []
        for key in keys:
            va, vb = a.get(key), b.get(key)
            if va == vb:
                continue
            if isinstance(vb, list) and all(isinstance(r, dict) and 'id' in r for r in (vb or [])) and \
                    all(isinstance(r, dict) and 'id' in r for r in (va or [])):
                ra, rb = {r['id']: r for r in va or []}, {r['id']: r for r in vb or []}
                for i in rb:
                    if i not in ra:
                        lines.append(f'    NEW {key} {i} {rb[i].get("name", "")!r}: {short(rb[i])}')
                for i in ra:
                    if i not in rb:
                        lines.append(f'    REMOVED {key} {i} {ra[i].get("name", "")!r}')
                for i in rb:
                    if i in ra and ra[i] != rb[i]:
                        fields = sorted(set(ra[i]) | set(rb[i]))
                        said = '; '.join(f'{f}: {short(ra[i].get(f))} -> {short(rb[i].get(f))}'
                                         for f in fields if ra[i].get(f) != rb[i].get(f))
                        lines.append(f'    CHANGED {key} {i} {rb[i].get("name", "")!r}: {said}')
            else:
                lines.append(f'    CHANGED {key}: {short(va)} -> {short(vb)}')
    return lines


def png_size(path: str):
    """(width, height) of a PNG from its header, or None."""
    try:
        with open(path, 'rb') as fh:
            head = fh.read(24)
        if head[:8] == b'\x89PNG\r\n\x1a\n':
            return struct.unpack('>II', head[16:24])
    except OSError:
        pass
    return None


def lint_pictures(folder: str, files: list) -> list:
    """One line for each new or changed picture: its size, with a warning for what the editor would not find or
    would have to scale (it draws 40 x 40)."""
    lines = []
    for f in files:
        if not f.lower().endswith('.png') or not f.startswith('sprites/'):
            continue
        parts = f.split('/')
        size = png_size(os.path.join(folder, *parts))
        warn = []
        if len(parts) != 3 or parts[1] not in PICTURE_FOLDERS:
            warn.append('not where the editor looks (sprites/<folder>/<number>.png): the game ignores it')
        elif not os.path.splitext(parts[2])[0].lstrip('-').isdigit():
            warn.append('the name is not a number: the game ignores it')
        if size and size != (40, 40):
            warn.append(f'{size[0]} x {size[1]}, not 40 x 40: it is scaled')
        lines.append(f'    {f}: {size[0]} x {size[1]}' if size else f'    {f}: not a readable PNG')
        if warn:
            lines[-1] += '   WARNING: ' + '; '.join(warn)
    return lines


def compare(now: dict, base: dict):
    added = sorted(f for f in now if f not in base)
    changed = sorted(f for f in now if f in base and now[f] != base[f])
    removed = sorted(f for f in base if f not in now)
    return added, changed, removed


def build(root: str = ROOT, include_all: bool = False, when: float | None = None, baseline: str = BASELINE,
          note: str = ''):
    """Make the zip. Returns (path of the zip or None, the report text)."""
    packs = os.path.join(root, PACKS)
    if not os.path.isdir(packs):
        return None, f'There is no {PACKS} folder in {root}. Run this from the main folder of the game.'
    stamp = time.localtime(when)
    lines = [f'Quest edits, made {time.strftime("%Y-%m-%d %H:%M", stamp)}', '']
    if note.strip():
        lines += ['NOTE FROM WHOEVER MADE THIS:', note.strip(), '']
    files = []                                                  # (path on disk, path in the zip)
    base = read_baseline(baseline) if os.path.exists(baseline) else None
    if base is None and not include_all:
        lines += ['!! tools/pack_baseline.json is missing, so there is nothing to compare packs/TheQuest with: all of',
                  '!! it is sent. (Get the latest game folder, which has that file, for a list of only what changed.)', '']
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
            tables = diff_tables(read_baseline_tables(baseline), read_tables(folder))
            if tables:
                lines += ['', 'What changed in the tables:'] + tables
            pictures = lint_pictures(folder, added + changed)
            if pictures:
                lines += ['', 'The new and changed pictures:'] + pictures
            lines.append('')
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
        if note.strip():
            z.writestr('NOTES.txt', note.strip() + '\n')
        for disk, arc in files:
            z.write(disk, arc)
    return out, report


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if '--baseline' in argv:
        n = write_baseline()
        print(f'Recorded {n} files of packs/{SHIPPED} in {os.path.relpath(BASELINE, ROOT)}.')
        return 0
    note = os.environ.get('QUEST_NOTE', '')                    # what the .bat asked for
    if '--note' in argv:
        note = ' '.join(argv[argv.index('--note') + 1:])
    path, report = build(include_all='--all' in argv, note=note)
    print(report)
    if path is None:
        return 1
    print('Made:', path)
    print('Send this zip on.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
