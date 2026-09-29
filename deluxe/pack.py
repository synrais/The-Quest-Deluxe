"""Quest packs: everything a quest is made of, as plain files in one folder.

    packs/<name>/quest.json         title, author, number of levels, ...
                 items.json         every item: name, price, stats
                 spells.json        every spell: requirements, mana, range, power, duration
                 creatures.json     monsters, people and summoned allies: stats, rewards
                 tiles.json         floor, wall and decoration names
                 text/talk.txt      what people say (the original Talk.dat layout)
                 text/stories.txt   the story screens (story.dat layout)
                 text/questions.txt the character-creation questions (qs.dat layout)
                 levels/<n>/map.txt     the 100x100 map, one square per line
                 levels/<n>/script.qs   the level's events
                 levels/<n>/shops/<k>.txt  a shop's wares
                 levels/common.qs   events shared by every level
                 sprites/...        pictures, by kind and id
                 fonts/*.CHR        the Borland stroked fonts

docs/QUEST_PACKS.md describes each file. tools/make_pack.py builds packs/quest1 from the original.
"""
from __future__ import annotations

import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKS_DIR = os.path.join(ROOT, 'packs')
DEFAULT_PACK = os.path.join(PACKS_DIR, 'quest1')

ITEM_COLUMNS = ['req_str', 'req_int', 'atk', 'def', 'warm', 'marm', 'str', 'int', 'power', 'kind', 'dex', 'acc']
SPELL_COLUMNS = ['req_int', 'mana', 'range', 'power', 'duration']
CREATURE_COLUMNS = ['life', 'power', 'atk', 'def', 'warm', 'marm', 'range', 'att']

_LEVEL_FILE = re.compile(r'^l(\d{5})\.dat$')
_SHOP_FILE = re.compile(r'^s0000(\d)(\d)\.dat$')


def pack_path() -> str:
    """The pack to play: $QUEST_PACK (a folder, or a name under packs/), else packs/quest1."""
    p = os.environ.get('QUEST_PACK')
    if not p:
        return DEFAULT_PACK
    return p if os.path.isdir(p) else os.path.join(PACKS_DIR, p)


_default = None


def default_pack() -> 'Pack':
    """The pack in play (loaded once), for code that isn't handed one."""
    global _default
    if _default is None:
        _default = Pack()
    return _default


def _load_json(path: str):
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


class Pack:
    """A quest pack, loaded."""

    def __init__(self, root: str | None = None):
        self.root = os.path.abspath(root or pack_path())
        self.quest = _load_json(self.path('quest.json'))
        self.items = {r['id']: r for r in _load_json(self.path('items.json'))['items']}
        self.spells = {r['id']: r for r in _load_json(self.path('spells.json'))['spells']}
        self.creatures = {r['id']: r for r in _load_json(self.path('creatures.json'))['creatures']}
        self.tiles = _load_json(self.path('tiles.json'))
        self.classes = {r['id']: r for r in _load_json(self.path('classes.json'))['classes']}
        self.skills = _load_json(self.path('skills.json'))['skills']
        self.floors = {t['id']: t for t in self.tiles.get('floors', [])}
        self.walls = {t['id']: t for t in self.tiles.get('walls', [])}
        self.decos = {t['id']: t for t in self.tiles.get('decos', [])}
        self._roles = {t['role']: t['id'] for t in self.decos.values() if 'role' in t}
        self._doors = {}
        for t in self.walls.values():
            if 'door' in t:
                self._doors.setdefault(t['door'], t['id'])

    def path(self, *parts) -> str:
        return os.path.join(self.root, *parts)

    @property
    def levels(self) -> int:
        return int(self.quest.get('levels', 0))

    def text(self, name: str) -> str:
        with open(self.path('text', f'{name}.txt'), encoding='utf-8') as fh:
            return fh.read()

    def script_path(self, level: int) -> str:
        return self.path('levels', 'common.qs') if level == 0 else self.path('levels', str(level), 'script.qs')

    def sprite_dir(self, kind: str) -> str:
        return self.path('sprites', kind)

    # ── items ───────────────────────────────────────────────────────────────
    def item(self, v: int) -> dict:
        return self.items.get(v, {})

    def item_type(self, v: int) -> str:
        """potion, key, chest, teleporter, exit, armour, weapon, launcher, shield, helmet, amulet,
        ammo, treasure; '' for nothing."""
        return self.items.get(v, {}).get('type', '') if v else ''

    def is_quest_item(self, v: int) -> bool:
        return bool(self.items.get(v, {}).get('quest'))

    def fires(self, launcher: int, ammo: int) -> bool:
        """Does this launcher take this ammunition?"""
        group = self.item(ammo).get('ammo')
        return group is not None and group in self.item(launcher).get('fires', ())

    def ammo_id(self, group: str, count: int) -> int:
        """The item that is `count` of this ammunition (0 for none)."""
        if not hasattr(self, '_ammo'):
            self._ammo = {(r['ammo'], r['count']): i for i, r in self.items.items() if r.get('type') == 'ammo'}
        return self._ammo.get((group, count), 0) if count > 0 else 0

    # ── classes and skills ──────────────────────────────────────────────────
    def skill_ids(self, kind: str) -> list:
        """creation()'s lists: the skills (kind 'skill') or the faults (kind 'fault'), in order."""
        return [s['id'] for s in self.skills if s['kind'] == kind]

    def skill(self, sid: str) -> dict:
        return next((s for s in self.skills if s['id'] == sid), {})

    def class_name(self, cls: int) -> str:
        return self.classes.get(cls, {}).get('name', '')

    # ── map tiles ───────────────────────────────────────────────────────────
    def wall(self, v: int) -> dict:
        return self.walls.get(v, {})

    def deco(self, role: str) -> int:
        """The decoration the engine puts down for a role (open_door, blood, bones, ...)."""
        return self._roles.get(role, 0)

    def door(self, kind: str = 'plain') -> int:
        return self._doors.get(kind, 0)

    def map_colour(self, floor: int, wall: int, level: int) -> int:
        """dmap(): the automap colour of a square."""
        best, rank = 2, 0
        for t in (self.floors.get(floor, {}), self.walls.get(wall, {})):
            c = t.get('map_colour_on_level', {}).get(str(level)) or t.get('map_colour')
            if c and c[1] > rank:
                best, rank = c
        return best

    # ── creatures ───────────────────────────────────────────────────────────
    def trait(self, creature: int, name: str, default=None):
        """A creature's trait from creatures.json (docs/QUEST_PACKS.md lists them)."""
        return self.creatures.get(creature, {}).get(name, default)

    def rewards(self) -> dict:
        """monsdeath2()'s rewards per creature: exp, loot, drop_on_level."""
        return {c: {k: r[k] for k in ('exp', 'loot', 'drop_on_level') if k in r} for c, r in self.creatures.items()}

    def names(self) -> dict:
        """(sprite kind, id) -> name, the way the renderer keys its pictures."""
        out = {('object', i): r.get('name', '') for i, r in self.items.items()}
        out.update({('enemy', c): r.get('name', '') for c, r in self.creatures.items()})
        out.update({('spell', s): r.get('name', '') for s, r in self.spells.items()})
        for kind, key in (('floor', 'floors'), ('wall', 'walls'), ('extra', 'decos')):
            out.update({(kind, t['id']): t.get('name', '') for t in self.tiles.get(key, [])})
        return {k: v for k, v in out.items() if v}


