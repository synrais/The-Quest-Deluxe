"""How a fight between a hero and a creature goes, worked out from the pack's own numbers with the game's own rules.

The hero's stats come from his class, his level and what he wears (engine/rules.status_update), the damage rolls are
power +- a third (rules.spread), a blow hits when attack - defence beats a roll of 1 to 100, and weapon armour (or magic
armour for magic blows) is taken off the damage. A creature with no melee attack (attack 0: a caster) always hits with its
spell and is stopped by magic armour.

Nothing here knows about windows.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

SLOTS = {'weapon': '12,4', 'offhand': '16,4', 'helmet': '14,2', 'armour': '14,4', 'amulet': '14,6'}
SLOT_TYPES = {'weapon': ('weapon', 'launcher'), 'offhand': ('shield', 'weapon'), 'helmet': ('helmet',), 'armour': ('armour',),
              'amulet': ('amulet',)}
GAIN = 0.75                                    # each level gives 3 random points: on average this many to each of the 4 stats


@dataclass
class Hero:
    name: str = ''
    level: int = 1
    life: int = 1
    atk: int = 0
    defense: int = 0
    warm: int = 0
    marm: int = 0
    power: int = 0
    kind: int = 0
    gear: dict = field(default_factory=dict)


def _item(project, v):
    return next((r for r in project.tables['items'] if r['id'] == v), None) or {}


def class_of(project, cid):
    return next((c for c in project.tables['classes'] if c['id'] == cid), None)


def starting_gear(project, cid) -> dict:
    """{'weapon': item id, ...} the class starts with."""
    c = class_of(project, cid) or {}
    bag = c.get('bag', {})
    return {slot: bag[cell] for slot, cell in SLOTS.items() if cell in bag}


def gear_for_level(project, cid, level) -> dict:
    """What a hero of this class might plausibly carry by this level: the best of each kind that costs what he could have
    saved up (about 40 gold a level, squared, so the shop gear keeps pace)."""
    budget = 8 * level * level + 25 * level
    out = starting_gear(project, cid)
    for slot, kinds in SLOT_TYPES.items():
        if slot == 'weapon':
            kinds = ('weapon',)
        rows = [r for r in project.tables['items'] if r.get('type') in kinds and r['id'] > 0 and 0 < (r.get('price') or 0) <= budget
                and not r.get('quest')]
        if slot == 'offhand' and 'offhand' not in out:
            rows = [r for r in rows if r.get('type') == 'shield'] if not out.get('offhand') else rows
            if not rows:
                continue
        if rows:
            best = max(rows, key=lambda r: r.get('price') or 0)
            cur = _item(project, out.get(slot))
            if (best.get('price') or 0) > (cur.get('price') or 0):
                out[slot] = best['id']
    return out


def hero_at(project, cid: int, level: int, gear: dict | None = None) -> Hero:
    """The hero of this class at this level wearing this gear, as the game works out his stats on average."""
    c = class_of(project, cid)
    if c is None:
        return Hero()
    gear = dict(gear if gear is not None else starting_gear(project, cid))
    n = max(0, level - 1)
    gl, gm = (c.get('growth') or (0, 0))
    wep, off, helm, arm, amu = (_item(project, gear.get(s)) for s in ('weapon', 'offhand', 'helmet', 'armour', 'amulet'))
    bstr, bdex, bacc = c['str'] + GAIN * n, c['dex'] + GAIN * n, c['acc'] + GAIN * n
    dex = amu.get('dex', 0) + bdex + helm.get('dex', 0)
    acc = amu.get('acc', 0) + bacc
    h = Hero(name=c['name'], level=level, gear=gear)
    h.life = int(round(c['life'] + gl * n + GAIN * n))
    h.kind = wep.get('kind', 0)
    if h.kind != 4:
        h.atk = int(round(wep.get('atk', 0) + dex + amu.get('atk', 0) + 35 + (off.get('atk', 0) if off.get('type') == 'shield' else 0)))
    else:
        h.atk = int(round(wep.get('atk', 0) + 2 * acc + amu.get('atk', 0) + 15))
    h.defense = int(round(off.get('def', 0) + dex + amu.get('def', 0) + 10))
    h.warm = arm.get('warm', 0) + helm.get('warm', 0) + amu.get('warm', 0) + wep.get('warm', 0)
    h.marm = arm.get('marm', 0) + helm.get('marm', 0) + amu.get('marm', 0) + wep.get('marm', 0)
    h.power = wep.get('power', 0)
    return h


def spread_values(power: int):
    """All the rolls power +- a third can give, equally likely."""
    third = power // 3 if power >= 0 else -((-power) // 3)
    return [power + k - third for k in range(2 * third + 1)]


def expected_damage(power: int, armour: int) -> float:
    vals = spread_values(power)
    return sum(max(0, v - armour) for v in vals) / len(vals)


def hit_chance(atk: int, defence: int) -> float:
    return max(0.0, min(1.0, (atk - defence) / 100))


@dataclass
class Duel:
    hero_hit: float
    hero_damage: float
    hits_to_kill: float
    rounds: float
    mon_hit: float
    mon_damage: float
    life_lost: float                 # average life the hero loses in the fight
    life_lost_pct: float             # ... as a share of his life
    win: float                       # chance the hero wins (monte carlo)
    verdict: str
    note: str = ''


def duel(hero: Hero, mon: dict, runs: int = 600, seed: int = 1) -> Duel:
    """Hero and creature trading blows, the hero first, until one falls."""
    e_life = max(1, int(mon.get('life') or 1))
    e_def = int(mon.get('def') or 0)
    e_warm = int(mon.get('warm') or 0)
    e_atk = int(mon.get('atk') or 0)
    e_pow = int(mon.get('power') or 0)
    caster = e_atk == 0 or (mon.get('range') or 1) > 1 and e_atk == 0
    magic = bool(mon.get('magic_attack')) or caster
    h_chance = hit_chance(hero.atk, e_def)
    h_dmg = expected_damage(hero.power, e_warm if hero.kind != 3 else 0)
    m_chance = 1.0 if caster else hit_chance(e_atk, hero.defense)
    m_dmg = expected_damage(e_pow, hero.marm if magic else hero.warm)
    per_swing = h_chance * h_dmg
    hits_to_kill = (e_life / h_dmg) if h_dmg > 0 else float('inf')
    rounds = (e_life / per_swing) if per_swing > 0 else float('inf')
    rng = random.Random(seed)
    wins, lost_total, fights = 0, 0.0, 0
    h_rolls = [max(0, v - (e_warm if hero.kind != 3 else 0)) for v in spread_values(hero.power)]
    m_rolls = [max(0, v - (hero.marm if magic else hero.warm)) for v in spread_values(e_pow)]
    nh, nm = len(h_rolls), len(m_rolls)
    rand = rng.random
    if per_swing > 0:
        for _ in range(runs):
            hl, el, t = hero.life, e_life, 0
            while hl > 0 and el > 0 and t < 300:
                t += 1
                if rand() < h_chance:
                    el -= h_rolls[int(rand() * nh)]
                if el <= 0:
                    break
                if rand() < m_chance:
                    hl -= m_rolls[int(rand() * nm)]
            if el <= 0 and hl > 0:
                wins += 1
            lost_total += max(0, hero.life - max(hl, 0))
            fights += 1
    win = wins / fights if fights else 0.0
    lost = lost_total / fights if fights else float(hero.life)
    pct = (lost / hero.life) if hero.life else 1.0
    note = ''
    if h_dmg <= 0:
        verdict, note = 'Cannot be hurt', f"{hero.name or 'The hero'}'s blows do nothing through its armour."
    elif win < 0.5:
        verdict = 'Deadly'
    elif pct > 0.6 or win < 0.9:
        verdict = 'Tough'
    elif pct > 0.25:
        verdict = 'Fair'
    elif pct > 0.08:
        verdict = 'Easy'
    else:
        verdict = 'Pushover'
    if m_dmg <= 0 and m_chance > 0 and not note:
        note = 'Its blows cannot get through his armour.'
    return Duel(hero_hit=h_chance, hero_damage=h_dmg, hits_to_kill=hits_to_kill, rounds=rounds, mon_hit=m_chance, mon_damage=m_dmg,
                life_lost=lost, life_lost_pct=pct, win=win, verdict=verdict, note=note)


def describe(d: Duel, hero: Hero, mon: dict) -> list[str]:
    """The numbers in words, for the creature's page."""
    name = mon.get('name') or 'It'
    lines = []
    if d.hero_damage > 0:
        lines.append(f'{hero.name} (level {hero.level}) hits {d.hero_hit * 100:.0f}% of the time for about {d.hero_damage:.1f}: '
                     f'{d.hits_to_kill:.1f} hits to kill it.')
    else:
        lines.append(f'{hero.name} cannot hurt it with this weapon.')
    if d.mon_damage > 0 and d.mon_hit > 0:
        lines.append(f'{name} hits {d.mon_hit * 100:.0f}% of the time for about {d.mon_damage:.1f}.')
    else:
        lines.append(f'{name} cannot hurt him.')
    lines.append(f'A fight costs him about {d.life_lost:.0f} of {hero.life} life ({d.life_lost_pct * 100:.0f}%), '
                 f'and he wins {d.win * 100:.0f}% of the time.')
    return lines


