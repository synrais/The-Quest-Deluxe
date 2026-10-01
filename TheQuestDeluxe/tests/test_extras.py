"""Spells that clear blood and freeze water (spells.json `burns`, `freezes_water`; tiles.json `freezes_to`).

    python tests/test_extras.py
"""
from __future__ import annotations

import os
import shutil
import sys

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pygame  # noqa: E402

pygame.init()
pygame.display.set_mode((640, 480))

from test_limits import pack_copy  # noqa: E402


def with_changes(change):
    g = pack_copy(change)
    g.quick_start(2, 1)
    return g


def flame_and_ice(folder, json):
    path = os.path.join(folder, 'spells.json')
    data = json.load(open(path))
    for s in data['spells']:
        if s['id'] == 2:
            s['burns'] = 1                                    # Flame: the square and its neighbours
        if s['id'] == 9:
            s['burns'] = 2                                    # Inferno: a larger area
        if s['id'] == 5:
            s['freezes_water'] = 1
            s['duration'] = 3
    json.dump(data, open(path, 'w'))
    path = os.path.join(folder, 'tiles.json')
    tiles = json.load(open(path))
    tiles['walls'].append({'id': 40, 'name': 'Ice', 'view3d': 'flat'})
    for w in tiles['walls']:
        if w['id'] == 2:
            w['freezes_to'] = 40
    json.dump(tiles, open(path, 'w'))
    shutil.copy(os.path.join(folder, 'sprites', 'walls', '2.png'), os.path.join(folder, 'sprites', 'walls', '40.png'))


def fire():
    g = with_changes(flame_and_ice)
    w, p, pk = g.world, g.player, g.pack
    ox, oy = w.origin
    cx, cy = ox + 5, oy + 5
    blood = pk.deco('blood')
    for x in range(cx - 3, cx + 4):
        for y in range(cy - 3, cy + 4):
            w.sq(x, y).deco = blood
    p.hero.mana = 100
    g.magic.cast_at(2, cx, cy)                                # Flame, burns 1
    left = {(x, y) for x in range(cx - 3, cx + 4) for y in range(cy - 3, cy + 4) if w.sq(x, y).deco == blood}
    assert len(left) == 49 - 9 and (cx, cy) not in left and (cx + 1, cy + 1) not in left and (cx + 2, cy) in left
    g.magic.cast_at(9, cx, cy)                                # Inferno, burns 2
    assert w.sq(cx + 2, cy + 2).deco == 0 and w.sq(cx + 3, cy).deco == blood
    w.sq(cx, cy).deco = pk.deco('bones')
    g.magic.cast_at(9, cx, cy)
    assert w.sq(cx, cy).deco == pk.deco('bones')              # bones stay
    print('fire clears blood, a stronger spell a larger area, bones stay: ok')


def ice():
    g = with_changes(flame_and_ice)
    w, p = g.world, g.player
    ox, oy = w.origin
    cx, cy = ox + 5, oy + 3
    for x in range(cx - 2, cx + 3):
        w.sq(x, cy).wall = 2                                  # a strip of water
        w.sq(x, cy).mon = 0
    p.hero.mana = 100
    assert g.magic.valid_target(5, cx, cy)                    # the water is a target
    g.magic.cast_at(5, cx, cy)                                # Ring of Ice, radius 1, 3 turns
    assert [w.sq(x, cy).wall for x in range(cx - 2, cx + 3)] == [2, 40, 40, 40, 2]
    assert not g.pack.wall(40).get('solid')
    assert p.more['frozen'] and len(p.more['frozen']) == 3
    saved = [list(e) for e in p.more['frozen']]
    for _ in range(3):                                        # the turn of the cast, and two more
        g.upkeep()
    assert w.sq(cx, cy).wall == 40
    g.upkeep()
    assert [w.sq(x, cy).wall for x in range(cx - 2, cx + 3)] == [2, 2, 2, 2, 2]     # melted again
    assert 'frozen' not in p.more, saved
    print('ice: water turns to walkable ice for the spell\'s turns, then melts: ok')


def elements():
    from engine.state import Enemy, SLOT_WEAPON, SLOT_OFFHAND

    g = with_changes(lambda folder, json: None)
    p, w, pk = g.player, g.world, g.pack
    ox, oy = w.origin
    ex, ey = p.X + 1, p.Y
    for e in list(w.enemies):
        w.sq(e.x, e.y).mon = 0
    w.enemies.clear()
    w.sq(ex, ey).wall = 0
    mon = g.spawn(1, ex, ey)
    mon.life = mon.mlife = 100
    firesword = {'element': 'fire', 'element_power': 4, 'element_turns': 2}
    g.combat.apply_element(firesword, mon, 5)
    assert mon.effects == {'fire': [2, 4]}
    g.combat.tick_effects()
    assert mon.life < 100 and mon.effects == {'fire': [1, 4]}
    g.combat.tick_effects()
    assert mon.effects == {} and mon.life < 97                      # two bursts of about 4
    g.combat.apply_element({'element': 'ice', 'element_turns': 4}, mon, 5)
    assert mon.att == -15
    g.combat.apply_element({'element': 'poison'}, mon, 5)
    assert mon.effects == {'poison': [3, 3]}
    pk.creatures[1]['resists'] = ['fire']
    mon.effects.clear()
    g.combat.apply_element(firesword, mon, 5)
    assert mon.effects == {}                                        # resisted
    p.hero.life = 10
    g.combat.apply_element({'element': 'drain'}, mon, 6)
    assert p.hero.life == 13 or p.hero.life == p.hero.mlife
    print('elements: fire and poison burn over turns, ice freezes, drain heals, resists stops them: ok')


