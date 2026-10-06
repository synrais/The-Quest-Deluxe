"""Ready-made kinds of creature to start a new one from: a brute, an archer, a mage, a boss ...

Each starts as a copy of a creature of the pack that already is that kind (so every trait the engine needs is there),
with its numbers set for how tough you want it, a fresh number, and the picture copied to paint over.
"""
from __future__ import annotations

import copy

from .worldgen import hostile, threat

TIERS = ['1  Easy', '2', '3  Fair', '4', '5  Tough', '6', '7  Hard', '8', '9  Brutal', '10  Boss']


def stats_for(t: float) -> dict:
    """The numbers of an ordinary melee creature at toughness t (1 to 10), fitted to the original game's monsters."""
    return {'life': 3 + 1.1 * t * t, 'power': 2 + 4.2 * (t - 1), 'atk': 60 + 15 * (t - 1), 'def': 5 + 5 * (t - 1),
            'warm': max(0, (t - 3) * 2.5), 'marm': max(0, (t - 3) * 1.8), 'exp': 8 * t ** 1.35}


class Kind:
    def __init__(self, key, title, text, icon, find, mods):
        self.key, self.title, self.text, self.icon, self.find, self.mods = key, title, text, icon, find, mods


def _first(rows, pred):
    return next((c for c in rows if pred(c)), None)


def _monsters(project):
    return [c for c in project.tables['creatures'] if c['id'] > 0]


def _people(project):
    return [c for c in project.tables['creatures'] if -100 < c['id'] < 0 and c['id'] != -5]


def find_brute(p):
    return _first(sorted(hostile(p), key=threat), lambda c: (c.get('range') or 1) == 1 and (c.get('atk') or 0) > 0
                  and not c.get('invisible') and not c.get('heals_allies') and c.get('corpse') is None and (c.get('size') or 1) == 1)


def find_archer(p):
    return _first(hostile(p), lambda c: (c.get('range') or 1) > 1 and (c.get('atk') or 0) > 0)


def find_mage(p):
    return _first(hostile(p), lambda c: (c.get('atk') or 0) == 0 and (c.get('range') or 1) > 1 and c.get('cast_anim') and not c.get('heals_allies'))


def find_tank(p):
    rows = [c for c in hostile(p) if (c.get('range') or 1) == 1 and (c.get('atk') or 0) > 0]
    return max(rows, key=lambda c: (c.get('warm') or 0)) if rows else None


def find_healer(p):
    return _first(_monsters(p), lambda c: c.get('heals_allies'))


def find_undead(p):
    return _first(hostile(p), lambda c: c.get('corpse') == 'bones' and (c.get('range') or 1) == 1)


def find_animal(p):
    return _first(_monsters(p), lambda c: c.get('animal') and (c.get('att') or 0) < 0)


def find_boss(p):
    rows = [c for c in hostile(p) if (c.get('life') or 0) >= 70 and (c.get('range') or 1) == 1]
    return min(rows, key=lambda c: c.get('life') or 0) if rows else find_brute(p)


def find_person(p):
    return _first(_people(p), lambda c: c.get('att') == -2) or (_people(p) or [None])[0]


def find_giant(p):
    return _first(_monsters(p), lambda c: (c.get('size') or 1) > 1) or find_boss(p)


def mod_archer(r, t):
    r.update(life=r['life'] * 0.8, power=r['power'] * 0.55, atk=r['atk'] * 0.6, range=max(r.get('range') or 1, 6))


def mod_mage(r, t):
    r.update(life=r['life'] * 0.6, power=r['power'] * 1.1, atk=0, range=max(r.get('range') or 1, 4), marm=r['marm'] + 4 + t)


def mod_tank(r, t):
    r.update(life=r['life'] * 1.7, warm=r['warm'] * 2 + 3, def_=r['def_'] + 10)


def mod_swarm(r, t):
    r.update(life=max(2, r['life'] * 0.5), power=r['power'] * 0.7, atk=r['atk'] * 0.9)


def mod_thief(r, t):
    r.update(life=r['life'] * 0.8, extra={'steal_gold': {'chance': 35, 'min': 5, 'max': int(10 + 12 * t)}})


def mod_healer(r, t):
    r.update(life=r['life'] * 0.8, atk=0, power=r['power'] * 0.7, marm=r['marm'] + 3)


def mod_giant(r, t):
    r.update(life=r['life'] * 3, power=r['power'] * 1.4, size=2)


def mod_boss(r, t):
    r.update(life=r['life'] * 4, power=r['power'] * 1.4, atk=r['atk'] + 20, def_=r['def_'] + 10, exp=r['exp'] * 6, rich=True)


