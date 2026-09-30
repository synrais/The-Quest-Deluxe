"""The original's save files: data\\saveNN.dat, written by save() and read by load2() (FUNCS.CPP).

A save is a text file of numbers, encoded with the data files' cipher (every byte but space, CR and
LF is stored as byte + 0x51). In order:

    hero.level hero.type  (followed on the same line by the first map square)
    10000 map squares      x y floor wall item mon gold deco   (x-major; the current screen as it
                                                                was on arrival, like map[])
    100 room squares       x y floor wall item mon gold deco   (the current screen, live)
    X Y ax ay
    hero: mlife life mmana mana bstr bintl bdex bacc rep exper
    inv:  bkey rkey ykey coins rose red purple blue yellow white cyan black
    100 creatures, one number per line: type x y life mlife atk def power range warm marm att
    bag cells [12..16][2..12], book cells [13..16][2..11], spells 1..20 (one per line)
    carta [1..10][1..10], each followed by a blank line
    fkey 1..9, each followed by two blank lines
    skill: amb bar sch mem mar cow hon ras  (then a blank line)
    st: mons ems killer armboost powboost Shield level mission1
    hero.invisible hero.poisoned st.mission2 st.fShield
    st.p1 st.p2 st.p3

The derived stats (dex, acc, intl, str, def, atk, power, warm, marm) are not saved; statusupdate()
rebuilds them. Because code() copies the file one character at a time until the end-of-file flag
is set, the last character (a newline) is written twice, so every save ends with a blank line.

newsave() gives each new game the first free slot 01..20 and reserves it with a file holding -1.
TheQuestClassic/The Quest Deluxe adds one thing: a game that goes past what the original's structures hold (more than
20 spells, potions 9 and 10, a pack's own key colours ...) keeps the rest in a last line,

    DELUXE {"spells": [...], "book": [...], "more": {...}}

written only when there is something to keep, so a Quest I game saves exactly as the original does.
The original's load2() reads a fixed count of numbers and never gets that far, and neither does
from_text() below: the classic part of such a save still loads in both.

TheQuestClassic/tools/re/verify_saves.py (QUEST_ENGINE=deluxe) checks this module against the exe's own save() and load2().
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

import json

from .formats import decode_bytes, encode_text

SLOTS = 20
MAP = 100

HERO_SAVED = ['mlife', 'life', 'mmana', 'mana', 'bstr', 'bintl', 'bdex', 'bacc', 'rep', 'exper']
INV_SAVED = ['bkey', 'rkey', 'ykey', 'coins', 'rose', 'red', 'purple', 'blue', 'yellow', 'white', 'cyan', 'black']
SKILLS = ['amb', 'bar', 'sch', 'mem', 'mar', 'cow', 'hon', 'ras']
ST_SAVED = ['mons', 'ems', 'killer', 'armboost', 'powboost', 'Shield', 'level', 'mission1']
ENEMY = ['type', 'x', 'y', 'life', 'mlife', 'atk', 'defense', 'power', 'range', 'warm', 'marm', 'att']
BAG_CELLS = [(i, ii) for i in range(12, 17) for ii in range(2, 13)]
BOOK_CELLS = [(i, ii) for i in range(13, 17) for ii in range(2, 12)]


@dataclass
class SaveData:
    """Everything a save file holds, in the original's terms (screen coordinates, matrices)."""
    hero: dict = field(default_factory=dict)          # HERO_SAVED + level, type, invisible, poisoned
    inv: dict = field(default_factory=dict)
    skill: dict = field(default_factory=dict)
    st: dict = field(default_factory=dict)            # ST_SAVED + mission2, fShield, p1, p2, p3
    X: int = 0
    Y: int = 0
    ax: int = 0
    ay: int = 0
    map: dict = field(default_factory=dict)           # (x, y) -> (floor, wall, item, mon, gold, deco)
    room: dict = field(default_factory=dict)          # (i, ii) 1..10 -> the same
    enemies: list = field(default_factory=list)       # up to 100 dicts of ENEMY (screen coordinates)
    bag: dict = field(default_factory=dict)           # (i, ii) -> item
    book: dict = field(default_factory=dict)          # (i, ii) -> spell
    spells: list = field(default_factory=lambda: [0] * 21)
    carta: dict = field(default_factory=dict)         # (i, ii) 1..10 -> 0/1
    fkey: list = field(default_factory=lambda: [0] * 10)
    extra: dict = field(default_factory=dict)         # The Quest Deluxe's block (see the top of this file)


