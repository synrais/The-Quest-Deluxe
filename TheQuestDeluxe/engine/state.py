"""Game state, mirroring the original C structs recovered from the debug symbols.

Field names follow the original source (heroo, inve, skills, statuss, monsters)
so the reverse-engineering notes in docs/ map one-to-one onto this code.
"""
from __future__ import annotations

from dataclasses import dataclass, field

KNIGHT, MAGE, ROGUE, MONK = 1, 2, 3, 4           # Quest I's classes (the pack's classes.json)

# Equipment slots are cells of the original 17x13 `bag` matrix.
SLOT_WEAPON = (12, 4)
SLOT_OFFHAND = (16, 4)   # shield, or second weapon with Ambidexterity
SLOT_HELMET = (14, 2)
SLOT_ARMOR = (14, 4)
SLOT_AMULET = (14, 6)
BACKPACK = [(x, y) for y in range(8, 12) for x in range(12, 16)]   # 16 cells

# Items.dat columns (itemtell(id, col))
IT_REQ_STR, IT_REQ_INT, IT_ATK, IT_DEF, IT_WARM, IT_MARM, IT_STR, IT_INT, IT_POWER, IT_KIND, IT_DEX, IT_ACC = range(1, 13)
KIND_RANGED = 4


@dataclass
class Hero:
    mlife: int = 0
    life: int = 0
    mmana: int = 0
    mana: int = 0
    bstr: int = 0
    bintl: int = 0
    bdex: int = 0
    bacc: int = 0
    dex: int = 0
    acc: int = 0
    intl: int = 0
    str: int = 0
    defense: int = 0
    atk: int = 0
    rep: int = 0
    power: int = 0
    warm: int = 0
    marm: int = 0
    level: int = 1
    exper: int = 100      # experience still needed for the next level
    type: int = KNIGHT
    invisible: int = -1
    poisoned: int = 0


@dataclass
class Inventory:
    bkey: int = 0
    rkey: int = 0
    ykey: int = 0
    coins: int = 0
    rose: int = 0     # potion 1: half life
    red: int = 0      # potion 2: full life
    purple: int = 0   # potion 3: half mana
    blue: int = 0     # potion 4: full mana
    white: int = 0    # potion 6: full restoration
    cyan: int = 0     # potion 7: cure poison
    yellow: int = 0   # potion 5: half restoration
    black: int = 0    # potion 8: berserker


POTION_FIELDS = {1: 'rose', 2: 'red', 3: 'purple', 4: 'blue', 5: 'yellow', 6: 'white', 7: 'cyan', 8: 'black'}


def potions(p: 'Player', n: int) -> int:
    """How many of potion n the hero has: 1-8 the original's, 9 and 10 The Quest Deluxe's."""
    if n in POTION_FIELDS:
        return getattr(p.inv, POTION_FIELDS[n])
    return p.more.get('potions', {}).get(str(n), 0)


def add_potions(p: 'Player', n: int, count: int = 1):
    if n in POTION_FIELDS:
        setattr(p.inv, POTION_FIELDS[n], getattr(p.inv, POTION_FIELDS[n]) + count)
    else:
        held = p.more.setdefault('potions', {})
        held[str(n)] = held.get(str(n), 0) + count
        if not held[str(n)]:
            del held[str(n)]


@dataclass
class Skills:
    amb: int = 0   # Ambidexterity
    bar: int = 0   # Bargaining
    sch: int = 0   # Scholar
    mem: int = 0   # Memorisation
    mar: int = 0   # Marksmanship
    cow: int = 0   # (fault) Cowardice
    hon: int = 0   # (fault) Honor
    ras: int = 0   # (fault) Rashness


@dataclass
class Status:
    mons: int = 0       # number of enemies in the current screen
    ems: int = 0        # number of hostile enemies in the current screen
    killer: int = 0     # killer switch (attack NPCs you walk into)
    armboost: int = 0
    powboost: int = 0
    Shield: int = -1
    fShield: int = -1
    level: int = 0
    mission1: int = 0   # per-level quest progress counters
    mission2: int = 0
    saveslot: int = 0
    p1: int = 0
    p2: int = 0
    p3: int = 0


