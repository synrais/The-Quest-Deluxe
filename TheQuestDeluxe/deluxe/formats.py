"""Readers for the data in the original's formats, as a quest pack serves them (deluxe.pack's
PackSource answers under the original's file names: Talk.dat, Items.dat, L00003.dat, ...).

The original's save files keep its light cipher: each byte except space, CR and LF is stored as
(char + 0x51).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

MAP_SIZE = 100

_PLAIN = (0x20, 0x0D, 0x0A)


# ── Cipher ────────────────────────────────────────────────────────────────────

def decode_bytes(raw: bytes) -> str:
    return bytes((c - 0x51) & 0xFF if c not in _PLAIN else c for c in raw).decode('latin-1')


def encode_text(text: str) -> bytes:
    return bytes((c + 0x51) & 0xFF if c not in _PLAIN else c for c in text.encode('latin-1'))


# ── Maps ──────────────────────────────────────────────────────────────────────

@dataclass
class Square:
    """One map tile — mirrors the original C struct `square {t, s, m, i, g, d}`."""
    floor: int = 1   # t: ground graphic (grass, road, carpet…)
    wall: int = 0    # s: >=1 blocks movement; -1 door, -2/-3/-4 locked (gold/red/blue key), -5/-6 fake wall
    mon: int = 0     # m: >0 monster type, <0 NPC type (-5 shopkeeper), <=-100 summoned ally
    item: int = 0    # i: 1-8 potions, 12-14 keys, 15 chest, 999 teleporter, 1000 level exit, >=100 gear
    gold: int = 0    # g: coins lying here
    deco: int = 0    # d: 1 open door, 2 open chest, 3/5/6 bodies, 4 blood

    def copy(self) -> 'Square':
        return Square(self.floor, self.wall, self.mon, self.item, self.gold, self.deco)


def level_filename(level: int) -> str:
    return f'L{level:05d}.dat'


def parse_map(text: str) -> list[list[Square]]:
    """Returns grid[x][y] with 1-based coordinates (index 0 unused), like the original."""
    grid = [[Square() for _ in range(MAP_SIZE + 2)] for _ in range(MAP_SIZE + 2)]
    for line in text.splitlines():
        parts = line.split()
        if len(parts) != 8:
            continue
        x, y, t, s, i, m, g, d = (int(p) for p in parts)
        if x == 0:
            break
        if 1 <= x <= MAP_SIZE and 1 <= y <= MAP_SIZE:
            grid[x][y] = Square(floor=t, wall=s, mon=m, item=i, gold=g, deco=d)
    return grid


def format_map(grid: list[list[Square]]) -> str:
    lines = []
    for x in range(1, MAP_SIZE + 1):
        for y in range(1, MAP_SIZE + 1):
            q = grid[x][y]
            lines.append(f'{x} {y} {q.floor} {q.wall} {q.item} {q.mon} {q.gold} {q.deco}')
    return '\r\n'.join(lines)


# ── Dialogue (Talk.dat) ───────────────────────────────────────────────────────

_TALK_HEAD = re.compile(r'^\s*(-?\d+)\s+(-?\d+)\s+(-?\d+)\s*"(.*)$')


def parse_talk(text: str) -> dict[tuple[int, int, int], str]:
    """Talk.dat: `level npcType msgIndex "line1"` + optional `"line2` ... ending with `;`.
    Level 0 = shared chatter (indices 1-3 picked at random); 10+ are scripted lines."""
    out: dict[tuple[int, int, int], str] = {}
    key, buf = None, []
    for raw in text.splitlines():
        m = _TALK_HEAD.match(raw)
        if m and key is None:
            key = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
            rest = m.group(4)
        elif key is not None:
            rest = raw.strip().lstrip('"')
        else:
            continue
        done = rest.rstrip().endswith(';')
        buf.append(rest.rstrip().rstrip(';').rstrip('"'))
        if done:
            out[key] = '\n'.join(buf)
            key, buf = None, []
    return out


# ── Story (story.dat) ─────────────────────────────────────────────────────────

def parse_story(text: str) -> dict[int, str]:
    """story.dat: header line `id nlines` followed by nlines of text."""
    out: dict[int, str] = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        head = lines[i].split()
        if len(head) == 2 and all(re.fullmatch(r'-?\d+', h) for h in head):
            sid, n = int(head[0]), int(head[1])
            out[sid] = '\n'.join(lines[i + 1:i + 1 + n])
            i += 1 + n
        else:
            i += 1
    return out


# ── Stat tables ───────────────────────────────────────────────────────────────

@dataclass
class MonsterStats:
    """MONSTERS.DAT columns (order used by the game's enemycheck())."""
    type: int
    life: int
    power: int
    atk: int
    defense: int
    warm: int     # weapon (physical) armour
    marm: int     # magic armour
    range: int    # 1 = melee, 9 = ranged
    att: int      # initial attitude/AI state (-2 friendly NPC, 9 hostile …)


def parse_monsters(rows: list[list[int]]) -> dict[int, MonsterStats]:
    return {r[0]: MonsterStats(*r[:9]) for r in rows if len(r) >= 9}


@dataclass
class GameData:
    """Everything the engine needs from the original game, loaded once."""
    src: object = None                            # a deluxe.pack.PackSource
    talk: dict = field(default_factory=dict)
    story: dict = field(default_factory=dict)
    monsters: dict = field(default_factory=dict)
    items: list = field(default_factory=list)
    spells: list = field(default_factory=list)
    prices: list = field(default_factory=list)

    @classmethod
    def load(cls, src=None) -> 'GameData':
        """Everything from a quest pack (deluxe.pack), served under the original's file names."""
        if src is None:
            from .pack import Pack, PackSource
            src = PackSource(Pack())
        gd = cls(src=src)
        gd.talk = parse_talk(src.text('Talk.dat'))
        gd.story = parse_story(src.text('story.dat'))
        gd.monsters = parse_monsters(src.numbers('MONSTERS.DAT'))
        gd.items = src.numbers('Items.dat')
        gd.spells = src.numbers('Spells.dat')
        gd.prices = src.numbers('prices.dat')
        return gd

    def level_count(self) -> int:
        if hasattr(self.src, 'pack'):
            return self.src.pack.levels
        n = 0
        while self.src.exists(level_filename(n + 1)):
            n += 1
        return n

    def load_level(self, level: int) -> list[list[Square]]:
        return parse_map(self.src.text(level_filename(level)))

    def shop(self, level: int, shop: int) -> list[list[int]]:
        return self.src.numbers(f'S0000{level}{shop}.dat')
