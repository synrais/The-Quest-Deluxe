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
    # it rises again and again while blood is in reach, and not from blood past its blood_range
    pk.creatures[1]['blood_range'] = 3
    w.sq(cx + 6, cy).deco = blood                                               # too far
    again = g.spawn(1, cx, cy)
    g.combat.hurt(1000, again, 3, by_hero=True)
    for _ in range(8):
        g.combat.revive_step()
    assert w.enemy_at(cx, cy) is None and w.sq(cx + 6, cy).deco == blood
    w.sq(cx - 3, cy + 1).deco = blood                                           # in reach
    w.sq(cx + 6, cy).deco = 0
    again = g.spawn(1, cx, cy)
    g.combat.hurt(1000, again, 3, by_hero=True)
    for _ in range(8):
        g.combat.revive_step()
    third = w.enemy_at(cx, cy)
    assert third is not None and third.life == third.mlife
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


def big_creature(shot=None):
    def big(folder, json):
        path = os.path.join(folder, 'creatures.json')
        data = json.load(open(path))
        for r in data['creatures']:
            if r['id'] == 1:
                r['size'] = 2
        json.dump(data, open(path, 'w'))
    from engine.ai import monsmove
    g = with_changes(big)
    p, w = g.player, g.world
    for e in list(w.enemies):
        w.sq(e.x, e.y).mon = 0
    w.enemies.clear()
    ox, oy = w.origin
    for x, y in w.room_tiles():
        q = w.sq(x, y)
        q.wall = q.mon = q.item = q.deco = 0
    p.X, p.Y = ox + 8, oy + 8
    w.sq(ox + 2, oy + 2).mon = 1                                   # only the top-left square on the map
    w.rescan(p, g.status)
    assert len(w.enemies) == 1
    e = w.enemies[0]
    cells = {(ox + 2, oy + 2), (ox + 3, oy + 2), (ox + 2, oy + 3), (ox + 3, oy + 3)}
    assert set(w.cells(e)) == cells and all(w.sq(x, y).mon == 1 for x, y in cells)
    assert all(w.enemy_at(x, y) is e for x, y in cells) and w.enemy_at(ox + 4, oy + 2) is None
    w.rescan(p, g.status)                                          # the marked squares make no more creatures
    assert len(w.enemies) == 1
    e = w.enemies[0]
    e.att = 9
    for _ in range(5):
        monsmove(g)
        e.moved = False
        now = set(w.cells(e))
        assert len(now) == 4 and sum(1 for x, y in w.room_tiles() if w.sq(x, y).mon == 1) == 4
        assert all(w.sq(x, y).mon == 1 for x, y in now)
    assert (e.x, e.y) != (ox + 2, oy + 2)                          # it came after the hero
    p.X, p.Y = e.x + 2, e.y                                        # next to its right side
    assert w.gap(e, p.X, p.Y) == (1, 0)
    mon = e
    mon.life = 1
    g.combat.hurt(1000, w.enemy_at(e.x + 1, e.y + 1), 3, by_hero=True)     # struck on its far square
    assert not w.enemies and not any(w.sq(x, y).mon for x, y in w.room_tiles())
    # it is drawn once, over all its squares, from above and in FPS mode
    e = g.spawn(1, ox + 2, oy + 2)
    g.renderer.draw(g, present=False)
    g.view3d = True
    g.facing = 3
    p.X, p.Y = ox + 6, oy + 3
    g.renderer.draw(g, present=False)
    if shot:
        pygame.image.save(g.renderer.screen, shot)
    print('big creatures: one creature on 2 x 2 squares: found from any, moves whole, fights from its nearest '
          'square, dies on all, drawn once: ok')