def mod_person(r, t):
    r.update(life=max(5, 4 + t * 2), power=max(2, t), atk=50 + t * 4, def_=0, warm=0, marm=0, exp=0)


def mod_animal(r, t):
    r.update(power=r['power'] * 0.9)


KINDS = [
    Kind('brute', 'Brute', 'Fights hand to hand. The plain, honest monster.', 'sword', find_brute, lambda r, t: None),
    Kind('archer', 'Archer', 'Shoots from a distance and stays away.', 'line', find_archer, mod_archer),
    Kind('mage', 'Mage', 'Casts spells from afar. No blows, but the spells hurt.', 'wand', find_mage, mod_mage),
    Kind('tank', 'Armoured', 'Slow to hurt: armour takes most of a weak weapon\'s damage.', 'shield', find_tank, mod_tank),
    Kind('swarm', 'Swarmer', 'Weak alone, a problem in a crowd.', 'people', find_brute, mod_swarm),
    Kind('thief', 'Thief', 'Steals gold when it hits, and drops it when it dies.', 'coin', find_brute, mod_thief),
    Kind('healer', 'Healer', 'Heals the monsters near it instead of fighting.', 'heart', find_healer, mod_healer),
    Kind('undead', 'Undead', 'Leaves bones that a necromancer can raise.', 'moon', find_undead, lambda r, t: None),
    Kind('giant', 'Giant', 'Takes up 2 by 2 squares.', 'skull', find_giant, mod_giant),
    Kind('boss', 'Boss', 'A big fight for the end of a level.', 'star', find_boss, mod_boss),
    Kind('animal', 'Wild animal', 'Leaves the hero alone unless he hits it.', 'tree', find_animal, mod_animal),
    Kind('person', 'Villager', 'Stands about and talks. Add what it says on the Story page.', 'person', find_person, mod_person),
]


def available(project) -> list:
    return [k for k in KINDS if k.find(project) is not None]


def next_id(project, kind: str) -> int:
    used = {c['id'] for c in project.tables['creatures']}
    if kind == 'person':
        return next((n for n in range(-20, -100, -1) if n not in used), None)
    v = 101
    while v in used:
        v += 1
    return v


def make(project, kind: Kind, name: str, tier: float):
    """A new creature row (not yet added to the table): its template with the numbers for this toughness."""
    base = kind.find(project)
    row = copy.deepcopy(base)
    st = stats_for(tier)
    vals = {'life': st['life'], 'power': st['power'], 'atk': st['atk'], 'def_': st['def'], 'warm': st['warm'], 'marm': st['marm'],
            'exp': st['exp'], 'range': base.get('range') or 1, 'extra': {}, 'rich': False, 'size': base.get('size') or 1}
    kind.mods(vals, tier)
    row['id'] = next_id(project, 'person' if kind.key == 'person' else 'monster')
    row['name'] = name
    row.pop('log_name', None)
    row['life'] = max(1, int(round(vals['life'])))
    row['power'] = max(1, int(round(vals['power'])))
    row['atk'] = max(0, int(round(vals['atk'])))
    row['def'] = max(0, int(round(vals['def_'])))
    row['warm'] = max(0, int(round(vals['warm'])))
    row['marm'] = max(0, int(round(vals['marm'])))
    row['exp'] = max(0, int(round(vals['exp'])))
    row['range'] = vals['range']
    if vals['size'] > 1:
        row['size'] = vals['size']
    else:
        row.pop('size', None)
    for k, v in vals['extra'].items():
        row[k] = v
    n = max(2, int(round(3 * tier ** 1.3)))
    gold = [20, 100, 'gold', n, int(tier)]
    if kind.key == 'boss' or vals['rich']:
        row['loot'] = [[0, 100, 'gold', n * 4, int(tier) * 8]]
    elif kind.key == 'person':
        row['loot'] = [[20, 100, 'gold', max(3, n), 1]]
    elif kind.key == 'animal':
        row['loot'] = base.get('loot', [])
    else:
        row['loot'] = [gold] + [r for r in (base.get('loot') or []) if r[2] == 'item'][:1]
    for k in ('transforms_into', 'transforms_below', 'transforms_damage', 'becomes_on_death', 'bursts_into', 'reveals_as',
              'hides_as', 'raises_dead', 'drop_on_level'):
        row.pop(k, None)                         # links to other creatures belong to the template, not to the new one
    if row.get('invisible'):
        row.pop('invisible')
    return row, base
