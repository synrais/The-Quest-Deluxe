"""Quest packs and the editor's model of them.

  - packs/quest1 goes through the editor's model and back byte for byte;
  - level settings edit the script and keep its comments;
  - a new blank pack keeps the things (items, creatures, ...) but has one empty level;
  - Deluxe plays the blank pack: a hero dropped on its level walks about.
"""
import os
import shutil
import sys
import tempfile

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from editor.project import Project, TABLES, TEXTS  # noqa: E402

tmp = tempfile.mkdtemp()
quest1 = os.path.join(ROOT, 'packs', 'quest1')


def same_tree(a, b):
    for base, _, files in os.walk(a):
        for f in files:
            pa = os.path.join(base, f)
            pb = os.path.join(b, os.path.relpath(pa, a))
            with open(pa, 'rb') as fa, open(pb, 'rb') as fb:
                if fa.read() != fb.read():
                    return os.path.relpath(pa, a)
    return None


# round trip: rewrite every file, nothing changes
copy = os.path.join(tmp, 'rt')
shutil.copytree(quest1, copy)
p = Project(copy)
for n in range(1, p.levels + 1):
    p.grid(n)
    p.dirty |= {('map', n), ('script', n), ('shops', n)}
p.dirty |= set(TABLES) | set(TEXTS) | {'quest', 'tiles', ('script', 0)}
p.save()
diff = same_tree(quest1, copy)
assert diff is None, f'{diff} changed on a round trip'
print('round trip: packs/quest1 unchanged')

# level settings
p.set_constant(3, 'START', (10, 20))
p.set_constant(3, 'PEACEFUL_SCREENS', [(2, 2)], 'people leave monsters alone here')
assert p.constant(3, 'START') == (10, 20) and p.constant(3, 'PEACEFUL_SCREENS') == [(2, 2)]
p.set_constant(1, 'START', (12, 34))
line = next(s for s in p.scripts[1].splitlines() if s.startswith('START'))
assert line.index('#') == 36 and 'newmap()' in line, line     # the comment stays, in its column
print('settings: START and PEACEFUL_SCREENS written, comments kept')

# a blank pack, and a level added to it
blank = Project.create(os.path.join(tmp, 'blank'), quest1, blank=True)
assert blank.levels == 1 and len(blank.tables['items']) == len(p.tables['items'])
g = blank.grid(1)
assert all(g.get(x, y) == [1, 0, 0, 0, 0, 0] for x in (1, 50, 100) for y in (1, 50, 100))
g.get(8, 5)[3] = 1                                       # a monster to meet
blank.touch(('map', 1))
n = blank.add_level()
blank.save()
assert n == 2 and Project(blank.root).levels == 2
print('blank pack: one empty level, the things kept, a second level added')

# Deluxe plays it
os.environ['QUEST_PACK'] = blank.root
import pygame  # noqa: E402

pygame.init()
pygame.display.set_mode((640, 480))
from deluxe.game import Game  # noqa: E402

game = Game(pygame.Surface((640, 480)))
assert game.pack.root == blank.root
game.quick_start(1, 1, (6, 5))
assert (game.player.X, game.player.Y) == (6, 5) and game.world.level == 1
for k in (pygame.K_RIGHT, pygame.K_RIGHT, pygame.K_DOWN, pygame.K_LEFT):
    game.handle(pygame.event.Event(pygame.KEYDOWN, key=k, unicode=''))
game.renderer.draw(game)
print(f'Deluxe on the blank pack: hero at ({game.player.X}, {game.player.Y}), '
      f'{len(game.world.enemies)} creature(s) on the screen')
print('all pack checks passed')
