"""The hero and the place both sides start from: a save file the original loads and our engine starts from.

The save is made from the ORIGINAL pack's level (that is what the DOS game will show); our side starts the pack being tested on the
same level and square with the same hero, so a difference you see is a difference between the pack and the original.
"""
from __future__ import annotations

import os

from engine import rules, savefile

SLOT = 1


def place(game, level: int, at=None):
    """Put the game's hero on `level` (at square `at` when it is free), as test play does."""
    game.overlay = None
    game.goto_level(level)
    w = game.world
    if at and w.in_map(*at) and not game.pack.wall(w.sq(*at).wall).get('solid'):
        w.leave_room()
        game.player.X, game.player.Y = at
        w.enter_room(game.player, game.status)
        game.count_hostiles()
        game.events.on_enter_room()
    rules.status_update(game.player, game.status, game.items)
    game.messages = []


def start(game, level: int, at=None, hero: savefile.SaveData | None = None, cls: int = 1, loadout: dict | None = None):
    """A hero (from a save, or a new one of class `cls`) on a level and square, wearing and carrying the loadout if there is one."""
    if hero is not None:
        game.from_save(hero, SLOT)
        game.overlay = None
    else:
        game.quick_start(cls, level, None)
    if loadout:
        from . import loadout as loadouts
        data = game.to_save()
        loadouts.apply(data, loadout)
        game.from_save(data, SLOT)
        game.overlay = None
    game.status.saveslot = SLOT
    place(game, level, at)
    game.status.saveslot = SLOT


def save_bytes(game) -> bytes:
    """What the original's save() would write for this game."""
    return savefile.to_bytes(game.to_save())


def write_dos_save(data_dir: str, raw: bytes):
    os.makedirs(data_dir, exist_ok=True)
    with open(os.path.join(data_dir, f'save{SLOT:02d}.dat'), 'wb') as fh:
        fh.write(raw)
