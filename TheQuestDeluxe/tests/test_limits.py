"""The Quest Deluxe past the original's limits.

  - The save file: a Quest I game saves exactly as the original does (no DELUXE block); a game with
    more than the original holds keeps the rest in the DELUXE block, and loads back whole; the
    classic part of such a save still loads in the classic port's reader (as in the original's).
  - More than 20 spells: the spell book grows pages, a level-up offers the new spells, a spell on page
    2 is shown, chosen and cast, and the lot saves and loads.

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


def main():
    saves()
    spells()
    print('all limit checks passed')


if __name__ == '__main__':
    main()
