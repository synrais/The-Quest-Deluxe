"""Looking for a newer Studio, and bringing it in.

The Studio's files are compared with the ones in the game's repository (the git blob checksum of each file, so no version number has to be kept up
to date): what differs, or is new, is an update. Your own things are never part of it: Custom Maps (your quests), saves, settings.ini, backups.
Before anything is changed, ALL of Custom Maps is copied into a zip in `backups` and the zip is read back to check it; the files an update replaces are
kept too, so it can be undone. Pure standard library, no windows: the Studio asks (studio/app.py) and the tests use it with a pretend GitHub.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import time
import urllib.error
import urllib.request
import zipfile

from . import send_edits

REPO = send_edits.REPO
BRANCH = send_edits.BASE
FOLDER = 'TheQuestDeluxe-Studio'                      # the Studio's folder in the repository
SKIP_TOP = {'Custom Maps', 'saves', 'backups', '.deps', 'windows', '__pycache__', '.git'}     # yours, or made on this computer: never compared, never replaced
SKIP_FILES = {'settings.ini'}                         # the player's own settings
API = send_edits.API


class UpdateError(Exception):
    pass


def http(path: str, token: str = '', timeout: float = 8.0):
    """(status, parsed JSON) of a GitHub API call; raises UpdateError when GitHub cannot be reached."""
    headers = {'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'QuestStudio'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    try:
        with urllib.request.urlopen(urllib.request.Request(API + path, headers=headers), timeout=timeout) as r:
            return r.status, json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b'{}')
        except ValueError:
            return e.code, {}
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise UpdateError(f'GitHub could not be reached ({e})')


def blob_sha(data: bytes) -> str:
    return hashlib.sha1(b'blob %d\0' % len(data) + data).hexdigest()


def same_file(path: str, sha: str) -> bool:
    """Is the file the one with this checksum? (A copy that has had its line endings changed counts as the same.)"""
    try:
        with open(path, 'rb') as fh:
            data = fh.read()
    except OSError:
        return False
    lf = data.replace(b'\r\n', b'\n')
    return sha in (blob_sha(data), blob_sha(lf), blob_sha(lf.replace(b'\n', b'\r\n')))


def skipped(rel: str) -> bool:
    parts = rel.replace('\\', '/').split('/')
    return parts[0] in SKIP_TOP or rel in SKIP_FILES or parts[-1].endswith(('.pyc', '.tmp')) or '__pycache__' in parts


def remote_tree(token: str = '', get=http) -> dict:
    """{path in the Studio's folder: checksum} of what the repository has now."""
    status, data = get(f'/repos/{REPO}/git/trees/{BRANCH}:{FOLDER}?recursive=1', token)
    if status != 200 or 'tree' not in data:
        raise UpdateError(f'GitHub did not give the list of files ({status})')
    if data.get('truncated'):
        raise UpdateError('the list of files was too long to read')
    return {e['path']: e['sha'] for e in data['tree'] if e.get('type') == 'blob' and not skipped(e['path'])}


def find_updates(root: str, tree: dict) -> list:
    """[(path, checksum, 'new' | 'changed')] of the files that differ from the repository's."""
    out = []
    for rel, sha in sorted(tree.items()):
        path = os.path.join(root, *rel.split('/'))
        if not os.path.exists(path):
            out.append((rel, sha, 'new'))
        elif not same_file(path, sha):
            out.append((rel, sha, 'changed'))
    return out


def check(root: str, token: str = '', get=http) -> list:
    """The updates there are (an empty list when there are none); raises UpdateError when it cannot be told."""
    return find_updates(root, remote_tree(token, get))


def backup_custom_maps(root: str, stamp: str | None = None) -> str | None:
    """Copy ALL of Custom Maps into backups/Custom Maps <date>.zip, and read the zip back to check it. The zip's path (None if there is no Custom Maps)."""
    src = os.path.join(root, 'Custom Maps')
    if not os.path.isdir(src):
        return None
    out_dir = os.path.join(root, 'backups')
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f'Custom Maps {stamp or time.strftime("%Y-%m-%d_%H%M%S")}.zip')
    names = []
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        for here, _, files in os.walk(src):
            for f in files:
                full = os.path.join(here, f)
                arc = os.path.relpath(full, root).replace(os.sep, '/')
                z.write(full, arc)
                names.append((arc, os.path.getsize(full)))
    with zipfile.ZipFile(path) as z:                                      # read it back: a backup that cannot be read is no backup
        if z.testzip() is not None or sorted((i.filename, i.file_size) for i in z.infolist()) != sorted(names):
            os.remove(path)
            raise UpdateError('the backup of Custom Maps did not check out, so nothing was changed')
    return path


def apply(root: str, updates: list, token: str = '', get=http, progress=None, stamp: str | None = None) -> dict:
    """Back up Custom Maps, then bring the files in. {'backup': zip or None, 'done': [...], 'failed': [(path, why)], 'kept': folder of the replaced files}."""
    say = progress or (lambda text: None)
    stamp = stamp or time.strftime('%Y-%m-%d_%H%M%S')
    say('Backing up all of Custom Maps ...')
    backup = backup_custom_maps(root, stamp)                              # first of all: if this fails, nothing is touched
    kept = os.path.join(root, 'backups', f'replaced files {stamp}')
    done, failed = [], []
    for i, (rel, sha, why) in enumerate(updates, 1):
        say(f'Updating {i} of {len(updates)}: {rel}')
        try:
            status, data = get(f'/repos/{REPO}/git/blobs/{sha}', token)
            if status != 200 or data.get('encoding') != 'base64':
                raise UpdateError(f'GitHub said {status}')
            content = base64.b64decode(data['content'])
            if blob_sha(content) != sha:
                raise UpdateError('what came did not match its checksum')
            path = os.path.join(root, *rel.split('/'))
            if os.path.exists(path):
                keep = os.path.join(kept, *rel.split('/'))
                os.makedirs(os.path.dirname(keep), exist_ok=True)
                shutil.copy2(path, keep)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp = path + '.update'
            with open(tmp, 'wb') as fh:
                fh.write(content)
            os.replace(tmp, path)
            done.append(rel)
        except (UpdateError, OSError, KeyError, ValueError) as e:
            failed.append((rel, str(e)))
            try:
                os.remove(os.path.join(root, *rel.split('/')) + '.update')
            except OSError:
                pass
    return {'backup': backup, 'done': done, 'failed': failed, 'kept': kept if done and os.path.isdir(kept) else None}
