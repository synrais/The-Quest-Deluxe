"""Quest packs and the Studio's model of them.

  - packs/TheQuest goes through the Studio's model and back byte for byte;
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

from core.project import Project, TABLES, TEXTS  # noqa: E402

tmp = tempfile.mkdtemp()
TheQuest = os.path.join(ROOT, 'packs', 'TheQuest')


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
shutil.copytree(TheQuest, copy)
p = Project(copy)
for n in range(1, p.levels + 1):
    p.grid(n)
    p.dirty |= {('map', n), ('script', n), ('shops', n)}
p.dirty |= set(TABLES) | set(TEXTS) | {'quest', 'tiles', ('script', 0)}
p.save()
diff = same_tree(TheQuest, copy)
assert diff is None, f'{diff} changed on a round trip'
print('round trip: packs/TheQuest unchanged')

# level settings
p.set_constant(3, 'START', (10, 20))
p.set_constant(3, 'PEACEFUL_SCREENS', [(2, 2)], 'people leave monsters alone here')
assert p.constant(3, 'START') == (10, 20) and p.constant(3, 'PEACEFUL_SCREENS') == [(2, 2)]
p.set_constant(1, 'START', (12, 34))
line = next(s for s in p.scripts[1].splitlines() if s.startswith('START'))
assert line.index('#') == 36 and 'newmap()' in line, line     # the comment stays, in its column
print('settings: START and PEACEFUL_SCREENS written, comments kept')

# a blank pack, and a level added to it
blank = Project.create(os.path.join(tmp, 'blank'), TheQuest, blank=True)
assert blank.levels == 1 and len(blank.tables['items']) == len(p.tables['items'])
assert blank.quest.get('fixes') is True and 'map_fixes' not in blank.quest   # a new pack fixes the bugs
g = blank.grid(1)
assert all(g.get(x, y) == [1, 0, 0, 0, 0, 0] for x in (1, 50, 100) for y in (1, 50, 100))
g.get(8, 5)[3] = 1                                       # a monster to meet
# a new weapon, on the map and in a shop run by a shopkeeper
blank.tables['items'].append({'id': 1001, 'name': 'Sword of Tests', 'price': 50, 'type': 'weapon',
                              'bag_name': 'Sword of Tests', 'req_str': 5, 'req_int': 0, 'atk': 10, 'def': 0,
                              'warm': 0, 'marm': 0, 'str': 0, 'int': 0, 'power': 20, 'kind': 1, 'dex': 0, 'acc': 0})
blank.touch('items')
g.get(5, 6)[2] = 1001
g.get(5, 2)[3] = -5
blank.shops[1] = {1: '1001 1 3\n'}
blank.touch(('shops', 1))
blank.set_constant(1, 'SHOPS', {(1, 1): 1})
# a new monster (one blow kills it; it always leaves item 11) and a new class
blank.tables['creatures'].append({'id': 101, 'name': 'Test Slime', 'life': 1, 'power': 1, 'atk': 0, 'def': 0,
                                  'warm': 0, 'marm': 0, 'range': 1, 'att': 9, 'exp': 77,
                                  'loot': [[0, 100, 'item', 11]], 'bleeds': False, 'corpse': 'none'})
blank.touch('creatures')
g.get(3, 8)[3] = 101
blank.tables['classes'].append({'id': 5, 'name': 'Tester', 'life': 99, 'mana': 9, 'str': 30, 'int': 5, 'dex': 12,
                                'acc': 12, 'growth': [5, 1], 'skill': 'bar', 'look': {'colour': 14},
                                'bag': {'12,4': 1001}, 'spells': [1]})
blank.touch('classes')
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
from engine.game import Game  # noqa: E402

game = Game(pygame.Surface((640, 480)))
assert game.pack.root == blank.root
def press(*keys):
    for k in keys:
        game.handle(pygame.event.Event(pygame.KEYDOWN, key=k, unicode=''))


game.quick_start(3, 1, (5, 5))                          # a Rogue: no Ambidexterity, the sword goes in the hand
assert (game.player.X, game.player.Y) == (5, 5) and game.world.level == 1
press(pygame.K_DOWN, pygame.K_RETURN)                   # onto the sword, pick it up
assert 1001 in game.player.bag.values()
cell = next(c for c, v in game.player.bag.items() if v == 1001)
assert cell == (14, 8), cell                            # the Rogue's sling and pebbles fill the first two cells
from engine import rules  # noqa: E402
rules._seed[0] = 3                               # (closing the inventory takes a turn, in which the shopkeeper may wander: the same dice every time)
press(pygame.K_i, pygame.K_RIGHT, pygame.K_RIGHT, pygame.K_RETURN, pygame.K_ESCAPE)   # wear it
assert game.player.item((12, 4)) == 1001 and game.player.hero.power == 20, (game.player.item((12, 4)),
                                                                              game.player.hero.power)
game.player.inv.coins = 100
press(pygame.K_UP, pygame.K_UP, pygame.K_UP, pygame.K_UP)   # into the shopkeeper
assert type(game.overlay).__name__ == 'Page'
press(pygame.K_RETURN, pygame.K_ESCAPE)                 # buy the sword
assert game.player.inv.coins == 50 and list(game.player.bag.values()).count(1001) == 2
game.renderer.draw(game)
print('Deluxe on the blank pack: a new weapon picked up, worn (power 20) and bought for 50 gold')

game.quick_start(5, 1, (3, 7))                          # the new class, next to the new monster
h = game.player.hero
assert h.type == 5 and h.mlife == 99 and game.player.item((12, 4)) == 1001 and game.player.spells[1] == 1
exp = h.exper
for _ in range(20):                                     # hit it until it falls
    if not game.world.sq(3, 8).mon:
        break
    press(pygame.K_DOWN)
assert game.world.sq(3, 8).mon == 0 and game.world.sq(3, 8).item == 11 and game.world.sq(3, 8).deco == 0
assert h.exper == exp - 77
game.renderer.draw(game)
print('a new class (Tester) killed a new monster: 77 experience, its loot, and no body (corpse: none)')
print('all pack checks passed')
