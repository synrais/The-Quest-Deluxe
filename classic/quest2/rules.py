"""Game rules ported from the original executable.

Each function names the original routine it reproduces (see docs/REVERSE_ENGINEERING.md).
`random(n)` is Borland's macro: an integer in [0, n).
"""
from __future__ import annotations

import math
import time as _time

from .state import (Player, Status, Enemy, SLOT_WEAPON, SLOT_OFFHAND, SLOT_HELMET, SLOT_ARMOR,
                    SLOT_AMULET, IT_ATK, IT_DEF, IT_WARM, IT_MARM, IT_STR, IT_INT, IT_POWER, IT_KIND,
                    IT_DEX, IT_ACC, KIND_RANGED)

LOW_HEALTH = 0.3   # DS:01D6 — cowardice threshold and "leave blood" threshold


_seed = [0]


def srand(seed: int):
    """Borland's srand(); the game seeds it from the clock (randomize())."""
    _seed[0] = seed & 0xFFFFFFFF


def rand() -> int:
    """Borland C's rand(): seed = seed * 22695477 + 1, result = bits 16-30 (checked against the exe)."""
    _seed[0] = (_seed[0] * 22695477 + 1) & 0xFFFFFFFF
    return (_seed[0] >> 16) & 0x7FFF


def random(n: int) -> int:
    """Borland's random(n) macro: rand() * n / 32768 in long arithmetic."""
    return rand() * n // 0x8000 if n > 0 else 0


def spread(power: int) -> int:
    """power ± power/3, as herohit/monhit/hurt compute it."""
    third = power // 3 if power >= 0 else -((-power) // 3)
    return power + random(2 * third + 1) - third


def distance(dx: int, dy: int) -> int:
    """sqrt(dx²+dy²) rounded half-up, as main2 computes ranged distance."""
    d = math.sqrt(dx * dx + dy * dy)
    return int(d) + (1 if d - int(d) >= 0.5 else 0)


class ItemTable:
    """Items.dat rows keyed by id (itemtell)."""

    def __init__(self, rows: list[list[int]]):
        self.rows = {r[0]: r for r in rows if r}

    def tell(self, item_id: int, col: int) -> int:
        r = self.rows.get(item_id)
        return r[col] if r and col < len(r) else 0


class SpellTable(ItemTable):
    pass


def status_update(p: Player, st: Status, items: ItemTable) -> None:
    """statusupdate(): recompute derived stats from base stats + equipment."""
    h, sk, it = p.hero, p.skill, items.tell
    wep, off, helm, arm, amu = (p.item(s) for s in (SLOT_WEAPON, SLOT_OFFHAND, SLOT_HELMET, SLOT_ARMOR, SLOT_AMULET))

    h.dex = it(amu, IT_DEX) + h.bdex + it(helm, IT_DEX)
    h.acc = it(amu, IT_ACC) + h.bacc
    h.str = it(amu, IT_STR) + h.bstr
    h.intl = it(amu, IT_INT) + h.bintl + it(helm, IT_INT)

    if it(wep, IT_KIND) != KIND_RANGED:
        h.atk = it(wep, IT_ATK) + h.dex + it(amu, IT_ATK) + 35
        if 300 < off < 400:                      # shield
            h.atk += it(off, IT_ATK)
    else:
        h.atk = it(wep, IT_ATK) + 2 * h.acc + it(amu, IT_ATK) + 15
        if sk.mar == 1:
            h.atk += 30
    if sk.cow == 1 and h.mlife and h.life / h.mlife <= LOW_HEALTH:
        h.atk = int(h.atk / 2)

    h.defense = it(off, IT_DEF) + h.dex + it(amu, IT_DEF) + 10
    if sk.amb == 1:
        h.defense += it(wep, IT_DEF)

    h.warm = it(arm, IT_WARM) + it(helm, IT_WARM) + it(amu, IT_WARM) + it(wep, IT_WARM)
    h.marm = it(arm, IT_MARM) + it(helm, IT_MARM) + it(amu, IT_MARM) + it(wep, IT_MARM)
    if sk.amb == 1:
        h.warm += it(off, IT_WARM)
        h.marm += it(off, IT_MARM)
    if st.armboost > 0:
        h.warm *= 2
        h.marm *= 2

    h.power = it(wep, IT_POWER)
    ranged = it(wep, IT_KIND) == KIND_RANGED
    if ranged and 640 < off < 661 and wep not in (230, 233):   # poison arrows with a bow
        h.power *= 2
    if not ranged and amu in (503, 507, 511):
        h.power += it(amu, IT_POWER)
    if ranged and amu == 504:
        h.power += it(amu, IT_POWER)
    if st.powboost > 0:
        h.power *= 2


def hero_hit(p: Player, e: Enemy, items: ItemTable) -> int:
    """herohit(): melee damage dealt by the hero to enemy e (0 = miss)."""
    h = p.hero
    chance = h.atk - e.defense
    if random(100) + 1 > chance:
        return 0
    power = spread(h.power)
    if items.tell(p.item(SLOT_WEAPON), IT_KIND) != 3:     # kind 3 = magic weapon, ignores armour
        power -= e.warm
    return power


SHIELDED = -1000     # mon_hit(): the blow was absorbed by the Shield spell (monhit() beeps)


