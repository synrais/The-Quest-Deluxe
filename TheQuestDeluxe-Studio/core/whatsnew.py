"""What is new: the notes that come with each update (core/whatsnew.json), so people are told what changed.

    [{"id": "2026-10-12-speed", "date": "2026-10-12", "title": "Play faster", "changes": ["one line a change", ...]}, ...]    newest first

The update question shows the notes of the update before it is installed (fresh(): the notes the repository has that this copy does not), and the first
time the Studio is opened after the update, they are shown once on each computer (unseen(): the ones not yet in the Studio's settings under
"whatsnew_seen"). The Studio's menu shows them again. To add one: put an entry first in core/whatsnew.json, with an id nobody has used. No windows here.
"""
from __future__ import annotations

import json
import os

from . import updates

REL = 'core/whatsnew.json'                       # where it is, in the Studio's folder (and in the repository)
SHOWN = 6                                        # how many entries one box shows at most (the newest)


def parse(data: bytes | str) -> list:
    """The entries of a whatsnew.json: only the well made ones ({id, title, changes: [lines]}); anything unreadable is nothing."""
    try:
        raw = json.loads(data)
    except (ValueError, TypeError):
        return []
    out = []
    for e in raw if isinstance(raw, list) else []:
        if isinstance(e, dict) and isinstance(e.get('id'), str) and isinstance(e.get('title'), str) and isinstance(e.get('changes'), list) \
                and e['changes'] and all(isinstance(c, str) for c in e['changes']):
            out.append({'id': e['id'], 'date': str(e.get('date', '')), 'title': e['title'], 'changes': list(e['changes'])})
    return out


def load(root: str) -> list:
    """This copy's notes, newest first."""
    try:
        with open(os.path.join(root, *REL.split('/')), 'rb') as fh:
            return parse(fh.read())
    except OSError:
        return []


def unseen(entries: list, seen) -> list:
    """The notes not shown yet on this computer, the newest SHOWN of them."""
    seen = set(seen or ())
    return [e for e in entries if e['id'] not in seen][:SHOWN]


def fresh(root: str, found: list, token: str = '', get=updates.http) -> list:
    """The notes of an update that has been found (updates.check) and not installed: the repository's, minus the ones this copy has. [] when the
    update does not change the notes, or they cannot be read (a note is never worth failing for)."""
    for rel, sha, _ in found:
        if rel == REL:
            try:
                new = parse(updates.fetch(sha, token, get))
            except (updates.UpdateError, OSError, KeyError, ValueError):
                return []
            have = {e['id'] for e in load(root)}
            return [e for e in new if e['id'] not in have][:SHOWN]
    return []


def text(entries: list) -> str:
    """The notes as plain text (for a box that has no room to lay them out)."""
    out = []
    for e in entries:
        out.append(e['title'])
        out.extend('  - ' + c for c in e['changes'])
        out.append('')
    return '\n'.join(out).strip()