def links():
    def stairs(folder, json):
        path = os.path.join(folder, 'items.json')
        data = json.load(open(path))
        data['items'] += [{'id': 990, 'name': 'Stairs down', 'type': 'stairs'},
                          {'id': 991, 'name': 'Stairs up', 'type': 'stairs'},
                          {'id': 992, 'name': 'Hole', 'type': 'hole'}]
        json.dump(data, open(path, 'w'))
        for n, text in ((1, 'LINKS = {(6, 5): (2, 20, 20), (8, 5): (2, 30, 30, "Down you go.")}\n'),
                        (2, 'LINKS = {(20, 20): (1, 6, 6)}\n')):
            path = os.path.join(folder, 'levels', str(n), 'script.qs')
            src = open(path).read()
            at = src.index('START')
            open(path, 'w').write(src[:at] + text + src[at:])
    g = with_changes(stairs)
    from engine.state import LINK_ITEMS
    assert LINK_ITEMS
    p, w = g.player, g.world
    assert w.level == 1
    for e in list(w.enemies):
        w.sq(e.x, e.y).mon = 0
    w.enemies.clear()
    w.leave_room()
    p.X, p.Y = 5, 5
    w.enter_room(p, g.status)
    for x in (6, 8):
        w.sq(x, 5).wall = w.sq(x, 5).mon = 0
    w.sq(6, 5).item, w.sq(8, 5).item = 990, 992
    w.sq(7, 5).gold = 77                                       # something done on level 1 that must stay done
    w.sq(20, 20).item = 0
    g.try_move(1, 0)                                           # onto the stairs at (6, 5)
    assert (w.level, g.status.level, p.X, p.Y) == (2, 2, 20, 20), (w.level, p.X, p.Y)
    assert 1 in w.stash
    w.sq(20, 20).item = 991
    w.sq(21, 20).gold = 5                                      # and something on level 2
    g.pick_up()                                                # Enter on the stairs back: level 2's LINKS
    assert (w.level, p.X, p.Y) == (1, 6, 6) and w.sq(7, 5).gold == 77 and 2 in w.stash
    p.X, p.Y = 7, 5
    g.try_move(1, 0)                                           # (8, 5): the hole, with its own text
    assert (w.level, p.X, p.Y) == (2, 30, 30) and w.sq(21, 20).gold == 5     # level 2 as it was left
    # a save keeps the levels left behind, as what differs from the pack's maps
    d = g.to_save()
    assert set(d.extra['levels']) == {'1'}
    g.slots.write(1, d)
    d = g.slots.read(1)                                        # through the file and back
    g2 = with_changes(stairs)
    g2.from_save(d, 1)
    assert g2.world.level == 2 and 1 in g2.world.stash and g2.world.stash[1][0][7][5].gold == 77
    print('links: stairs and holes lead to another level, which keeps what was done in it, and saves: ok')


def moved_walls():
    def boulder(folder, json):
        path = os.path.join(folder, 'tiles.json')
        tiles = json.load(open(path))
        tiles['walls'].append({'id': 41, 'name': 'Boulder', 'solid': True, 'needs_item': 995, 'becomes': 0,
                               'becomes_deco': 5, 'consumes': True, 'message': 'The boulder rolls away.',
                               'blocked_message': 'Too heavy.'})
        json.dump(tiles, open(path, 'w'))
        shutil.copy(os.path.join(folder, 'sprites', 'walls', '1.png'), os.path.join(folder, 'sprites', 'walls', '41.png'))
        path = os.path.join(folder, 'items.json')
        data = json.load(open(path))
        data['items'].append({'id': 995, 'name': 'Crowbar', 'type': 'treasure'})
        json.dump(data, open(path, 'w'))
    g = with_changes(boulder)
    p, w = g.player, g.world
    for e in list(w.enemies):
        w.sq(e.x, e.y).mon = 0
    w.enemies.clear()
    w.sq(p.X + 1, p.Y).wall = w.sq(p.X + 1, p.Y).mon = w.sq(p.X + 1, p.Y).item = 0
    w.sq(p.X + 1, p.Y).wall = 41
    assert not g.try_move(1, 0) and w.sq(p.X + 1, p.Y).wall == 41        # no crowbar: it stays
    free = p.free_backpack_slot()
    p.bag[free] = 995
    assert g.try_move(1, 0) and w.sq(p.X + 1, p.Y).wall == 0 and w.sq(p.X + 1, p.Y).deco == 5
    assert 995 not in p.bag.values()                                        # used up
    print('an item moves a wall: the boulder gives way to the crowbar, which is used up: ok')


def painted_hero():
    def paint(folder, json):
        os.makedirs(os.path.join(folder, 'sprites', 'heroes'), exist_ok=True)
        img = pygame.Surface((40, 40), pygame.SRCALPHA)
        img.fill((0, 0, 0, 0))
        pygame.draw.rect(img, (255, 0, 255, 255), (10, 10, 20, 20))
        pygame.image.save(img, os.path.join(folder, 'sprites', 'heroes', '2.png'))
    g = with_changes(paint)                                       # quick_start(2, 1): a Mage
    p = g.player
    g.renderer.draw(g, present=False)
    ox, oy = g.world.origin
    px, py = (p.X - ox) * 40, (p.Y - oy) * 40
    assert tuple(g.renderer.screen.get_at((px + 20, py + 20)))[:3] == (255, 0, 255)      # his painted picture
    assert tuple(g.renderer.screen.get_at((px + 2, py + 2)))[:3] != (255, 0, 255)
    print('a painted hero (sprites/heroes/<class>.png) takes the place of the drawn one: ok')