def mon_hit(e: Enemy, p: Player, st: Status, spells: SpellTable) -> int:
    """monhit(): melee damage dealt by enemy e to the hero (0 = miss, SHIELDED = absorbed)."""
    h = p.hero
    if random(100) + 1 > e.atk - h.defense:
        return 0
    power = spread(e.power)
    if st.Shield > 0 and spells.tell(5, 4) >= power:
        return SHIELDED
    power -= h.marm if e.type in (23, 24, 25) else h.warm
    return power


def hurt_amount(dmg: int, target_warm: int, target_marm: int, kind: int) -> int:
    """Damage part of hurt(): kind 0 = physical (weapon armour), 1 = magic (magic armour), 2/3 = unarmoured."""
    dam = spread(dmg)
    if kind == 0:
        dam -= target_warm
    elif kind == 1:
        dam -= target_marm
    return max(0, dam)


# ── Spells.dat columns (spelltell) ────────────────────────────────────────────
SP_INT, SP_MANA, SP_RANGE, SP_POWER, SP_DURATION = 1, 2, 3, 4, 5
SPELL_NAMES = {1: 'Heal', 2: 'Flame', 3: 'Teleport', 4: 'Shield', 5: 'Ring of Ice', 6: 'Black Ward',
               7: 'Invisibility', 8: 'Summon Skeleton', 9: 'Inferno', 10: 'Restore', 11: 'Life Drain',
               12: 'Thunder Bolt', 13: 'Shield of Fire', 14: 'Deteriorate', 15: 'Summon Stone Knight',
               16: 'Earthquake', 17: 'Cure', 18: 'Summon Scorpion', 19: 'Meteor', 20: 'Dark Hour'}

# Items.dat weapon kinds (column 10)
KIND_NORMAL, KIND_DOUBLE, KIND_PARRY, KIND_PIERCE, KIND_RANGED_, KIND_TWOHAND, KIND_TWOHAND_PARRY = range(7)


def item_slot(item_id: int):
    """Which equipment slot an item id belongs to (inventory() uses the id's hundreds)."""
    from .state import SLOT_ARMOR, SLOT_WEAPON, SLOT_OFFHAND, SLOT_HELMET, SLOT_AMULET
    if 100 < item_id < 200:
        return SLOT_ARMOR
    if 200 < item_id < 300:
        return SLOT_WEAPON
    if 300 < item_id < 400:
        return SLOT_OFFHAND
    if 400 < item_id < 500:
        return SLOT_HELMET
    if 500 < item_id < 600:
        return SLOT_AMULET
    if 600 < item_id < 700:
        return SLOT_OFFHAND          # ammunition goes in the off hand
    return None


def ammo_ok(weapon: int, ammo: int) -> bool:
    """Which ammunition a launcher accepts (main2, Space/Tab handler)."""
    b = weapon - 230
    if b > -1 and 600 + 20 * b < ammo < 641 + 20 * b:
        return True
    if weapon == 232 and 620 < ammo < 661:
        return True
    if weapon == 233 and 660 < ammo < 681:
        return True
    return False


def jumble() -> tuple[int, int, int]:
    """jumble(): the three automatic stat points for the next level-up (1 str, 2 int, 3 dex, 4 acc)."""
    while True:
        a, b, c = random(4) + 1, random(4) + 1, random(4) + 1
        if not (a == b == c):
            return a, b, c


CLASS_GROWTH = {1: (7, 3), 2: (1, 5), 3: (4, 4), 4: (3, 3)}   # (max life, max mana) per level
INNATE_SKILL = {1: 'amb', 2: 'mem', 3: 'mar', 4: 'sch'}


def apply_stat_point(h, which: int) -> None:
    if which == 1:
        h.bstr += 1
        h.mlife += 1
    elif which == 2:
        h.bintl += 1
        h.mmana += 1
    elif which == 3:
        h.bdex += 1
    elif which == 4:
        h.bacc += 1


def level_up_auto(p, st) -> list[int]:
    """First half of levelup(): level, exp target, class growth and the automatic points."""
    h = p.hero
    h.level += 1
    h.exper = 300 if h.level == 2 else h.level * 200
    l, m = CLASS_GROWTH.get(h.type, (0, 0))
    h.mlife += l
    h.mmana += m
    gained = []
    for n, which in enumerate((st.p1, st.p2, st.p3)):
        if n == 0 and p.skill.sch == 1 and h.level % 2 == 0:
            continue                     # Scholar: this point is chosen by hand instead
        apply_stat_point(h, which)
        gained.append(which)
    st.p1, st.p2, st.p3 = jumble()
    return gained


def choices_this_level(p) -> int:
    return 2 if p.skill.sch == 1 and p.hero.level % 2 == 0 else 1


def reclassify(p) -> int | None:
    """End of levelup(): the class follows the stats; innate skills swap. Returns the new class if it changed."""
    h, sk = p.hero, p.skill
    if h.bdex + h.bacc > h.bstr + h.bintl:
        new = 3
    else:
        new = 4
        if h.bstr > h.bintl + 3:
            new = 1
        if h.bintl > h.bstr + 3:
            new = 2
    if new == h.type:
        return None
    gain, lose = INNATE_SKILL[new], INNATE_SKILL[h.type]
    if getattr(sk, gain) == 0:
        setattr(sk, gain, 1)
        setattr(sk, lose, 0)
    h.type = new
    return new


srand(int(_time.time()))              # randomize()
