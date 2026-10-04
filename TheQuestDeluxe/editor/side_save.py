"""Your additions, kept off to the side: every Save in the editor makes another zip of what was added or changed
since the game came (a copy; nothing is moved or replaced), in QuestDeluxeEdits in your home folder, outside the game folder. A new version of the game can be
dragged over the old one without losing anything: the editor offers to put the zip's edits back (restore).

The zip is the same content "Send my edits..." sends: the new and changed files of the packs, WHAT_CHANGED.txt, and
side_save.json: the changed rows of the shipped pack's tables (items, creatures, classes ...) found by number, so they
can be merged into a newer game's tables. No tkinter here: the tests use it too."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
import zipfile

from . import pack_edits
from .pack_edits import DELUXE, PREFIX, SHIPPED, TABLES



def home_dir() -> str:
    """Where the zips are kept: QuestDeluxeEdits in the home folder (looked up when asked, so tests can move it)."""
    return os.path.join(os.path.expanduser('~'), 'QuestDeluxeEdits')




def is_rows(value) -> bool:
    return isinstance(value, list) and all(isinstance(r, dict) and 'id' in r for r in value)


def table_delta(base: dict, now: dict) -> dict:
    """{file: {key: {'rows': [added or changed rows]} or {'value': changed value}}} between the shipped tables
    (base) and the pack's tables now."""
    out = {}
    for name, data in now.items():
        if not isinstance(data, dict):
            continue
        before = base.get(name, {}) if isinstance(base.get(name), dict) else {}
        for key, value in data.items():
            if key == '_comment':
                continue
            if is_rows(value):
                old = {r['id']: r for r in before.get(key) or [] if isinstance(r, dict) and 'id' in r}
                rows = [r for r in value if old.get(r['id']) != r]
                if rows:
                    out.setdefault(name, {})[key] = {'rows': rows}
            elif before.get(key) != value:
                out.setdefault(name, {})[key] = {'value': value}
    return out


def digest(delta: dict, files) -> str:
    h = hashlib.sha1(json.dumps(delta, sort_keys=True).encode())
    for disk, arc in sorted(files, key=lambda f: f[1]):
        h.update(arc.encode())
        h.update(pack_edits.file_hash(disk).encode())
    return h.hexdigest()


def save_zip(deluxe: str = DELUXE, root: str | None = None, baseline: str = pack_edits.BASELINE, when: float | None = None,
             note: str = ''):
    """Make a new zip of the edits, QuestEdits_<date>_<time>.zip, in the folder (a copy: nothing in the game is moved,
    and no zip is ever replaced or deleted). When the edits are just what the newest zip already holds, no new one is
    made. Returns (path of the newest zip or None, the report)."""
    root = root or home_dir()
    files, report = pack_edits.gather(deluxe, False, when, baseline, note)
    if not files:
        return None, report
    complete = os.path.exists(baseline)
    shipped = os.path.join(deluxe, 'packs', SHIPPED)
    now = pack_edits.read_tables(shipped)
    delta = table_delta(pack_edits.read_baseline_tables(baseline) if complete else {}, now)
    meta = {'made': time.strftime('%Y-%m-%d %H:%M', time.localtime(when)), 'complete': complete, 'delta': delta,
            'digest': digest(delta, files)}
    os.makedirs(root, exist_ok=True)
    zips = saved_zips(root)
    old = read_meta(zips[0]) if zips else None
    if old and old.get('digest') == meta['digest']:
        return zips[0], report
    out = os.path.join(root, time.strftime('QuestEdits_%Y-%m-%d_%H%M%S.zip', time.localtime(when)))
    n = 1
    while os.path.exists(out):                                          # two saves in one second: never overwrite
        n += 1
        out = out[:-4].split('~')[0] + f'~{n}.zip'
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('WHAT_CHANGED.txt', report)
        z.writestr('side_save.json', json.dumps(meta, indent=1, sort_keys=True))
        if note.strip():
            z.writestr('NOTES.txt', note.strip() + '\n')
        for disk, arc in files:
            z.write(disk, arc)
        for name in now:                                                   # the whole tables too, to read by hand
            z.write(os.path.join(shipped, name), f'tables_full/{name}')
    return out, report