def blood_regen():
    def feeds(folder, json):
        path = os.path.join(folder, 'creatures.json')
        data = json.load(open(path))
        for r in data['creatures']:
            if r['id'] == 1:
                r['regenerates_from_blood'] = True
        json.dump(data, open(path, 'w'))
    g = with_changes(feeds)
    p, w, pk = g.player, g.world, g.pack
    for e in list(w.enemies):
        w.sq(e.x, e.y).mon = 0
    w.enemies.clear()
    ox, oy = w.origin
    for x, y in w.room_tiles():
        q = w.sq(x, y)
        q.wall, q.deco, q.mon, q.item = 0, 0, 0, 0
    p.X, p.Y = ox, oy
    cx, cy = ox + 5, oy + 5
    mon = g.spawn(1, cx, cy)
    near, far = (cx + 2, cy - 2), (cx + 4, cy)
    blood = pk.deco('blood')
    w.sq(*near).deco = w.sq(*far).deco = blood
    full = mon.mlife
    g.combat.hurt(1000, mon, 3, by_hero=True)
    assert w.enemy_at(cx, cy) is None and p.more['reviving']
    g.combat.revive_step()
    assert w.sq(*near).deco == 0 and w.sq(cx + 1, cy - 1).deco == blood        # the nearer pile came a square
    w.sq(cx + 1, cy - 1).deco = 0                                              # ... and is burnt away
    g.combat.revive_step()
    assert w.sq(*far).deco == 0 or w.sq(cx + 3, cy).deco == blood              # the other one comes instead
    for _ in range(6):
        g.combat.revive_step()
    again = w.enemy_at(cx, cy)
    assert again is not None and again.life == again.mlife == full and 'reviving' not in p.more
    assert w.sq(cx, cy).deco == 0
    g.combat.hurt(1000, again, 3, by_hero=True)                                 # no blood left but its own
    for _ in range(3):
        g.combat.revive_step()
    assert w.enemy_at(cx, cy) is None and 'reviving' not in p.more
    print('a creature that feeds on blood: the nearest pile slides to its body, it rises at full life, '
          'burnt blood starves it: ok')


def foresight():
    def potion(folder, json):
        path = os.path.join(folder, 'quest.json')
        q = json.load(open(path))
        q['potions'] = {'9': {'name': 'Foresight', 'colour': 13, 'foresight': 3}}
        json.dump(q, open(path, 'w'))
        path = os.path.join(folder, 'creatures.json')
        data = json.load(open(path))
        for r in data['creatures']:
            if r['id'] == 2:
                r['invisible'] = True
                r['reveals_as'] = 3
        json.dump(data, open(path, 'w'))
    from engine.state import add_potions
    g = with_changes(potion)
    p = g.player
    add_potions(p, 9, 1)
    assert not g.foresight() and g.true_form(2) == 2
    assert g.drink_extra(9) and g.foresight() and g.true_form(2) == 3
    for _ in range(3):
        g.upkeep()
        assert g.foresight()
    g.upkeep()
    assert not g.foresight()
    print('foresight: invisible creatures are drawn as what they are, for its turns: ok')


def clones():
    def spell(folder, json):
        path = os.path.join(folder, 'spells.json')
        data = json.load(open(path))
        data['spells'].append({'id': 21, 'name': 'Shadow Clones', 'req_int': 1, 'mana': 5, 'range': 0, 'power': 0,
                               'duration': 4, 'effect': 'shadow_clones', 'creature': -100, 'clones_hero': 50})
        json.dump(data, open(path, 'w'))
    g = with_changes(spell)
    p, w = g.player, g.world
    for e in list(w.enemies):
        w.sq(e.x, e.y).mon = 0
    w.enemies.clear()
    ox, oy = w.origin
    p.X, p.Y = ox + 5, oy + 5
    for x, y in w.room_tiles():
        w.sq(x, y).wall = w.sq(x, y).mon = 0
    w.sq(p.X + 1, p.Y).wall = 1                                   # a tree: no clone there
    p.hero.mana, p.spells[21] = 50, 1
    g.magic.cast_self(21)
    allies = [e for e in w.enemies if e.type == -100]
    assert len(allies) == 7 and all(max(abs(e.x - p.X), abs(e.y - p.Y)) == 1 for e in allies)
    assert all(e.life == max(1, p.hero.mlife * 50 // 100) for e in allies)
    for _ in range(4):
        g.combat.tick_effects()
    assert len(w.enemies) == 7
    g.combat.tick_effects()
    assert not w.enemies and not any(w.sq(x, y).mon for x, y in w.room_tiles())
    print('shadow clones: an ally on each free square around the hero, as strong as asked, fading after their turns: ok')


if __name__ == '__main__':
    fire()
    ice()
    elements()
    blood_regen()
    foresight()
    clones()
    print('all extras checks passed')