class PackSource:
    """Serves the pack under the original's file names, so the engine can ask for 'Talk.dat',
    'Items.dat', 'L00003.dat', 'S000031.dat' or 'GOTH.CHR' as the original did."""

    def __init__(self, pack: Pack):
        self.pack = pack

    def _file(self, name: str) -> str | None:
        n = name.lower()
        p = self.pack
        simple = {'talk.dat': ('text', 'talk.txt'), 'story.dat': ('text', 'stories.txt'),
                  'qs.dat': ('text', 'questions.txt')}
        if n in simple:
            return p.path(*simple[n])
        m = _LEVEL_FILE.match(n)
        if m:
            return p.path('levels', str(int(m.group(1))), 'map.txt')
        m = _SHOP_FILE.match(n)
        if m:
            return p.path('levels', m.group(1), 'shops', f'{m.group(2)}.txt')
        if n.endswith('.chr'):
            return p.path('fonts', name.upper())
        return None

    def _table(self, name: str) -> list[list[int]] | None:
        n, p = name.lower(), self.pack
        if n == 'items.dat':
            return [[i] + [r.get(c, 0) for c in ITEM_COLUMNS] for i, r in p.items.items() if 'req_str' in r]
        if n == 'spells.dat':
            return [[s] + [r.get(c, 0) for c in SPELL_COLUMNS] for s, r in p.spells.items()]
        if n == 'prices.dat':
            return [[i, r['price']] for i, r in p.items.items() if 'price' in r]
        if n == 'monsters.dat':
            return [[c] + [r.get(k, 0) for k in CREATURE_COLUMNS] for c, r in p.creatures.items() if 'life' in r]
        return None

    def exists(self, name: str) -> bool:
        f = self._file(name)
        return (f is not None and os.path.exists(f)) or self._table(name) is not None

    def read(self, name: str) -> bytes:
        f = self._file(name)
        if f is None or not os.path.exists(f):
            raise FileNotFoundError(f'{name} is not in the pack {self.pack.root}')
        with open(f, 'rb') as fh:
            return fh.read()

    def text(self, name: str) -> str:
        return self.read(name).decode('utf-8')

    def numbers(self, name: str) -> list[list[int]]:
        rows = self._table(name)
        if rows is not None:
            return rows
        out = []
        for line in self.text(name).splitlines():
            parts = line.split()
            if parts and not parts[0].startswith('#'):
                out.append([int(v) for v in parts])
        return out
