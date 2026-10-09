"""Send the edits to the game's repository on GitHub, onto a branch of their own (never onto main): one branch per person,
`edits/<username>`, that every send adds a commit to, so each send is kept in its history and nobody's work mixes with another's.
In it, everything is under `edits_inbox/<username>/`:
    files/            the new and changed files, with the paths they have in the game folder (copy them over it to use them)
    compare zips/     the recordings of comparisons with the DOS game
    latest/WHAT_CHANGED.txt   the report of the last send;  sends/<date-time>/WHAT_CHANGED.txt   the report of each one

Pure standard library, no tkinter: the editor's "Send my edits..." window and the tests both use it.
The key (a fine-grained GitHub token limited to the one repository) is kept in ~/.quest_editor.json,
outside the game folder, so it is never zipped or committed.
"""
from __future__ import annotations

import base64
import json
import os
import re
import time
import urllib.error
import urllib.request

REPO = 'synrais/The-Quest-Deluxe'
BASE = 'main'
API = 'https://api.github.com'
SETTINGS = os.path.join(os.path.expanduser('~'), '.quest_editor.json')
BIG = 20 * 1024 * 1024                                          # warn above this much in one go


class SendError(Exception):
    """Something went wrong; the message is for the person at the editor."""


def load_settings(path: str = SETTINGS) -> dict:
    try:
        with open(path, encoding='utf-8') as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(values: dict, path: str = SETTINGS) -> None:
    data = load_settings(path)
    data.update(values)
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, indent=2)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def http(method: str, url: str, body, token: str):
    """The real transport: (status, parsed JSON)."""
    req = urllib.request.Request(url, method=method, data=None if body is None else json.dumps(body).encode(),
                                 headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
                                          'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'QuestEditor',
                                          'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b'{}')
        except ValueError:
            return e.code, {}
    except (urllib.error.URLError, OSError) as e:
        raise SendError('Could not reach GitHub. Is the internet on? (%s)' % getattr(e, 'reason', e))


def explain(status: int, what: str) -> str:
    if status == 401:
        return 'GitHub did not accept the key (wrong, mistyped or expired). Ask for a new one.'
    if status in (403, 404):
        return ('GitHub refused (%s). The key may be out of date, or not allowed to write to the game repository.'
                % what)
    if status == 422:
        return 'GitHub did not like that (%s). Try again in a minute.' % what
    return 'GitHub said %d (%s).' % (status, what)


def username(text: str) -> str:
    """A name that is safe for a branch and a folder: lower case letters, numbers, - and _ ."""
    return re.sub(r'[^a-z0-9_-]+', '-', (text or '').lower()).strip('-')[:30]


def branch_name(user: str) -> str:
    return 'edits/' + (username(user) or 'unknown')


def inbox_path(user: str, arc: str) -> str:
    """Where a file goes in the repository: under the person's own folder."""
    root = 'edits_inbox/' + (username(user) or 'unknown')
    marker = '/compare zips/'
    if marker in arc:
        return f'{root}/compare zips/{arc.split(marker, 1)[1]}'
    return f'{root}/files/{arc}'


def total_size(files) -> int:
    return sum(os.path.getsize(p) for p, _ in files)


def send(files, report: str, token: str, name: str = '', repo: str = REPO, when: float | None = None,
         transport=http, progress=None, user: str = '') -> str:
    """Upload files [(disk path, repo path)] plus the report onto the person's branch (made if it is new). Returns the branch name."""
    token = (token or '').strip()
    user = username(user or name)
    if not token:
        raise SendError('There is no key yet. Paste the key you were given.')
    if not user:
        raise SendError('There is no username yet. Type the username you were given (letters and numbers).')
    if not files:
        raise SendError('Nothing has been added or changed, so there is nothing to send.')
    say = progress or (lambda msg: None)

    def call(method, path, body=None, what='', allow_missing=False):
        status, data = transport(method, '%s/repos/%s/%s' % (API, repo, path), body, token)
        if allow_missing and status == 404:
            return None
        if status >= 300:
            raise SendError(explain(status, what or path))
        return data

    branch = branch_name(user)
    say('Finding the current game...')
    own = call('GET', 'git/ref/heads/' + branch, what='your branch', allow_missing=True)
    head = (own or call('GET', 'git/ref/heads/' + BASE, what='the game'))['object']['sha']   # on top of what they sent before
    base_tree = call('GET', 'git/commits/' + head, what='the game')['tree']['sha']
    entries = []
    for i, (disk, arc) in enumerate(files, 1):
        say('Sending %d of %d: %s' % (i, len(files), arc))
        with open(disk, 'rb') as fh:
            blob = call('POST', 'git/blobs', {'content': base64.b64encode(fh.read()).decode(), 'encoding': 'base64'},
                        what=arc)['sha']
        entries.append({'path': inbox_path(user, arc), 'mode': '100644', 'type': 'blob', 'sha': blob})
    note = call('POST', 'git/blobs', {'content': report, 'encoding': 'utf-8'}, what='the note')['sha']
    stamp = time.strftime('%Y-%m-%d-%H%M%S', time.localtime(when or time.time()))
    for path in (f'edits_inbox/{user}/latest/WHAT_CHANGED.txt', f'edits_inbox/{user}/sends/{stamp}/WHAT_CHANGED.txt'):
        entries.append({'path': path, 'mode': '100644', 'type': 'blob', 'sha': note})
    say('Putting it together...')
    tree = call('POST', 'git/trees', {'base_tree': base_tree, 'tree': entries}, what='the files')['sha']
    msg = 'Edits from %s (%s), %d files, %s\n\n%s' % (name or user, user, len(files), stamp, report[:4000])
    commit = call('POST', 'git/commits', {'message': msg, 'tree': tree, 'parents': [head]}, what='the edits')['sha']
    if own:
        call('PATCH', 'git/refs/heads/' + branch, {'sha': commit}, what='your branch')
    else:
        call('POST', 'git/refs', {'ref': 'refs/heads/' + branch, 'sha': commit}, what='the branch')
    say('Sent.')
    return branch