EXTRA = 'DELUXE '


# ── writing: save() ─────────────────────────────────────────────────────────────
def to_text(d: SaveData) -> str:
    out = [f"{d.hero.get('level', 0)} {d.hero.get('type', 0)} "]
    sq = lambda t: ' '.join(str(v) for v in t)
    for x in range(1, MAP + 1):
        for y in range(1, MAP + 1):
            out.append(f'{x} {y} {sq(d.map.get((x, y), (0,) * 6))}\n')
    for i in range(1, 11):
        for ii in range(1, 11):
            out.append(f'{i} {ii} {sq(d.room.get((i, ii), (0,) * 6))}\n')
    out.append(f'{d.X} {d.Y} {d.ax} {d.ay}\n')
    out.append(' '.join(str(d.hero.get(k, 0)) for k in HERO_SAVED) + '\n')
    out.append(' '.join(str(d.inv.get(k, 0)) for k in INV_SAVED) + '\n')
    for k in range(100):
        e = d.enemies[k] if k < len(d.enemies) else {}
        out.extend(f'{e.get(f, 0)}\n' for f in ENEMY)
    out.extend(f'{d.bag.get(c, 0)}\n' for c in BAG_CELLS)
    out.extend(f'{d.book.get(c, 0)}\n' for c in BOOK_CELLS)
    out.extend(f'{d.spells[i]}\n' for i in range(1, 21))
    out.extend(f'{d.carta.get((i, ii), 0)}\n\n' for i in range(1, 11) for ii in range(1, 11))
    out.extend(f'{d.fkey[i]}\n\n\n' for i in range(1, 10))
    out.append(' '.join(str(d.skill.get(k, 0)) for k in SKILLS) + '\n\n')
    out.append(' '.join(str(d.st.get(k, 0)) for k in ST_SAVED) + '\n')
    out.append(f"{d.hero.get('invisible', 0)} {d.hero.get('poisoned', 0)} {d.st.get('mission2', 0)} "
               f"{d.st.get('fShield', 0)}\n")
    out.append(f"{d.st.get('p1', 0)} {d.st.get('p2', 0)} {d.st.get('p3', 0)}\n")
    if d.extra:
        out.append(EXTRA + json.dumps(d.extra, sort_keys=True, separators=(',', ':'), ensure_ascii=True) + '\n')
    return ''.join(out)


def to_bytes(d: SaveData) -> bytes:
    """The file exactly as the original leaves it: DOS line ends, encoded, last newline doubled."""
    text = to_text(d)
    return encode_text((text + text[-1:]).replace('\n', '\r\n'))