@dataclass
class Enemy:
    """One creature on the current screen (original `monsters` struct)."""
    type: int
    x: int
    y: int
    life: int = 0
    mlife: int = 0
    atk: int = 0
    defense: int = 0
    power: int = 0
    range: int = 1
    warm: int = 0
    marm: int = 0
    att: int = 0        # attitude / AI state, see ATT_* below
    moved: bool = False  # original `move[i]`: already acted this turn

    @property
    def is_npc(self) -> bool:
        return -100 < self.type < 0

    @property
    def is_summon(self) -> bool:
        return self.type <= -100


# Enemy attitude (`att`) values, as used by main2/monsmove:
#   > 0   hostile; the value is also its sight radius (+range-1). 9 = normal, 8 = sees invisible
#   -1    neutral: wanders, turns hostile when hit
#   -2    peaceful NPC (stands still)
#   -3    summoned ally following the hero
#   -4    caster that acts every turn but never melees (cleric, necromancer)
#   -5    hostile but can't see the invisible hero
#   < -10 frozen by Ring of Ice: counts up each turn, becomes 9 at -10
ATT_HOSTILE, ATT_NEUTRAL, ATT_PEACEFUL, ATT_FOLLOWER, ATT_CASTER, ATT_BLIND = 9, -1, -2, -3, -4, -5


@dataclass
class Player:
    hero: Hero = field(default_factory=Hero)
    inv: Inventory = field(default_factory=Inventory)
    skill: Skills = field(default_factory=Skills)
    bag: dict = field(default_factory=dict)       # (col,row) -> item id
    spells: list = field(default_factory=lambda: [0] * 21)   # 0 unknown, 1 known, >1 level-ups left to learn
    book: list = field(default_factory=lambda: [0] * 20)     # spellbook pages: slots 0-9 left column, 10-19 right
    fkey: list = field(default_factory=lambda: [0] * 10)     # F1..F9 -> spell id (index 1..9)
    X: int = 5          # absolute map position 1..100
    Y: int = 5
    # The Quest Deluxe's own state, past what the original's structures hold (potions 9 and 10, key
    # colours of a pack's own ...). spells and book above may also grow past 20. Saved in the save
    # file's DELUXE block (savefile.py).
    more: dict = field(default_factory=dict)

    def item(self, slot) -> int:
        return self.bag.get(slot, 0)

    def fit_spells(self, count: int):
        """Room for spells 1..count, and a spell book of 20-spell pages for them (Quest I: 20 and one
        page, the original's)."""
        if len(self.spells) < count + 1:
            self.spells += [0] * (count + 1 - len(self.spells))
        pages = -(-count // 20)
        if len(self.book) < pages * 20:
            self.book += [0] * (pages * 20 - len(self.book))

    def free_backpack_slot(self):
        return next((s for s in BACKPACK if not self.bag.get(s)), None)


def new_player(cls: int, skill: int = 0, fault: int = 0, pack=None) -> Player:
    """Starting character, exactly as creation() and newgame() set it up, from the pack's
    classes.json, skills.json and quest.json. skill / fault are positions (1-based) in creation()'s
    lists; 0 is none."""
    from .pack import default_pack
    pack = pack or default_pack()
    c = pack.classes[cls]
    p = Player()
    p.fit_spells(pack.spell_count())
    skills, faults = pack.skill_ids('skill'), pack.skill_ids('fault')
    if 1 <= skill <= len(skills):
        setattr(p.skill, skills[skill - 1], 1)
    setattr(p.skill, c['skill'], 1)
    if 1 <= fault <= len(faults):
        setattr(p.skill, faults[fault - 1], 1)
    p.fkey = list(range(10))                     # newgame(): F1..F9 start bound to spells 1..9
    h = p.hero
    h.mlife = h.life = c['life']
    h.mmana = h.mana = c['mana']
    h.bstr, h.bintl, h.bdex, h.bacc = c['str'], c['int'], c['dex'], c['acc']
    h.type, h.level, h.rep, h.exper, h.invisible, h.poisoned = cls, 1, 0, 100, -1, 0
    for n, count in pack.quest.get('start_potions', {}).items():
        if int(n) in POTION_FIELDS:
            setattr(p.inv, POTION_FIELDS[int(n)], count)
        elif int(n) in pack.extra_potions():
            add_potions(p, int(n), count)
    for cell, it in c.get('bag', {}).items():
        p.bag[tuple(int(v) for v in cell.split(','))] = it
    for n, s in enumerate(c.get('spells', [])):
        p.spells[s] = 1
        p.book[n] = s
    return p
