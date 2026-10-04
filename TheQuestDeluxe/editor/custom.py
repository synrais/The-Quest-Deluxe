"""Custom Maps: the editor only ever edits packs in the Custom Maps folder, one subfolder each, every one made as a
copy of the locked game (packs/TheQuest, the first 7 levels). The locked game itself is never opened for editing.
No tkinter here: the tests use it too."""
from __future__ import annotations

import os
import re

from engine import packio
from engine.pack import CUSTOM_DIR, DEFAULT_PACK, PACKS_DIR, custom_packs

from .project import Project

NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9 _.\-]{0,38}$')


def pack_dir(name: str) -> str:
    return os.path.join(CUSTOM_DIR, name)


def valid_name(name: str, folder: str | None = None) -> str | None:
    """Why this can't be a pack's name (None if it can)."""
    name = (name or '').strip()
    if not NAME.match(name):
        return 'Use letters, numbers, spaces, - and _ (up to 40), starting with a letter or number.'
    if name.lower() == 'thequest' or name.lower() in {n.lower() for n in os.listdir(PACKS_DIR)}:
        return f'"{name}" is the name of a game that comes with Quest Deluxe. Pick another.'
    if name.lower() in {n.lower() for n in (os.listdir(folder or CUSTOM_DIR) if os.path.isdir(folder or CUSTOM_DIR) else [])}:
        return f'There is already a pack called "{name}".'
    return None


def create(name: str, folder: str | None = None, template: str | None = None) -> str:
    """Make Custom Maps/<name>: a full copy of the locked game (its 7 levels, creatures, items, pictures ...). Returns its
    folder."""
    name = name.strip()
    problem = valid_name(name, folder)
    if problem:
        raise ValueError(problem)
    root = folder or CUSTOM_DIR
    os.makedirs(root, exist_ok=True)
    dest = os.path.join(root, name)
    Project.create(dest, template or DEFAULT_PACK, blank=False)
    quest = packio.read_json(os.path.join(dest, 'quest.json'))
    quest['title'] = name
    packio.write_json(os.path.join(dest, 'quest.json'), quest)
    return dest


def is_locked(path: str) -> bool:
    """Is this a pack that comes with the game (under packs/), which the editor never opens?"""
    path = os.path.abspath(path)
    return os.path.dirname(path) == os.path.abspath(PACKS_DIR) or path == os.path.abspath(DEFAULT_PACK)


def packs() -> list[str]:
    return custom_packs()
