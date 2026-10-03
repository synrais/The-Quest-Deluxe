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
    orc.att, orc.atk = 9, 0                                      # (it cannot hurt them, so that they are still there)
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


def followers_and_mending():
    def spells(folder, json):
        path = os.path.join(folder, 'spells.json')
        data = json.load(open(path))
        data['spells'] += [
            {'id': 21, 'name': 'Raise', 'req_int': 1, 'mana': 5, 'range': 5, 'power': 0, 'duration': 0,
             'effect': 'resurrect', 'follows': True},
            {'id': 22, 'name': 'Mend', 'req_int': 1, 'mana': 5, 'range': 5, 'power': 30, 'duration': 0,
             'effect': 'heal_target', 'anim': ['aheal2']}]
        json.dump(data, open(path, 'w'))
    g = with_changes(spells)
    p, w = g.player, g.world
    for e in list(w.enemies):
        w.sq(e.x, e.y).mon = 0
    w.enemies.clear()
    ox, oy = w.origin
    ox, oy = w.origin
    for x, y in w.room_tiles():
        q = w.sq(x, y)
        q.wall = q.mon = q.item = q.deco = q.gold = 0
    p.X, p.Y = ox + 9, oy + 5                                    # on the screen's east edge
    p.hero.mana, p.spells[21], p.spells[22] = p.hero.mmana, 1, 1
    victim = g.spawn(1, ox + 7, oy + 5)
    g.combat.hurt(10000, victim, 3, by_hero=True)
    g.magic.cast_at(21, ox + 7, oy + 5)
    ally = w.enemy_at(ox + 7, oy + 5)
    assert ally is not None and ally.__dict__.get('_follow')
    ally.life = max(1, ally.mlife // 3)
    g.magic.cast_at(22, ally.x, ally.y)                           # mend the ally
    assert ally.life > ally.mlife // 3
    foe = g.spawn(2, ox + 3, oy + 3)                               # and an enemy
    foe.att, foe.life = 9, 1
    g.magic.cast_at(22, foe.x, foe.y)
    assert foe.life > 1
    assert g.magic.valid_target(22, foe.x, foe.y) and not g.magic.valid_target(22, ox + 1, oy + 1)
    # he walks into the next screen: the raised ally comes too
    assert g.try_move(1, 0)
    assert p.X == ox + 10
    near = [e for e in w.enemies if e.type == 1 and e.__dict__.get('_risen')]
    assert len(near) == 1 and near[0].life == ally.life and w.in_room(near[0].x, near[0].y)
    assert max(abs(near[0].x - p.X), abs(near[0].y - p.Y)) <= 2
    print('a raised ally follows from screen to screen; a mending spell heals allies and enemies: ok')


def sizes_and_worn():
    def setup(folder, json):
        path = os.path.join(folder, 'quest.json')
        q = json.load(open(path))
        q['potions'] = {'9': {'name': 'Shrinking', 'colour': 11, 'shrink': 5},
                        '10': {'name': 'Gigantism', 'colour': 12, 'grow': 5}}
        json.dump(q, open(path, 'w'))
        path = os.path.join(folder, 'tiles.json')
        tiles = json.load(open(path))
        tiles['walls'].append({'id': 43, 'name': 'Barricade', 'solid': True, 'giant_breaks': True,
                               'message': 'Crash!'})
        json.dump(tiles, open(path, 'w'))
        shutil.copy(os.path.join(folder, 'sprites', 'walls', '1.png'), os.path.join(folder, 'sprites', 'walls', '43.png'))
        path = os.path.join(folder, 'items.json')
        data = json.load(open(path))
        data['items'] += [
            {'id': 2001, 'name': 'Big Mushroom', 'type': 'treasure', 'pickup': {'grow': 6, 'message': 'Mmm.'}},
            {'id': 2002, 'name': 'Small Mushroom', 'type': 'treasure', 'pickup': {'shrink': 6}},
            {'id': 2003, 'name': 'Bad Mushroom', 'type': 'treasure', 'pickup': {'poison': True, 'life': -2}},
            {'id': 2010, 'name': 'Ring of Mending', 'type': 'amulet', 'regen': 2, 'mana_regen': 1, 'sight': 3,
             'thorns': 4, 'lifesteal': 50, 'see_invisible': True, 'water_walk': True, 'poison_immune': True},
            {'id': 2011, 'name': 'Ring of Shrinking', 'type': 'amulet', 'makes_small': True},
            {'id': 2012, 'name': 'Belt of Giants', 'type': 'amulet', 'makes_giant': True}]
        json.dump(data, open(path, 'w'))
    from engine.state import add_potions, SLOT_AMULET, Enemy
    g = with_changes(setup)
    p, w, h = g.player, g.world, g.player.hero
    for e in list(w.enemies):
        w.sq(e.x, e.y).mon = 0
    w.enemies.clear()
    assert g.size_state() == 'normal' and g.renderer.EYES['small'] < 0.5 < g.renderer.EYES['giant']
    # the eye: lower when small, higher when a giant; the frame differs
    g.view3d = True
    g.renderer.draw(g, present=False)
    normal = pygame.image.tostring(g.renderer.screen.subsurface((0, 0, 400, 400)), 'RGB')
    add_potions(p, 9, 1)
    add_potions(p, 10, 1)
    assert g.drink_extra(9) and g.size_state() == 'small'
    for _ in range(40):
        g.renderer.draw(g, present=False)                        # the eye eases down over a few frames
    assert abs(g.renderer._eye_now - g.renderer.EYES['small']) < 0.02
    small = pygame.image.tostring(g.renderer.screen.subsurface((0, 0, 400, 400)), 'RGB')
    assert small != normal
    assert g.drink_extra(10) and g.size_state() == 'normal' and not p.more.get('shrunk')     # they cancel
    add_potions(p, 10, 1)
    assert g.drink_extra(10) and g.grown() and g.size_state() == 'giant'
    for _ in range(40):
        g.renderer.draw(g, present=False)
    giant = pygame.image.tostring(g.renderer.screen.subsurface((0, 0, 400, 400)), 'RGB')
    assert giant != normal and giant != small
    # a giant smashes the barricade; a normal hero cannot, and a giant hits half as hard again
    w.sq(p.X + 1, p.Y).wall = 43
    x0 = p.X
    assert g.try_move(1, 0) and w.sq(x0 + 1, p.Y).wall == 0 and p.X == x0
    g.view3d = False
    g.renderer.draw(g, present=False)                            # a giant is drawn big
    p.more.pop('grown')
    w.sq(p.X + 1, p.Y).wall = 43
    assert not g.try_move(1, 0) and w.sq(p.X + 1, p.Y).wall == 43
    w.sq(p.X + 1, p.Y).wall = 0
    # mushrooms: picked up with Enter, used on the spot
    q = w.sq(p.X, p.Y)
    q.item = 2001
    assert g.pick_up() and q.item == 0 and g.grown() and not any(v == 2001 for v in p.bag.values())
    p.more.pop('grown')
    q.item = 2002
    g.pick_up()
    assert g.shrunk()
    p.more.pop('shrunk')
    h.life = h.mlife
    q.item = 2003
    g.pick_up()
    assert h.poisoned == 1 and h.life == h.mlife - 2
    h.poisoned = 0
    # what he wears
    p.bag[SLOT_AMULET] = 2010
    rules_ok = g.worn_sum('regen') == 2 and g.sight_bonus() == 3 and g.foresight()
    assert rules_ok
    h.life = h.mlife - 10
    h.mana = max(0, h.mmana - 5)
    life, mana = h.life, h.mana
    g.upkeep()
    assert h.life == life + 2 and h.mana == mana + 1
    g.combat.poison_hero()
    assert not h.poisoned                                          # immune
    foe = g.spawn(1, p.X + 1, p.Y)
    foe.att, foe.life, foe.mlife, foe.atk, foe.power = 9, 50, 50, 1000, 5
    before = foe.life
    g.combat.enemy_melee(foe, 'foe')
    assert foe.life < before                                       # thorns hurt it
    w.sq(p.X + 1, p.Y).mon = 0
    w.enemies.clear()
    wallet = w.sq(p.X + 1, p.Y)
    wallet.wall = 2                                                # water
    g.pack.walls[2]['water'] = True
    assert g.try_move(1, 0)                                        # walked on with the ring
    p.X -= 1
    p.bag[SLOT_AMULET] = 0
    assert not g.try_move(1, 0)                                    # and not without
    p.bag[SLOT_AMULET] = 2010
    p.bag[SLOT_AMULET] = 2011
    assert g.shrunk()
    p.bag[SLOT_AMULET] = 2012
    assert g.grown()
    p.bag[SLOT_AMULET] = 0
    assert g.size_state() == 'normal' and g.sight_bonus() == 0
    print('sizes and worn items: eye height, gigantism, mushrooms, regen, thorns, sight, immunities: ok')


def fps_settings():
    import tempfile
    from engine import settings as player_settings, view3d
    from engine.game import Game
    path = os.path.join(tempfile.mkdtemp(), 'settings.ini')
    open(path, 'w').write('[play]\nfps_quality = high\nfps_dither = fine\nfps_view_distance = 20\n')
    got = player_settings.load(path)
    assert (got['fps_quality'], got['fps_dither'], got['fps_view_distance']) == ('high', 'fine', 20)
    open(path, 'w').write('[play]\nfps_quality = huge\nfps_dither = ?\nfps_view_distance = 99\n')
    got = player_settings.load(path)
    assert (got['fps_quality'], got['fps_dither'], got['fps_view_distance']) == ('normal', 'ordered', 'level')
    shots = {}
    for name, settings in (('normal', {}), ('high', {'fps_quality': 'high'}), ('low', {'fps_quality': 'low'}),
                           ('far', {'fps_view_distance': 25}), ('fine', {'fps_dither': 'fine'}),
                           ('smooth', {'fps_dither': 'smooth'}), ('off', {'fps_dither': 'off'})):
        g = Game(pygame.Surface((640, 480)), settings=settings)
        g.quick_start(1, 1)
        g.view3d = True
        g.facing = 2                                             # looking south: the start is at the map's north edge
        for x in range(1, 101):                                  # open ground, so that the fog shows
            for y in range(1, 101):
                q = g.world.sq(x, y)
                q.wall = q.mon = q.item = q.deco = 0
        g.world.enemies.clear()
        g.renderer.draw(g, present=False)
        shots[name] = pygame.image.tostring(g.renderer.screen.subsurface((0, 0, 400, 400)), 'RGB')
        assert view3d.RES == view3d.QUALITY[settings.get('fps_quality', 'normal')]
        if name == 'far':
            assert g.renderer.scene3d(g).range == 25 and g.renderer.v3d.frame.get_width() == view3d.RES
    assert len(set(shots.values())) == len(shots), 'every setting changes the picture'
    Game(pygame.Surface((640, 480))).renderer                       # a game without settings is back to normal
    assert view3d.RES == 200
    # the texture filter: a far path of pebbles is averaged, not skipped
    frames = {}
    for name, st in (('on', {'fps_texture_filter': 'on'}), ('off', {})):          # off is the default
        g = Game(pygame.Surface((640, 480)), settings=st)
        g.quick_start(1, 1)
        g.view3d = True
        g.facing = 2
        for x in range(1, 101):
            for y in range(1, 101):
                q = g.world.sq(x, y)
                q.wall = q.mon = q.item = q.deco = 0
                q.floor = 2 if 3 <= x <= 7 and y >= 6 else 1
        g.world.enemies.clear()
        g.renderer.draw(g, present=False)
        frames[name] = pygame.image.tobytes(g.renderer.v3d.frame, 'RGB')
    assert frames['on'] != frames['off'], 'the filter changes the far ground'
    assert 'fps_texture_filter' in player_settings.load(path)
    # the fog fade: starting later leaves more of the view crisp
    ends = {}
    for name, st in (('early', {'fps_fog_start': 20}), ('late', {'fps_fog_start': 100})):
        g = Game(pygame.Surface((640, 480)), settings=st)
        g.quick_start(1, 1)
        g.view3d = True
        g.facing = 2
        for x in range(1, 101):
            for y in range(1, 101):
                q = g.world.sq(x, y)
                q.wall = q.mon = q.item = q.deco = 0
                q.floor = 2 if 3 <= x <= 7 and y >= 6 else 1
        g.world.enemies.clear()
        g.renderer.draw(g, present=False)
        ends[name] = pygame.image.tobytes(g.renderer.v3d.frame, 'RGB')
    assert ends['early'] != ends['late']
    # render_quality: one switch for how finely FPS mode is drawn
    open(path, 'w').write('[play]\nrender_quality = ultra\n')
    got = player_settings.load(path)
    assert (got['fps_quality'], got['smooth_scaling']) == ('max', 'off')       # quality does not blur the picture
    open(path, 'w').write('[play]\nrender_quality = high\nfps_quality = ultra\n')
    got = player_settings.load(path)
    assert got['fps_quality'] == 'ultra', 'never coarser than fps_quality'
    window = pygame.display.set_mode((1280, 960))
    g = Game(window, settings={'render_quality': 'ultra', 'smooth_scaling': 'on'})
    g.quick_start(1, 1)
    g.view3d = True
    assert view3d.RES == view3d.QUALITY['max'] and g.renderer.smooth
    g.renderer.draw(g, present=False)
    g.renderer.present()                                            # scaled smoothly to the window
    assert g.renderer.v3d.frame.get_width() == 600
    pygame.display.set_mode((640, 480))
    Game(pygame.Surface((640, 480)))                                # back to normal for what follows
    assert view3d.RES == 200
    print('settings.ini: FPS quality, view distance and dithering, and bad values fall back: ok')


def creature_changes():
    def traits(folder, json):
        path = os.path.join(folder, 'creatures.json')
        data = json.load(open(path))
        for r in data['creatures']:
            if r['id'] == 1:
                r['becomes_on_death'] = 2                      # an imp turns into an orc
            if r['id'] == 3:
                r['bursts_into'] = {'1': 3}                     # breaks into three imps
            if r['id'] == 4:
                r.update({'transforms_into': 5, 'transforms_below': 50})
            if r['id'] == 6:
                r.update({'transforms_into': 5, 'transforms_damage': 7})
            if r['id'] == 7:
                r['hit_drops'] = [[0, 50, 'gold', 5, 10], [50, 100, 'item', 620]]
        json.dump(data, open(path, 'w'))
    g = with_changes(traits)
    p, w, pk = g.player, g.world, g.pack
    ox, oy = w.origin
    for e in list(w.enemies):
        w.sq(e.x, e.y).mon = 0
    w.enemies.clear()
    for x, y in w.room_tiles():
        q = w.sq(x, y)
        q.wall = q.mon = q.item = q.deco = q.gold = 0
    p.X, p.Y = ox, oy
    # turns into another creature on death
    a = g.spawn(1, ox + 5, oy + 5)
    g.combat.hurt(1000, a, 3, by_hero=True)
    now = w.enemy_at(ox + 5, oy + 5)
    assert now is not None and now.type == 2 and now.life == now.mlife and w.sq(ox + 5, oy + 5).mon == 2
    assert w.sq(ox + 5, oy + 5).deco == 0                       # no body: it did not die
    w.enemies.clear()
    w.sq(ox + 5, oy + 5).mon = 0
    # bursts into several
    b = g.spawn(3, ox + 5, oy + 5)
    g.combat.hurt(1000, b, 3, by_hero=True)
    kids = [e for e in w.enemies if e.type == 1]
    assert len(kids) == 3 and all(max(abs(e.x - (ox + 5)), abs(e.y - (oy + 5))) <= 2 for e in kids)
    assert w.sq(ox + 5, oy + 5).deco != 0                       # and it leaves its body
    for e in list(w.enemies):
        w.sq(e.x, e.y).mon = 0
    w.enemies.clear()
    # transforms when its life is low (percent), or after damage taken
    c = g.spawn(4, ox + 3, oy + 3)
    c.life = c.mlife * 6 // 10 or 1
    g.combat.check_dead()
    assert c.type == 4
    g.combat.hurt(max(1, c.life - c.mlife // 2 + 1), c, 3, by_hero=True)
    g.combat.check_dead()
    assert c.type == 5 and c.life == c.mlife and w.sq(ox + 3, oy + 3).mon == 5
    d = g.spawn(6, ox + 7, oy + 7)
    d.life = d.mlife = max(d.mlife, 30)
    d.life -= 5
    g.combat.check_dead()
    assert d.type == 6
    d.life -= 3
    g.combat.check_dead()
    assert d.type == 5
    # drops something each time it is hit
    e = g.spawn(7, ox + 8, oy + 3)
    e.life = e.mlife = 500
    drops = 0
    for _ in range(12):
        gold, items = w.sq(e.x, e.y).gold, sum(1 for x, y in w.room_tiles() if w.sq(x, y).item)
        g.combat.hurt(1, e, 3, by_hero=True)
        drops += (w.sq(e.x, e.y).gold > gold) + (sum(1 for x, y in w.room_tiles() if w.sq(x, y).item) > items)
    assert drops >= 8, drops                                    # every hit let something fall (rolls 1-100, all covered)
    g.combat.hurt(3, e, 3, by_hero=True, how='burning')         # burning is not a hit
    print('creatures: turn into another on death, burst into several, transform when hurt, drop things when hit: ok')


def behaviour():
    def traits(folder, json):
        path = os.path.join(folder, 'creatures.json')
        data = json.load(open(path))
        for r in data['creatures']:
            if r['id'] == 1:
                r['chase_range'] = 3
            if r['id'] == 2:
                r['flees_within'] = 4
            if r['id'] == 3:
                r.update({'regenerates_from_blood': True, 'rise_limit': 2})
        json.dump(data, open(path, 'w'))
        path = os.path.join(folder, 'quest.json')
        q = json.load(open(path))
        q['giant_size'] = 2
        q['potions'] = {'9': {'name': 'Gigantism', 'colour': 12, 'grow': 8}}
        json.dump(q, open(path, 'w'))
    from engine.ai import monsmove
    from engine.state import add_potions
    g = with_changes(traits)
    p, w, pk = g.player, g.world, g.pack
    ox, oy = w.origin

    def clear():
        for e in list(w.enemies):
            w.sq(e.x, e.y).mon = 0
        w.enemies.clear()
        for x, y in w.room_tiles():
            q = w.sq(x, y)
            q.wall = q.mon = q.item = q.deco = q.gold = 0
    clear()
    p.X, p.Y = ox + 5, oy + 5
    # chases only within its range
    near = g.spawn(1, ox + 5, oy + 1)                             # 4 squares away
    near.att = 9
    for _ in range(3):
        monsmove(g)
        near.moved = False
    assert (near.x, near.y) == (ox + 5, oy + 1), 'out of its chase range it stays where it is'
    p.Y = oy + 3                                                  # now 2 squares away
    monsmove(g)
    assert abs(near.y - p.Y) < 2 or near.y > oy + 1, 'within range it comes'
    clear()
    # runs away, and fights when cornered
    p.X, p.Y = ox + 5, oy + 5
    runner = g.spawn(2, ox + 5, oy + 7)
    runner.att = 9
    for _ in range(3):
        before = max(abs(runner.x - p.X), abs(runner.y - p.Y))
        monsmove(g)
        runner.moved = False
        assert max(abs(runner.x - p.X), abs(runner.y - p.Y)) >= before
    assert max(abs(runner.x - p.X), abs(runner.y - p.Y)) > 2
    for _ in range(12):
        monsmove(g)
        runner.moved = False
    clear()
    p.X, p.Y = ox + 1, oy + 1
    trapped = g.spawn(2, ox, oy)                                  # in a corner, the hero next to it
    trapped.att, trapped.atk, trapped.power = 9, 1000, 1
    w.sq(ox, oy + 1).wall = 1                                     # walled in on the other side
    p.X, p.Y = ox + 1, oy
    life = p.hero.life
    g.combat.enemy_attacks()
    assert p.hero.life < life, 'cornered, it fights'
    clear()
    # rises from blood a limited number of times
    p.X, p.Y = ox + 8, oy + 8
    blood = pk.deco('blood')
    w.sq(ox + 1, oy + 1).deco = w.sq(ox + 1, oy + 2).deco = w.sq(ox + 2, oy + 1).deco = blood
    m = g.spawn(3, ox + 4, oy + 4)
    risen = 0
    for _ in range(4):
        g.combat.hurt(10000, m, 3, by_hero=True)
        for _ in range(12):
            g.combat.revive_step()
        m = w.enemy_at(ox + 4, oy + 4)
        if m is None:
            break
        risen += 1
        w.sq(ox + 1, oy + 1).deco = w.sq(ox + 1, oy + 2).deco = w.sq(ox + 2, oy + 1).deco = blood   # more blood
    assert risen == 2, risen
    clear()
    # a giant that takes up space: 2 x 2, restricted by walls, and the potion needs room
    p.X, p.Y = ox + 5, oy + 5
    ring = [(p.X + i, p.Y + j) for i in (-1, 0, 1) for j in (-1, 0, 1) if (i, j) != (0, 0)]
    for cx, cy in ring:
        w.sq(cx, cy).wall = 1                                     # trees all round: no room to grow
    add_potions(p, 9, 1)
    assert not g.drink_extra(9) and not g.grown()
    for cx, cy in ring:
        w.sq(cx, cy).wall = 0
    assert g.drink_extra(9) and g.grown() and g.hero_size() == 2
    x0 = p.X
    w.sq(p.X + 2, p.Y).wall = w.sq(p.X + 2, p.Y + 1).wall = 0
    w.sq(p.X + 2, p.Y + 1).wall = 1                               # blocks only the lower right square of the move
    assert not g.try_move(1, 0) and p.X == x0, 'it does not all fit'
    w.sq(p.X + 2, p.Y + 1).wall = 0
    assert g.try_move(1, 0) and p.X == x0 + 1
    g.renderer.draw(g, present=False)                            # drawn over his four squares
    print('behaviour: chases within a range, runs away, rises a limited number of times, a giant fills 2 x 2: ok')


def usable_items():
    def food(folder, json):
        path = os.path.join(folder, 'items.json')
        data = json.load(open(path))
        data['items'] += [{'id': 2101, 'name': 'Bread', 'type': 'treasure', 'use': {'life': 20, 'message': 'Tasty.'}},
                          {'id': 2102, 'name': 'Mana Root', 'type': 'treasure', 'use': {'mana': 'half'}},
                          {'id': 2103, 'name': 'Antidote Leaf', 'type': 'treasure', 'use': {'cure_poison': True}}]
        json.dump(data, open(path, 'w'))
    from engine import invshop
    from engine.game import PageHost
    g = with_changes(food)
    p, h = g.player, g.player.hero
    h.life, h.mana = h.mlife - 30, 0
    h.poisoned = 1
    p.bag[(12, 8)], p.bag[(13, 8)], p.bag[(14, 8)] = 2101, 2102, 2103
    p.bag[(15, 8)] = 201                                            # an ordinary item: Enter equips as before
    host = PageHost(g, g.page_layer(), {})
    gen = invshop.inventory(host, 1)

    def press(*keys):
        """Run the page until it asks for a key, give it each key in turn."""
        out = next(gen)
        for k in keys:
            while out is not invshop.KEY:
                out = gen.send(None)
            out = gen.send(k)
        while out is not invshop.KEY:
            out = gen.send(None)
    life = h.life
    press(13)                                                       # Enter on the bread at (12, 8)
    assert h.life == life + 20 and p.bag.get((12, 8), 0) == 0
    press(77, 13)                                                   # right, Enter: the mana root
    assert h.mana == h.mmana // 2 + h.mmana % 2 and p.bag.get((13, 8), 0) == 0
    press(77, 13)                                                   # the antidote leaf
    assert not h.poisoned and p.bag.get((14, 8), 0) == 0
    print('items: Enter on food in the inventory restores life, mana, cures poison, and is used up: ok')


def loot_stays_only_when_cleared():
    """goroom2(): leaving a screen with hostile creatures alive loses the loot lying on it (gold goes back to
    what the screen had on arrival, an item that is not what it had is wiped); picked-up things stay picked up;
    with the screen cleared everything stays."""
    def leave(hostile, setup):
        g = with_changes(lambda folder, json: None)
        w = g.world
        w.enemies = []
        for x, y in w.room_tiles():
            w.grid[x][y].mon = 0
        ox, oy = w.origin
        far = [(ox + 1 + i, oy + 1) for i in range(4)]
        for x, y in far:
            w.grid[x][y].item = w.grid[x][y].gold = 0
        w.grid[far[0][0]][far[0][1]].item = 2                     # lay there on arrival
        w.grid[far[1][0]][far[1][1]].gold = 7
        g.events.snapshot()
        setup(w, far)
        w.leave_room(1 if hostile else 0, g.events.shadow)
        return [(w.grid[x][y].item, w.grid[x][y].gold) for x, y in far]

    def play(w, far):
        w.grid[far[0][0]][far[0][1]].item = 0                      # picked up
        w.grid[far[1][0]][far[1][1]].gold = 0                      # picked up
        w.grid[far[2][0]][far[2][1]].item = 5                      # dropped or fallen
        w.grid[far[3][0]][far[3][1]].gold = 30                     # fallen
    assert leave(True, play) == [(0, 0), (0, 0), (0, 0), (0, 0)]
    assert leave(False, play) == [(0, 0), (0, 0), (5, 0), (0, 30)]
    assert leave(True, lambda w, far: None) == [(2, 0), (0, 7), (0, 0), (0, 0)]   # untouched loot is kept
    print('loot: with enemies left it is lost, picked-up things stay picked up, a cleared screen keeps it: ok')


def fps_transition():
    """F zooms the map down and in (and back out) instead of switching; settings.ini fps_transition = off, and tests (fast), don't."""
    import engine.render as R
    g = with_changes(lambda folder, json: None)
    assert g.view_fx is None if hasattr(g, 'view_fx') else True
    g.fast = False
    g.settings = {'fps_transition': 'on'}
    g.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_f, unicode='f', mod=0))
    assert g.view3d and g.view_fx and g.view_fx[1] is True
    t0 = g.view_fx[0]
    real = pygame.time.get_ticks
    try:
        seen = []
        for ms in (0, R.FX_MS // 4, R.FX_MS // 2, R.FX_MS * 3 // 4):
            pygame.time.get_ticks = lambda ms=ms: t0 + ms
            seen.append(g.renderer.transition(g))
            g.renderer.draw(g, present=False)                  # every stage draws
        assert seen[0] < seen[1] < seen[2] < seen[3] <= 1 and abs(seen[2] - 0.5) < 1e-6, seen
        pygame.time.get_ticks = lambda: t0 + R.FX_MS + 1
        assert g.renderer.transition(g) is None and g.view_fx is None       # over
        g.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_f, unicode='f', mod=0))
        assert not g.view3d and g.view_fx[1] is False
        t1 = g.view_fx[0]
        pygame.time.get_ticks = lambda: t1 + R.FX_MS // 4
        assert g.renderer.transition(g) > 0.5 and g.renderer.transition(g) < 1       # going out starts from the view
        g.renderer.draw(g, present=False)
    finally:
        pygame.time.get_ticks = real
    g.view_fx = None
    g.view3d = True
    seen = []
    real_box = g.renderer.map_box
    g.renderer.map_box = lambda game, scr: seen.append('map')
    g.renderer.draw(g, present=False)
    g.renderer.draw(g, present=False, flat=True)             # the frames an animation draws: the panel stays (no grey box)
    g.renderer.map_box = real_box
    assert seen == ['map', 'map'], seen
    g.view3d = False
    g.settings = {'fps_transition': 'off'}
    g.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_f, unicode='f', mod=0))
    assert g.view3d and g.view_fx is None                     # off: it just switches
    g.fast = True
    g.settings = {}
    g.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_f, unicode='f', mod=0))
    assert g.view_fx is None
    print('fps transition: the map zooms in and the eye drops (and back out), off and fast just switch: ok')


