"""The Quest Deluxe past the original's limits.

  - The save file: a Quest I game saves exactly as the original does (no DELUXE block); a game with
    more than the original holds keeps the rest in the DELUXE block, and loads back whole; the
    classic part of such a save still loads in the classic port's reader (as in the original's).
  - More than 20 spells: the spell book grows pages, a level-up offers the new spells, a spell on page
    2 is shown, chosen and cast, and the lot saves and loads.
  - Potions 9 and 10: defined in quest.json, started with, drunk with keys 9 and 0, picked up, on a belt
    of ten, saved and loaded.
  - More key colours: defined in quest.json, open their doors, drawn on the key panel, saved and loaded.

    python tests/test_limits.py
"""
from __future__ import annotations

import os
import sys
import tempfile

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import pygame  # noqa: E402

pygame.init()
pygame.display.set_mode((640, 480))

from engine.game import Game  # noqa: E402
from engine import savefile  # noqa: E402
from engine.savefile import Slots  # noqa: E402


def new_game():
    g = Game(pygame.Surface((640, 480)))
    g.slots = Slots(tempfile.mkdtemp())
    g.quick_start(1, 1)
    return g


def saves():
    g = new_game()
    plain = savefile.to_bytes(g.to_save())
    assert savefile.EXTRA.encode() not in savefile.decode_bytes(plain).encode(), 'a Quest I game wrote a DELUXE block'
    # the same game saved and loaded gives the same bytes again
    g.from_save(savefile.from_bytes(plain), 1)
    assert savefile.to_bytes(g.to_save()) == plain
    # past the original: spells 21-22, a third book page, and state of Deluxe's own
    p = g.player
    p.spells = p.spells + [1, 3]
    p.book = p.book + [21, 22] + [0] * 18
    p.more = {'potions': {'9': 2}, 'keys': {'green': 1}}
    raw = savefile.to_bytes(g.to_save())
    text = savefile.decode_bytes(raw)
    assert '\nDELUXE {' in text
    g2 = new_game()
    g2.from_save(savefile.from_bytes(raw), 1)
    q = g2.player
    assert q.spells[21:] == [1, 3] and q.book[20:22] == [21, 22], (q.spells[21:], q.book[20:])
    assert q.more == {'potions': {'9': 2}, 'keys': {'green': 1}}, q.more
    # the classic reader: it reads the original's numbers and stops, as load2() does
    classic_pkg = os.path.join(os.path.dirname(ROOT), 'TheQuestClassic', 'engine')
    if os.path.isdir(classic_pkg):
        import importlib.util
        spec = importlib.util.spec_from_file_location('classic', os.path.join(classic_pkg, '__init__.py'),
                                                      submodule_search_locations=[classic_pkg])
        mod = sys.modules['classic'] = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        import classic.savefile as cs
        d = cs.from_bytes(raw)
        assert d.spells[1:21] == q.spells[1:21] and d.hero['type'] == q.hero.type
        print('the save file: Quest I unchanged, the DELUXE block round trip, and the classic reader loads '
              'the original part: ok')
    else:
        print('the save file: Quest I unchanged and the DELUXE block round trip: ok (no classic edition beside '
              'this folder to check its reader)')


def pack_copy(change):
    """A copy of packs/TheQuest, changed by change(folder), and a game playing it."""
    import json
    import shutil
    from engine.formats import GameData
    from engine.pack import Pack, PackSource
    folder = os.path.join(tempfile.mkdtemp(), 'pack')
    shutil.copytree(os.path.join(ROOT, 'packs', 'TheQuest'), folder)
    change(folder, json)
    g = Game(pygame.Surface((640, 480)), data=GameData.load(PackSource(Pack(folder))))
    g.slots = Slots(tempfile.mkdtemp())
    return g


def press(g, k):
    g.handle(pygame.event.Event(pygame.KEYDOWN, key=k, unicode=''))


def spells():
    from engine import ui, rules

    def more_spells(folder, json):
        path = os.path.join(folder, 'spells.json')
        data = json.load(open(path))
        flame = next(r for r in data['spells'] if r['id'] == 2)
        for n in range(21, 26):
            data['spells'].append(dict(flame, id=n, name=f'Spell {n}', req_int=12))
        json.dump(data, open(path, 'w'))
    g = pack_copy(more_spells)
    assert g.pack.spell_count() == 25
    g.quick_start(2, 1)                                   # a Mage
    p = g.player
    assert len(p.spells) == 26 and len(p.book) == 40, (len(p.spells), len(p.book))
    # a level-up offers the new spells
    p.hero.bintl = 30
    rules.status_update(p, g.status, g.items)
    g.after_level_spells()
    assert isinstance(g.overlay, ui.LearnSpell) and {21, 25} <= set(g.overlay.c), g.overlay.c
    g.renderer.draw(g, present=False)                     # a long list scrolls
    g.overlay = None
    # a full first page: the next spell learnt goes on page 2
    for k in range(20):
        if not p.book[k]:
            p.book[k] = 99
    g.learn_spell(23)
    assert p.book[20] == 23 and p.spells[23] > 1
    p.spells[23] = 1                                      # learnt
    p.hero.mana = p.hero.mmana = 50
    ov = ui.SpellBook(g)
    g.overlay = ov
    press(g, pygame.K_RIGHT)
    press(g, pygame.K_RIGHT)                              # left column of page 2
    assert ov.i == 20 and ov.spell(g) == 23, ov.i
    g.renderer.draw(g, present=False)
    press(g, pygame.K_RETURN)                             # cast it: a bolt, so it asks for a target
    assert isinstance(g.overlay, ui.Cursor), type(g.overlay).__name__
    g.overlay = None
    g.cursor = None
    # Left from page 1 goes back to the last page's right column
    ov = ui.SpellBook(g)
    g.overlay = ov
    press(g, pygame.K_LEFT)
    assert ov.i == 30, ov.i
    g.overlay = None
    # saved and loaded
    for k in range(20):
        if p.book[k] == 99:
            p.book[k] = 0
    d = savefile.from_bytes(savefile.to_bytes(g.to_save()))
    assert d.extra.get('book', [])[:1] == [23] and d.extra['spells'][23 - 21] == 1, d.extra
    g.from_save(d, 1)
    assert g.player.book[20] == 23 and g.player.spells[23] == 1 and len(g.player.spells) == 26
    print('more than 20 spells: a second page, learnt, shown, cast, saved and loaded: ok')


