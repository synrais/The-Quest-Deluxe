"""Your additions, kept off to the side: every Save in the editor makes another zip of what was added or changed
since the game came (a copy; nothing is moved or replaced), in the folder `zips` in Custom Maps (which a new game dragged over this one leaves alone). A new version of the game can be
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
from .pack_edits import CUSTOM, DELUXE, PREFIX, SHIPPED, TABLES



def home_dir() -> str:
    """Where the zips are kept: the folder `zips` in Custom Maps (inside the game folder, so a new game dragged over this
    one leaves it alone). Looked up when asked, so the tests can move it with QUEST_ZIPS_DIR."""
    from engine import pack
    return os.environ.get('QUEST_ZIPS_DIR') or os.path.join(pack.CUSTOM_DIR, 'zips')


def old_dir() -> str:
    """Where the first versions kept them: QuestDeluxeEdits in the home folder (still read, for restoring)."""
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
    base = pack_edits.read_baseline_tables(baseline) if complete else {}
    custom = os.path.join(deluxe, CUSTOM)
    packs = {n: os.path.join(custom, n) for n in sorted(os.listdir(custom))
             if os.path.exists(os.path.join(custom, n, 'quest.json'))} if os.path.isdir(custom) else {}
    now = {n: pack_edits.read_tables(folder) for n, folder in packs.items()}
    delta = {n: d for n in packs if (d := table_delta(base, now[n]))}
    meta = {'made': time.strftime('%Y-%m-%d %H:%M', time.localtime(when)), 'format': 2, 'complete': complete,
            'delta': delta, 'digest': digest(delta, files)}
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
        for n, tables in now.items():                                      # the whole tables too, to read by hand
            for name in tables:
                z.write(os.path.join(packs[n], name), f'tables_full/{n}/{name}')
    return out, report


def read_meta(path: str):
    try:
        with zipfile.ZipFile(path) as z:
            return json.loads(z.read('side_save.json').decode('utf-8'))
    except (OSError, KeyError, ValueError, zipfile.BadZipFile):
        return None


def saved_zips(root: str | None = None) -> list:
    """The saved zips, the newest first: those in the zips folder, and (when no folder is asked for) the ones the first
    versions left in QuestDeluxeEdits in the home folder."""
    found = []
    for folder in ([root] if root else [home_dir(), old_dir()]):
        if os.path.isdir(folder):
            found += [(f, os.path.join(folder, f)) for f in os.listdir(folder)
                      if f.startswith('QuestEdits_2') and f.endswith('.zip')]
    return [path for _, path in sorted(found, reverse=True)]


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


def merge_tables(folder: str, delta: dict, complete: bool, write: bool, label: str) -> list:
    """Put saved table rows into the pack at folder, by number (his rows win; with an incomplete zip only rows that are
    missing are added). Returns what it does."""
    from engine import packio
    changes = []
    for name, keys in delta.items():
        path = os.path.join(folder, name)
        if not os.path.exists(path):
            continue
        data = packio.read_json(path)
        touched = False
        for key, change in keys.items():
            if 'rows' in change:
                have = {r['id']: i for i, r in enumerate(data.get(key) or []) if isinstance(r, dict)}
                for row in change['rows']:
                    what = f'{label}{name}: {key} {row["id"]} {row.get("name", "")}'.rstrip()
                    if row['id'] not in have:
                        data.setdefault(key, []).append(row)
                        changes.append(what + ' (put back)')
                        touched = True
                    elif complete and data[key][have[row['id']]] != row:
                        data[key][have[row['id']]] = row
                        changes.append(what + ' (his version)')
                        touched = True
            elif key not in data or (complete and data[key] != change['value']):
                data[key] = change['value']
                changes.append(f'{label}{name}: {key} (his)')
                touched = True
        if touched and write:
            table_writer(name, data, path)
    return changes


def apply(deluxe: str, zip_path: str, write: bool = False, into: str | None = None):
    """Put a saved zip's edits into the game. A zip made in a Custom Maps pack goes back into that pack (made as a copy
    of the locked game if it is not there). Edits from before Custom Maps, made in packs/TheQuest, go into the pack
    folder `into`, if one is given (otherwise they are left). Table rows are merged by number; his other files
    (pictures, maps, scripts, text) are copied back. Returns the list of what it does (or would do, with write=False)."""
    from engine import packio
    changes = []
    custom = os.path.join(deluxe, CUSTOM)
    shipped = os.path.join(deluxe, 'packs', SHIPPED)
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        if 'side_save.json' in names:
            meta = json.loads(z.read('side_save.json').decode('utf-8'))
        else:                                  # a zip from "Make Edits Zip" or Make zip: its whole tables, rows to add
            meta = {'complete': False, 'delta': {}}
            legacy = {}
            for name in TABLES:
                arc = f'{PREFIX}/packs/{SHIPPED}/{name}'
                if arc in names:
                    try:
                        table = json.loads(z.read(arc).decode('utf-8'))
                    except ValueError:
                        continue
                    for key, value in table.items():
                        if is_rows(value):
                            legacy.setdefault(name, {})[key] = {'rows': value}
            meta['delta'] = legacy
        complete = bool(meta.get('complete'))
        delta = meta.get('delta') or {}
        # format 2: {pack: {table file: ...}} for the packs of Custom Maps; before it, one flat {table file: ...} of
        # packs/TheQuest, which goes into the pack named by `into`
        deltas = delta if meta.get('format') == 2 else ({'': delta} if delta else {})
        for pack, delta in deltas.items():
            folder = into if pack == '' else os.path.join(custom, pack)
            if folder is None:
                continue
            if pack and not os.path.isdir(folder) and write:
                shutil.copytree(shipped, folder)
            reading = folder if os.path.isdir(folder) else shipped      # a pack still to be made: what it would be
            if os.path.isdir(reading):
                changes += merge_tables(reading, delta, complete, write and reading == folder,
                                        f'{pack + ": " if pack else ""}')
        for arc in names:
            parts = arc.split('/')
            if len(parts) < 4 or parts[0] != PREFIX:
                continue
            if parts[1] == CUSTOM:
                folder, rel = os.path.join(custom, parts[2]), '/'.join(parts[3:])
            elif parts[1] == 'packs' and parts[2] == SHIPPED and into is not None:
                folder, rel = into, '/'.join(parts[3:])
            else:
                continue
            if '/' not in rel and rel in TABLES:
                continue                                              # tables were merged above
            target = os.path.join(folder, *rel.split('/'))
            data = z.read(arc)
            if os.path.exists(target):
                with open(target, 'rb') as fh:
                    here = fh.read()
                if here.replace(b'\r\n', b'\n') == data.replace(b'\r\n', b'\n'):
                    continue
            changes.append(f'{os.path.basename(folder)}: {rel}')
            if write:
                if not os.path.isdir(folder):
                    shutil.copytree(shipped, folder)
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with open(target, 'wb') as fh:
                    fh.write(data)
    return changes
