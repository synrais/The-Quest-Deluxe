"""Game state, mirroring the original C structs recovered from the debug symbols.

Field names follow the original source (heroo, inve, skills, statuss, monsters)
so the reverse-engineering notes in docs/ map one-to-one onto this code.
"""
from __future__ import annotations

from dataclasses import dataclass, field

KNIGHT, MAGE, ROGUE, MONK = 1, 2, 3, 4
CLASS_NAMES = {KNIGHT: 'Knight', MAGE: 'Mage', ROGUE: 'Rogue', MONK: 'Monk'}

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

    def item(self, slot) -> int:
        return self.bag.get(slot, 0)

    def free_backpack_slot(self):
        return next((s for s in BACKPACK if not self.bag.get(s)), None)


CLASS_START = {
    #          mlife mmana str int dex acc
    KNIGHT: (50, 0, 20, 10, 10, 10),
    MAGE: (20, 30, 10, 20, 10, 10),
    ROGUE: (35, 15, 10, 10, 15, 15),
    MONK: (30, 20, 15, 15, 10, 10),
}


# creation(): the extra skill picked from the list (1 Bargaining, 2 Ambidexterity, 3 Memorization,
# 4 Marksmanship, 5 Scholar) and the fault (1 Cowardice, 2 Rashness, 3 Honor), as Skills fields.
SKILL_CHOICES = {1: 'bar', 2: 'amb', 3: 'mem', 4: 'mar', 5: 'sch'}
FAULT_CHOICES = {1: 'cow', 2: 'ras', 3: 'hon'}
CLASS_SKILL = {1: 'amb', 2: 'mem', 3: 'mar', 4: 'sch'}      # KNIGHT, MAGE, ROGUE, MONK get this one free


def new_player(cls: int, skill: int = 0, fault: int = 0) -> Player:
    """Starting character, exactly as creation() and newgame() set it up."""
    p = Player()
    if skill in SKILL_CHOICES:
        setattr(p.skill, SKILL_CHOICES[skill], 1)
    setattr(p.skill, CLASS_SKILL[cls], 1)
    if fault in FAULT_CHOICES:
        setattr(p.skill, FAULT_CHOICES[fault], 1)
    p.fkey = list(range(10))                     # newgame(): F1..F9 start bound to spells 1..9
    ml, mm, s, i, d, a = CLASS_START[cls]
    h = p.hero
    h.mlife = h.life = ml
    h.mmana = h.mana = mm
    h.bstr, h.bintl, h.bdex, h.bacc = s, i, d, a
    h.type, h.level, h.rep, h.exper, h.invisible, h.poisoned = cls, 1, 0, 100, -1, 0
    p.inv.white = 1
    p.bag[SLOT_WEAPON] = 201                      # club
    if cls == KNIGHT:
        p.bag[SLOT_OFFHAND] = 301                 # buckler
    elif cls == MAGE:
        p.spells[1] = p.spells[2] = p.spells[3] = 1   # heal, flame, teleport
        p.book[0], p.book[1], p.book[2] = 1, 2, 3
    elif cls == ROGUE:
        p.bag[(12, 8)] = 230                      # sling
        p.bag[(13, 8)] = 620                      # 20 pebbles
    elif cls == MONK:
        p.spells[1] = 1
        p.book[0] = 1
        p.bag[SLOT_AMULET] = 502                  # stoic necklace
    return p