def standing_effects():
    """Tiles that hurt or heal, and worn items that do something on blood (or any floor, decoration or item)."""
    def ring(folder, json):
        path = os.path.join(folder, 'items.json')
        data = json.load(open(path))
        amulet = dict(next(r for r in data['items'] if r.get('type') == 'amulet'))
        amulet.update({'id': 2700, 'name': 'Ring of Rage', 'stand_on': 'blood', 'stand_effect': 'berserk', 'stand_amount': 4})
        data['items'].append(amulet)
        json.dump(data, open(path, 'w'))
        path = os.path.join(folder, 'tiles.json')
        t = json.load(open(path))
        t['floors'].append({'id': 60, 'name': 'Lava', 'hurts': 3})
        t['floors'].append({'id': 61, 'name': 'Spring', 'heals': 2})
        json.dump(t, open(path, 'w'))
    g = with_changes(ring)
    p, h, w = g.player, g.player.hero, g.world
    q = w.sq(p.X, p.Y)
    q.deco = q.item = 0
    g.upkeep()
    assert g.status.powboost <= 0                                 # nothing here, nothing happens
    from engine.game import SLOT_AMULET
    p.bag[SLOT_AMULET] = 2700
    q.deco = g.pack.deco('blood')
    g.upkeep()
    assert g.status.powboost == 3 and g.status.armboost == 3, (g.status.powboost, g.status.armboost)   # 4, less this turn's
    for _ in range(5):
        g.upkeep()
    assert g.status.powboost == 3                                 # stays on while he stands in the blood
    q.deco = 0
    for _ in range(6):
        g.upkeep()
    assert g.status.powboost <= 0                                 # and fades after he steps off
    # tiles
    h.life = h.mlife = 50
    q.floor = 60
    g.upkeep()
    assert h.life == 47, h.life
    q.floor = 61
    g.upkeep()
    assert h.life == 49, h.life
    q.floor = 1
    g.upkeep()
    assert h.life == 49
    # a plain amulet or no tile fields: nothing changes
    p.bag.pop(SLOT_AMULET)
    q.deco = g.pack.deco('blood')
    g.upkeep()
    assert g.status.powboost <= 0
    print('standing: blood wakes the ring\'s rage, lava hurts, a spring heals, nothing else changes: ok')