def event_code_text():
    from editor.event_code import rule_lines, add_to_handler
    from engine.script import Script
    rule = rule_lines('talk', -6, [('m1', 0), ('has', 208)], [('say', 12), ('give', 208), ('m1', 1)])
    assert rule[0] == 'if npc == -6 and m1 == 0 and has_any(208):' and rule[-1] == '    m1 = 1'
    script = 'START = (5, 5)\n\n\ndef talk(npc):\n    # hi\n    pass\n\n\ndef dies(w):\n    pass\n'
    out = add_to_handler(script, 'talk', rule)
    assert 'pass' not in out.split('def dies')[0] and out.count('def talk') == 1
    out = add_to_handler(out, 'talk', rule_lines('talk', -7, [], [('message', (-7, 11))]))
    out = add_to_handler(out, 'level_start', rule_lines('arrive', None, [('rep', 3)], [('coins', 50)]))
    out = add_to_handler(out, 'dies', rule_lines('dies', 3, [], [('next', None)]))
    Script(out, 'test')                                         # every handler it wrote is one the game reads
    assert 'def level_start():' in out and 'message(-7, 11)' in out
    print('events: rules are written into the right handler, made when missing, and read by the game: ok')


def disguise():
    def spell(folder, json):
        path = os.path.join(folder, 'spells.json')
        data = json.load(open(path))
        data['spells'].append({'id': 21, 'name': 'Disguise', 'req_int': 1, 'mana': 5, 'range': 0, 'power': 0,
                               'duration': 5, 'effect': 'disguise', 'npc_anger': 100, 'creatures': [1]})
        json.dump(data, open(path, 'w'))
    from engine.state import Enemy
    g = with_changes(spell)
    p, w, h = g.player, g.world, g.player.hero
    for e in list(w.enemies):
        w.sq(e.x, e.y).mon = 0
    w.enemies.clear()
    ox, oy = w.origin
    p.X, p.Y = ox + 5, oy + 5
    friend = g.spawn(-6, ox + 2, oy + 2)                          # a farmer, friendly
    friend.att = -2
    orc = g.spawn(1, ox + 8, oy + 8)
    orc.att = 9
    p.hero.mana, p.spells[21] = p.hero.mmana, 1
    assert not g.disguised()
    g.magic.cast_self(21)
    assert g.disguised() and p.more['disguise'][0] == 1
    assert orc.att == -5 and friend.att == 8                       # monsters leave him be, the farmer does not
    g.renderer.draw(g, present=False)                              # drawn in the creature's shape
    px, py = (p.X - ox) * 40, (p.Y - oy) * 40
    shape = g.renderer.sprites.get('enemy', 1)
    assert shape is not None and g.renderer.screen.get_at((px + 20, py + 20)) in (shape.get_at((20, 20)),
                                                                                  shape.get_at((20, 21)))
    g.combat.wake_on_attack(orc)                                   # fighting does not end it
    assert g.disguised()
    for _ in range(5):
        g.upkeep()
    assert g.disguised()                                           # its turns, and the one of the cast
    g.upkeep()
    assert g.disguised() is False and 'disguise' not in p.more
    assert orc.att == 9 and friend.att == -2                       # everyone is as they were
    print('disguise: a random shape, monsters leave him, a friendly person turns on him, and it wears off: ok')