def tune(hero: Hero, mon: dict, target: float = 0.30, runs: int = 250):
    """Scale a creature's life and power together until a fight costs this hero about `target` of his life.
    Returns (life, power) or None if his weapon cannot hurt it at all."""
    base_life, base_pow = max(1, int(mon.get('life') or 1)), max(1, int(mon.get('power') or 1))
    probe = dict(mon, life=base_life, power=base_pow)
    if expected_damage(hero.power, int(probe.get('warm') or 0) if hero.kind != 3 else 0) <= 0 or hit_chance(hero.atk, int(probe.get('def') or 0)) <= 0:
        return None
    lo, hi = 0.1, 12.0
    best = (base_life, base_pow)
    for _ in range(16):
        m = (lo * hi) ** 0.5
        life, power = max(1, round(base_life * m)), max(1, round(base_pow * m))
        d = duel(hero, dict(mon, life=life, power=power), runs=runs, seed=7)
        best = (life, power)
        if d.life_lost_pct > target:
            hi = m
        else:
            lo = m
    return best


def heat(project, mon: dict, cid: int, levels=range(1, 21), runs: int = 200):
    """The verdict against the hero of this class at each level (with the gear he might have): [(level, Duel)]."""
    out = []
    for lv in levels:
        h = hero_at(project, cid, lv, gear_for_level(project, cid, lv))
        out.append((lv, duel(h, mon, runs=runs)))
    return out