def hands_react():
    from engine.game import Game
    from engine.state import SLOT_WEAPON, SLOT_OFFHAND
    g = Game(pygame.Surface((640, 480)))
    g.quick_start(1, 1)
    g.view3d = True
    g.renderer.draw(g, present=False)
    hands = g.renderer.hands
    now = 50000
    g.hand_fx = ('hit', now - 190)
    hx, hy, ha = hands.reaction(g, now)
    assert hx < -40 and hy > 30 and ha < 0                       # knocked away (left) and down
    g.hand_fx = ('miss', now - 230)
    mx, my, ma = hands.reaction(g, now)
    assert mx > 40 and my < -30 and ma > 0                       # brought up and across, to block
    g.hand_fx = ('hit', now - 5000)
    assert hands.reaction(g, now) == (0.0, 0.0, 0.0)             # over
    # the left hand strikes on the second blow only: the right hand rests then
    p = g.player
    p.bag[SLOT_WEAPON], p.bag[SLOT_OFFHAND] = 201, 202
    g.start_swing()
    assert g.swing_hand == 'right'
    g.start_swing(second=True)
    assert g.swing_hand == 'left'
    g.swing = ('swing', now - 140)
    assert hands.pose(g, now, swinging=False) == (0.0, 0.0, 0.0)
    assert hands.pose(g, now, swinging=True)[0] < -40
    for hand, fx in (('right', None), ('left', None), ('right', ('hit', now - 100)), ('right', ('miss', now - 100))):
        g.swing_hand, g.hand_fx = hand, fx
        scr = pygame.Surface((400, 400))
        hands.draw(g, scr, now)                                   # every combination draws
    # the weapons trade places in the bag while the second blow is worked out: in view each stays in its own hand
    g.swing, g.swing_hand, g.hand_fx = None, 'right', None
    scr = pygame.Surface((400, 400))
    scr.fill((0, 0, 0))
    hands.draw(g, scr, now)
    rest = pygame.image.tobytes(scr, 'RGB')
    p.bag[SLOT_WEAPON], p.bag[SLOT_OFFHAND] = p.bag[SLOT_OFFHAND], p.bag[SLOT_WEAPON]
    g.slots_swapped = True
    scr.fill((0, 0, 0))
    hands.draw(g, scr, now)
    assert pygame.image.tobytes(scr, 'RGB') == rest, 'a swapped bag does not swap the hands in view'
    g.slots_swapped = False
    p.bag[SLOT_WEAPON], p.bag[SLOT_OFFHAND] = p.bag[SLOT_OFFHAND], p.bag[SLOT_WEAPON]
    from engine.combat import Combat
    g.hand_fx = None
    g.fast = False
    g.hand_react('hit')
    assert g.hand_fx and g.hand_fx[0] == 'hit'
    print('hands: the second blow is the left hand\'s, a shield is knocked away by a hit and comes up for a miss: ok')