# ── reading: load2() ────────────────────────────────────────────────────────────
def from_text(text: str) -> SaveData:
    """load2(): fscanf %d after %d, so only the order of the numbers matters, not the lines. Then The
    Quest Deluxe's block, if there is one."""
    extra = {}
    at = text.find('\n' + EXTRA)
    if at >= 0:
        line = text[at + 1 + len(EXTRA):].split('\n', 1)[0]
        try:
            extra = json.loads(line)
        except ValueError:
            extra = {}
        text = text[:at + 1]
    nums = iter(int(t) for t in text.split())
    nxt = lambda: next(nums, 0)
    d = SaveData()
    d.hero['level'], d.hero['type'] = nxt(), nxt()
    for _ in range(10000):                       # map[aa][bb] = ..., until a row starts with 0
        aa, bb, *sq = [nxt() for _ in range(8)]
        if aa == 0:
            break
        d.map[(aa, bb)] = tuple(sq)
    for _ in range(100):
        aa, bb, *sq = [nxt() for _ in range(8)]
        if aa == 0:
            break
        d.room[(aa, bb)] = tuple(sq)
    d.X, d.Y, d.ax, d.ay = nxt(), nxt(), nxt(), nxt()
    for k in HERO_SAVED:
        d.hero[k] = nxt()
    for k in INV_SAVED:
        d.inv[k] = nxt()
    d.enemies = [{f: nxt() for f in ENEMY} for _ in range(100)]
    d.bag = {c: nxt() for c in BAG_CELLS}
    d.book = {c: nxt() for c in BOOK_CELLS}
    d.spells = [0] + [nxt() for _ in range(20)]
    d.carta = {(i, ii): nxt() for i in range(1, 11) for ii in range(1, 11)}
    d.fkey = [0] + [nxt() for _ in range(9)]
    d.skill = {k: nxt() for k in SKILLS}
    d.st = {k: nxt() for k in ST_SAVED}
    d.hero['invisible'], d.hero['poisoned'] = nxt(), nxt()
    d.st['mission2'], d.st['fShield'] = nxt(), nxt()
    d.st['p1'], d.st['p2'], d.st['p3'] = nxt(), nxt(), nxt()
    d.extra = extra if isinstance(extra, dict) else {}
    return d


def from_bytes(raw: bytes) -> SaveData:
    return from_text(decode_bytes(raw))


# ── the slots ───────────────────────────────────────────────────────────────────
class Slots:
    """data\\save01.dat .. save20.dat. Names are matched without regard to case (the original
    runs on DOS), so an existing SAVE01.DAT is used as is."""

    def __init__(self, data_dir: str):
        self.dir = data_dir

    def path(self, n: int) -> str:
        want = f'save{n:02d}.dat'
        if os.path.isdir(self.dir):
            for f in os.listdir(self.dir):
                if f.lower() == want:
                    return os.path.join(self.dir, f)
        return os.path.join(self.dir, want)

    def read_raw(self, n: int) -> bytes | None:
        try:
            with open(self.path(n), 'rb') as fh:
                return fh.read()
        except OSError:
            return None

    def reserved(self, raw: bytes) -> bool:
        """newsave()'s placeholder: the file holds -1 (written plainly, not encoded)."""
        return raw.split()[:1] == [b'-1']

    def header(self, n: int):
        """loadscreen(): (level, type) from the start of the file, or None if the slot is empty or
        only reserved."""
        raw = self.read_raw(n)
        if raw is None or self.reserved(raw):
            return None
        nums = decode_bytes(raw[:10]).split()
        try:
            return int(nums[0]), int(nums[1])
        except (IndexError, ValueError):
            return None

    def listing(self) -> list[tuple[int, int, int]]:
        """loadscreen()'s list: slots 1, 2, ... up to the first one that is missing or reserved."""
        out = []
        for n in range(1, SLOTS + 1):
            h = self.header(n)
            if h is None:
                break
            out.append((n, *h))
        return out

    def new(self) -> int:
        """newsave(): the first slot with no file (a reserved one is reused); 0 when all 20 are taken."""
        for n in range(1, SLOTS + 1):
            raw = self.read_raw(n)
            if raw is not None and self.reserved(raw):
                os.remove(self.path(n))
                raw = None
            if raw is None:
                os.makedirs(self.dir, exist_ok=True)
                with open(self.path(n), 'wb') as fh:
                    fh.write(b'-1')
                return n
        return 0

    def write(self, n: int, d: SaveData):
        """save(): written to data\\delete.dat first, then renamed over the slot."""
        os.makedirs(self.dir, exist_ok=True)
        tmp = os.path.join(self.dir, 'delete.dat')
        with open(tmp, 'wb') as fh:
            fh.write(to_bytes(d))
        os.replace(tmp, self.path(n))

    def read(self, n: int) -> SaveData | None:
        raw = self.read_raw(n)
        if raw is None or self.reserved(raw):
            return None
        return from_bytes(raw)
