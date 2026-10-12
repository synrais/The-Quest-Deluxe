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


def start(game, level: int, at=None, hero: savefile.SaveData | None = None, cls: int = 1, loadout: dict | None = None, story=None):
    """A hero (from a save, or a new one of class `cls`) on a level and square, wearing and carrying the loadout if there is one.
    story: (mission1, mission2), how far the level's story has got (the last level's Death Bringer only comes when mission2 is 2)."""
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
    if story is not None:
        game.status.mission1, game.status.mission2 = int(story[0]), int(story[1])
    scenario(game, loadout or {})
    game.status.saveslot = SLOT


def scenario(game, spec: dict):
    """A test screen made from a loadout's extra keys (both sides run this, on the same dice, so both start from the same screen):
    only: creature numbers to leave on the screen; spawn: creatures added; talks: talk() for these creatures, as the story would have, in this order
    (a scene is walked through); edit: {creature number: {field: value}} (a boss with one hit left)."""
    from engine import rules
    w = game.world
    if spec.get('only') is not None:
        for e in list(w.enemies):
            if e.type not in spec['only']:
                w.sq(e.x, e.y).mon = 0
                w.enemies.remove(e)
        game.count_hostiles()
    for number, x, y in spec.get('spawn') or []:                      # creatures put on the screen: [number, x, y] (x, y on the screen, 1 to 10)
        game.spawn(int(number), w.origin[0] + int(x) - 1, w.origin[1] + int(y) - 1)
    if spec.get('talks'):
        rules._seed[0] = 777
        here = (game.player.X, game.player.Y)
        for npc in spec['talks']:
            game.events.talk(npc)
        game.player.X, game.player.Y = here                           # (a scene may push the hero back a square: he starts where he was put)
        game.count_hostiles()
    if spec.get('next_to') is not None:                              # the hero beside the first creature of this number, on a free square
        target = next((e for e in w.enemies if e.type == int(spec['next_to'])), None)
        if target is not None:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                x, y = target.x + dx, target.y + dy
                if w.in_map(x, y) and w.sq(x, y).mon == 0 and not game.pack.wall(w.sq(x, y).wall).get('solid'):
                    game.player.X, game.player.Y = x, y
                    break
    for number, fields in (spec.get('edit') or {}).items():
        for e in w.enemies:
            if e.type == int(number):
                for field, v in fields.items():
                    setattr(e, field, int(v))


def save_bytes(game) -> bytes:
    """What the original's save() would write for this game."""
    return savefile.to_bytes(game.to_save())


def write_dos_save(data_dir: str, raw: bytes):
    os.makedirs(data_dir, exist_ok=True)
    with open(os.path.join(data_dir, f'save{SLOT:02d}.dat'), 'wb') as fh:
        fh.write(raw)