def water_walking():
    def amulet(folder, json):
        path = os.path.join(folder, 'items.json')
        data = json.load(open(path))
        data['items'].append({'id': 2020, 'name': 'Undine Amulet', 'type': 'amulet', 'water_walk': True})
        json.dump(data, open(path, 'w'))
    from engine.state import SLOT_AMULET
    g = with_changes(amulet)
    p, w = g.player, g.world
    for e in list(w.enemies):
        w.sq(e.x, e.y).mon = 0
    w.enemies.clear()
    sq = w.sq(p.X + 1, p.Y)
    sq.wall = sq.mon = sq.item = 0
    sq.wall = 2                                                    # the Quest's own Water, as the pack ships it
    assert g.pack.wall(2).get('water'), "the pack's water is marked as water"
    x0 = p.X
    assert not g.try_move(1, 0) and p.X == x0                       # without the amulet, water stops him
    p.bag[SLOT_AMULET] = 2020
    assert g.try_move(1, 0) and p.X == x0 + 1                       # with it he walks on the water
    print('water walking: the amulet carries him over the pack\'s water: ok')


if __name__ == '__main__':
    fire()
    ice()
    elements()
    blood_regen()
    foresight()
    clones()
    water_walking()
    loot_stays_only_when_cleared()
    fps_transition()
    standing_effects()
    hands_react()
    usable_items()
    behaviour()
    creature_changes()
    fps_settings()
    resurrection()
    followers_and_mending()
    shrinking()
    sizes_and_worn()
    disguise()
    event_code_text()
    links()
    moved_walls()
    painted_hero()
    big_creature(sys.argv[1] if len(sys.argv) > 1 else None)
    print('all extras checks passed')