def shrinking():
    def setup(folder, json):
        path = os.path.join(folder, 'quest.json')
        q = json.load(open(path))
        q['potions'] = {'9': {'name': 'Shrinking', 'colour': 11, 'shrink': 3}}
        json.dump(q, open(path, 'w'))
        path = os.path.join(folder, 'tiles.json')
        tiles = json.load(open(path))
        tiles['walls'].append({'id': 42, 'name': 'Crack', 'solid': True, 'small_only': True})
        json.dump(tiles, open(path, 'w'))
        shutil.copy(os.path.join(folder, 'sprites', 'walls', '1.png'), os.path.join(folder, 'sprites', 'walls', '42.png'))
    from engine.state import add_potions
    g = with_changes(setup)
    p, w = g.player, g.world
    for e in list(w.enemies):
        w.sq(e.x, e.y).mon = 0
    w.enemies.clear()
    for dx in (1, 2):
        sq = w.sq(p.X + dx, p.Y)
        sq.wall = sq.mon = sq.item = 0
    w.sq(p.X + 1, p.Y).wall = 42
    x0 = p.X
    assert not g.shrunk() and not g.try_move(1, 0) and p.X == x0           # too big
    add_potions(p, 9, 1)
    assert g.drink_extra(9) and g.shrunk()
    assert g.try_move(1, 0) and p.X == x0 + 1                              # through the crack
    g.renderer.draw(g, present=False)                                      # drawn small, inside the wall
    for _ in range(4):
        g.upkeep()
    assert g.shrunk()                                                      # not while he is inside it
    assert g.try_move(1, 0) and p.X == x0 + 2
    g.upkeep()
    assert not g.shrunk()
    assert not g.try_move(-1, 0) and p.X == x0 + 2                         # and big again, he can't go back
    print('shrinking: a potion makes the hero small enough for a crack in the wall, and holds while inside: ok')


def resurrection():
    def spell(folder, json):
        path = os.path.join(folder, 'spells.json')
        data = json.load(open(path))
        data['spells'].append({'id': 21, 'name': 'Resurrect', 'req_int': 1, 'mana': 5, 'range': 5, 'power': 0,
                               'duration': 0, 'effect': 'resurrect'})
        json.dump(data, open(path, 'w'))
    from engine.ai import monsmove
    g = with_changes(spell)
    p, w, pk = g.player, g.world, g.pack
    for e in list(w.enemies):
        w.sq(e.x, e.y).mon = 0
    w.enemies.clear()
    ox, oy = w.origin
    for x, y in w.room_tiles():
        q = w.sq(x, y)
        q.wall = q.mon = q.item = q.deco = q.gold = 0
    p.X, p.Y = ox + 5, oy + 8
    p.hero.mana, p.spells[21] = p.hero.mmana, 1
    victim = g.spawn(1, ox + 4, oy + 8)                          # a monster dies beside the hero
    person = g.spawn(-6, ox + 6, oy + 8)                         # and a farmer
    person.att = -2
    for e in (victim, person):
        g.combat.hurt(1000, e, 3, by_hero=True)
    assert not g.magic.valid_target(21, ox + 4, oy + 1)          # nothing lies there
    assert g.magic.valid_target(21, ox + 4, oy + 8) and g.magic.valid_target(21, ox + 6, oy + 8)
    g.magic.cast_at(21, ox + 4, oy + 8)
    raised = w.enemy_at(ox + 4, oy + 8)
    assert raised is not None and raised.type == 1 and raised.att == -3 and raised.ally
    assert raised.life == raised.mlife and w.sq(ox + 4, oy + 8).deco == 0
    assert not g.magic.valid_target(21, ox + 4, oy + 8)          # the body is gone
    g.magic.cast_at(21, ox + 6, oy + 8)                          # and the person
    friend = w.enemy_at(ox + 6, oy + 8)
    assert friend is not None and friend.type == -6 and friend.ally
    # a hostile monster comes: the raised creatures fight it, and the hero cannot hit his own side
    orc = g.spawn(2, ox + 4, oy + 5)
    orc.att = 9
    start = orc.life
    hp = raised.life
    assert not g.try_move(-1, 0) and raised.life == hp           # bumping into him does not strike him
    for _ in range(12):
        monsmove(g)
        for e in w.enemies:
            e.moved = False
        if orc not in w.enemies:
            break
        g.combat.check_dead()
    assert orc not in w.enemies or orc.life < start, 'the raised creature fought the orc'
    # leaving the screen: the raised go back to rest
    risen = [(e.x, e.y) for e in w.enemies if e.ally]
    assert risen
    w.leave_room()
    assert all(w.sq(x, y).mon == 0 for x, y in risen)
    print('resurrection: a dead creature and a dead person rise at full life, fight beside the hero, rest when he leaves: ok')


if __name__ == '__main__':
    fire()
    ice()
    elements()
    blood_regen()
    foresight()
    clones()
    resurrection()
    shrinking()
    disguise()
    event_code_text()
    links()
    moved_walls()
    painted_hero()
    big_creature(sys.argv[1] if len(sys.argv) > 1 else None)
    print('all extras checks passed')