def potions():
    from engine.state import potions as held

    def more_potions(folder, json):
        path = os.path.join(folder, 'quest.json')
        q = json.load(open(path))
        q['potions'] = {'9': {'name': 'Elixir of Life', 'colour': 10, 'life': 'full', 'mana': 5},
                        '10': {'name': 'Rage Draught', 'colour': 13, 'berserk': 5}}
        q['start_potions'] = {'6': 1, '9': 2}
        json.dump(q, open(path, 'w'))
        path = os.path.join(folder, 'items.json')
        items = json.load(open(path))
        items['items'].append({'id': 950, 'name': 'Rage Draught', 'type': 'potion', 'potion': 10, 'price': 30})
        json.dump(items, open(path, 'w'))
    g = pack_copy(more_potions)
    g.quick_start(1, 1)
    g.combat_log = True
    p, h = g.player, g.player.hero
    assert held(p, 9) == 2 and held(p, 6) == 1 and held(p, 10) == 0
    h.life, h.mana = 3, 0
    press(g, pygame.K_9)
    assert held(p, 9) == 1 and h.life == h.mlife and h.mana == min(5, h.mmana), (h.life, h.mana)
    assert any('elixir of life' in t for t, _, _ in g.log_lines)
    press(g, pygame.K_0)                                  # none of potion 10 yet: nothing happens
    assert g.status.powboost <= 0
    q = g.world.sq(p.X, p.Y)
    q.item = 950
    press(g, pygame.K_RETURN)                             # picked up
    assert held(p, 10) == 1 and q.item == 0
    press(g, pygame.K_0)
    assert held(p, 10) == 0 and g.status.powboost > 0
    g.renderer.draw(g, present=False)                     # the belt of ten
    d = savefile.from_bytes(savefile.to_bytes(g.to_save()))
    assert d.extra['more']['potions'] == {'9': 1}, d.extra
    g.from_save(d, 1)
    assert held(g.player, 9) == 1
    print('potions 9 and 10: started with, drunk (keys 9 and 0), picked up, on the belt, saved and loaded: ok')


def keys(shot=None):
    from engine.state import has_key

    def green_keys(folder, json):
        path = os.path.join(folder, 'quest.json')
        q = json.load(open(path))
        q['keys'] = {'green': 10, 'purple': {'colour': 5}}
        json.dump(q, open(path, 'w'))
        path = os.path.join(folder, 'items.json')
        items = json.load(open(path))
        items['items'].append({'id': 951, 'name': 'Green Key', 'type': 'key', 'key': 'green'})
        json.dump(items, open(path, 'w'))
        path = os.path.join(folder, 'tiles.json')
        tiles = json.load(open(path))
        tiles['walls'].append({'id': -40, 'name': 'Locked Green Key Door', 'door': 'locked', 'key': 'green'})
        json.dump(tiles, open(path, 'w'))
    g = pack_copy(green_keys)
    assert g.pack.extra_keys() == {'green': 10, 'purple': 5}, g.pack.extra_keys()
    g.quick_start(1, 1)
    g.combat_log = True
    p, w = g.player, g.world
    # a green door beside the hero: locked without the key
    door = w.sq(p.X + 1, p.Y)
    door.wall, door.mon, door.item = -40, 0, 0
    x0 = p.X
    press(g, pygame.K_RIGHT)
    assert w.sq(x0 + 1, p.Y).wall == -40 and p.X == x0
    assert any('green key' in t for t, _, _ in g.log_lines), g.log_lines
    # picked up, drawn on the key panel
    here = w.sq(p.X, p.Y)
    here.item = 951
    press(g, pygame.K_RETURN)
    assert has_key(p, 'green') and not has_key(p, 'purple') and here.item == 0 and p.more['keys'] == {'green': 1}
    g.renderer.draw(g, present=False)
    if shot:
        pygame.image.save(g.renderer.screen, shot)
    # saved and loaded
    d = savefile.from_bytes(savefile.to_bytes(g.to_save()))
    assert d.extra['more']['keys'] == {'green': 1}, d.extra
    g.from_save(d, 1)
    p, w = g.player, g.world
    assert has_key(p, 'green')
    # it opens the door
    w.sq(p.X + 1, p.Y).wall = -40
    w.sq(p.X + 1, p.Y).mon = 0
    press(g, pygame.K_RIGHT)
    assert w.sq(x0 + 1, p.Y).wall == 0, w.sq(x0 + 1, p.Y).wall
    # a new level takes it, as the original's keys
    w.load_level(2, p, g.status)
    assert not has_key(p, 'green') and 'keys' not in p.more
    print('more key colours: a locked green door, the key picked up, on the panel, saved, loaded, the door '
          'opened, and gone on a new level: ok')


def main():
    saves()
    spells()
    potions()
    keys(sys.argv[1] if len(sys.argv) > 1 else None)
    print('all limit checks passed')


if __name__ == '__main__':
    main()