def read_meta(path: str):
    try:
        with zipfile.ZipFile(path) as z:
            return json.loads(z.read('side_save.json').decode('utf-8'))
    except (OSError, KeyError, ValueError, zipfile.BadZipFile):
        return None


def saved_zips(root: str | None = None) -> list:
    """The saved zips, the newest first."""
    root = root or home_dir()
    if not os.path.isdir(root):
        return []
    return [os.path.join(root, f) for f in sorted((f for f in os.listdir(root)
                                                    if f.startswith('QuestEdits_2') and f.endswith('.zip')), reverse=True)]


def table_writer(name: str, data: dict, path: str):
    """Write a table file back the way the editor does."""
    from engine import packio
    if name == 'tiles.json':
        packio.write_text(path, packio.tiles_text(data))
    elif name == 'quest.json':
        packio.write_json(path, data)
    else:
        key = next((k for k, v in data.items() if is_rows(v)), None)
        if key is None:
            packio.write_json(path, data)
        else:
            packio.write_table(path, key, data[key], data.get('_comment', ''))


def apply(deluxe: str, zip_path: str, write: bool = False):
    """Put a saved zip's edits into the game: its rows go into the shipped pack's tables by number (his rows win; with
    an incomplete zip, which could not tell his edits from the game's, only rows that are missing are added), and
    its other files are copied back. Returns the list of what it does (or would do, with write=False)."""
    from engine import packio
    changes = []
    with zipfile.ZipFile(zip_path) as z:
        if 'side_save.json' in z.namelist():
            meta = json.loads(z.read('side_save.json').decode('utf-8'))
        else:                                  # a zip from "Make Edits Zip" or Make zip: its whole tables, rows to add
            meta = {'complete': False, 'delta': {}}
            for name in TABLES:
                arc = f'{PREFIX}/packs/{SHIPPED}/{name}'
                if arc in z.namelist():
                    try:
                        table = json.loads(z.read(arc).decode('utf-8'))
                    except ValueError:
                        continue
                    for key, value in table.items():
                        if is_rows(value):
                            meta['delta'].setdefault(name, {})[key] = {'rows': value}
        shipped = os.path.join(deluxe, 'packs', SHIPPED)
        for name, keys in meta.get('delta', {}).items():
            path = os.path.join(shipped, name)
            if not os.path.exists(path):
                continue
            data = packio.read_json(path)
            touched = False
            for key, change in keys.items():
                if 'rows' in change:
                    have = {r['id']: i for i, r in enumerate(data.get(key) or []) if isinstance(r, dict)}
                    for row in change['rows']:
                        if row['id'] not in have:
                            data.setdefault(key, []).append(row)
                            changes.append(f'{name}: {key} {row["id"]} {row.get("name", "")}'.rstrip() + ' (put back)')
                            touched = True
                        elif meta.get('complete') and data[key][have[row['id']]] != row:
                            data[key][have[row['id']]] = row
                            changes.append(f'{name}: {key} {row["id"]} {row.get("name", "")}'.rstrip() + ' (his version)')
                            touched = True
                elif key not in data or (meta.get('complete') and data[key] != change['value']):
                    data[key] = change['value']
                    changes.append(f'{name}: {key} (his)')
                    touched = True
            if touched and write:
                table_writer(name, data, path)
        for arc in z.namelist():
            if not arc.startswith(f'{PREFIX}/packs/'):
                continue
            rel = arc[len(PREFIX) + 1:]
            target = os.path.join(deluxe, *rel.split('/'))
            parts = rel.split('/')
            if len(parts) == 3 and parts[1] == SHIPPED and parts[2] in TABLES:
                continue                                                  # tables were merged above
            data = z.read(arc)
            if os.path.exists(target):
                with open(target, 'rb') as fh:
                    here = fh.read()
                if here.replace(b'\r\n', b'\n') == data.replace(b'\r\n', b'\n'):
                    continue
            changes.append(f'{rel}')
            if write:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with open(target, 'wb') as fh:
                    fh.write(data)
    return changes
