"""The Quest Deluxe past the original's limits.

  - The save file: a Quest I game saves exactly as the original does (no DELUXE block); a game with
    more than the original holds keeps the rest in the DELUXE block, and loads back whole; the
    classic part of such a save still loads in the classic port's reader (as in the original's).

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


def main():
    saves()
    print('all limit checks passed')


if __name__ == '__main__':
    main()
