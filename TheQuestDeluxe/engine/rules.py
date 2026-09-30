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

    def __init__(self, rows: list[list[int]], pack=None):
        self.rows = {r[0]: r for r in rows if r}
        self.pack = pack

    def tell(self, item_id: int, col: int) -> int:
        r = self.rows.get(item_id)
        return r[col] if r and col < len(r) else 0


class SpellTable(ItemTable):
    pass


def status_update(p: Player, st: Status, items: ItemTable) -> None:
    """statusupdate(): recompute derived stats from base stats + equipment."""
    h, sk, it, pk = p.hero, p.skill, items.tell, items.pack
    wep, off, helm, arm, amu = (p.item(s) for s in (SLOT_WEAPON, SLOT_OFFHAND, SLOT_HELMET, SLOT_ARMOR, SLOT_AMULET))

    h.dex = it(amu, IT_DEX) + h.bdex + it(helm, IT_DEX)
    h.acc = it(amu, IT_ACC) + h.bacc
    h.str = it(amu, IT_STR) + h.bstr
    h.intl = it(amu, IT_INT) + h.bintl + it(helm, IT_INT)

    if it(wep, IT_KIND) != KIND_RANGED:
        h.atk = it(wep, IT_ATK) + h.dex + it(amu, IT_ATK) + 35
        if pk.item_type(off) == 'shield':
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
    if ranged and pk.item(off).get('power_x2') and not pk.item(wep).get('no_ammo_bonus'):
        h.power *= 2                             # poisoned arrows with a bow
    if pk.item(amu).get('power_bonus') == ('ranged' if ranged else 'melee'):
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


def mon_hit(e: Enemy, p: Player, st: Status, spells: SpellTable, pack) -> int:
    """monhit(): melee damage dealt by enemy e to the hero (0 = miss, SHIELDED = absorbed)."""
    h = p.hero
    if random(100) + 1 > e.atk - h.defense:
        return 0
    power = spread(e.power)
    if st.Shield > 0 and pack.shield_absorbs() >= power:
        return SHIELDED
    power -= h.marm if pack.trait(e.type, 'magic_attack') else h.warm
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

# Items.dat weapon kinds (column 10)
KIND_NORMAL, KIND_DOUBLE, KIND_PARRY, KIND_PIERCE, KIND_RANGED_, KIND_TWOHAND, KIND_TWOHAND_PARRY = range(7)


def jumble() -> tuple[int, int, int]:
    """jumble(): the three automatic stat points for the next level-up (1 str, 2 int, 3 dex, 4 acc)."""
    while True:
        a, b, c = random(4) + 1, random(4) + 1, random(4) + 1
        if not (a == b == c):
            return a, b, c




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


def level_up_auto(p, st, pack) -> list[int]:
    """First half of levelup(): level, exp target, class growth and the automatic points."""
    h = p.hero
    h.level += 1
    h.exper = 300 if h.level == 2 else h.level * 200
    l, m = pack.classes.get(h.type, {}).get('growth', (0, 0))
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


def reclassify(p, pack) -> int | None:
    """End of levelup(): the class follows the stats; innate skills swap. Returns the new class if it
    changed. Quest I's rule, between its four classes; a pack turns it off with "reclass": false."""
    h, sk = p.hero, p.skill
    if not pack.quest.get('reclass'):
        return None
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
    gain, lose = pack.classes[new]['skill'], pack.classes[h.type]['skill']
    if getattr(sk, gain) == 0:
        setattr(sk, gain, 1)
        setattr(sk, lose, 0)
    h.type = new
    return new


srand(int(_time.time()))              # randomize()
