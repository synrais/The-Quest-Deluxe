"""Send the edits to the game's repository on GitHub, as a branch of their own (never onto main).

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

REPO = 'synrais/The-Quest-I-II'
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


def branch_name(name: str, when: float | None = None) -> str:
    who = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-') or 'editor'
    return 'edits/%s-%s' % (who, time.strftime('%Y-%m-%d-%H%M%S', time.localtime(when or time.time())))


def total_size(files) -> int:
    return sum(os.path.getsize(p) for p, _ in files)


def send(files, report: str, token: str, name: str = '', repo: str = REPO, when: float | None = None,
         transport=http, progress=None) -> str:
    """Upload files [(disk path, repo path)] plus the report to a new branch. Returns the branch name."""
    token = (token or '').strip()
    if not token:
        raise SendError('There is no key yet. Paste the key you were given.')
    if not files:
        raise SendError('Nothing has been added or changed, so there is nothing to send.')
    say = progress or (lambda msg: None)

    def call(method, path, body=None, what=''):
        status, data = transport(method, '%s/repos/%s/%s' % (API, repo, path), body, token)
        if status >= 300:
            raise SendError(explain(status, what or path))
        return data

    say('Finding the current game...')
    head = call('GET', 'git/ref/heads/' + BASE, what='the game')['object']['sha']
    base_tree = call('GET', 'git/commits/' + head, what='the game')['tree']['sha']
    branch = branch_name(name, when)
    entries = []
    for i, (disk, arc) in enumerate(files, 1):
        say('Sending %d of %d: %s' % (i, len(files), arc))
        with open(disk, 'rb') as fh:
            blob = call('POST', 'git/blobs', {'content': base64.b64encode(fh.read()).decode(), 'encoding': 'base64'},
                        what=arc)['sha']
        entries.append({'path': arc, 'mode': '100644', 'type': 'blob', 'sha': blob})
    note = call('POST', 'git/blobs', {'content': report, 'encoding': 'utf-8'}, what='the note')['sha']
    entries.append({'path': 'edits_inbox/%s/WHAT_CHANGED.txt' % branch.split('/', 1)[1], 'mode': '100644',
                    'type': 'blob', 'sha': note})
    say('Putting it together...')
    tree = call('POST', 'git/trees', {'base_tree': base_tree, 'tree': entries}, what='the files')['sha']
    msg = 'Edits from %s (%d files)\n\n%s' % (name or 'the editor', len(files), report[:4000])
    commit = call('POST', 'git/commits', {'message': msg, 'tree': tree, 'parents': [head]}, what='the edits')['sha']
    call('POST', 'git/refs', {'ref': 'refs/heads/' + branch, 'sha': commit}, what='the branch')
    say('Sent.')
    return branch
