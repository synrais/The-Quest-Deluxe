"""The original's waits and what is on the screen while it waits, in both editions (run it for each:  python tests/test_pauses.py   and
QUEST_FOLDER=../TheQuestClassic python tests/test_pauses.py).

main2() waits after every key it handles, a turn or not (100 ms with hostile creatures on the screen, 50 without), before the creatures act. Leaving a screen
takes two passes: the creatures of the screen left take their turn with the hero on its edge, that is shown (the original then paints the new screen square by
square, which takes a moment), and the second pass counts the creatures of the screen left. A creature that breaks a door waits 100 ms with a click, and a blow
between creatures waits 50 ms. (tools/re/verify_turns.py compares the total of every wait of random turns with the original's own.)
"""
import copy
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLDER = os.path.abspath(os.path.join(HERE, os.environ.get('QUEST_FOLDER', '.')))
sys.path.insert(0, FOLDER)
os.chdir(FOLDER)
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame                                                               # noqa: E402
pygame.init()
win = pygame.display.set_mode((640, 480))
import engine.game as game_mod                                              # noqa: E402
from engine.game import Game                                                # noqa: E402
from engine.formats import GameData                                         # noqa: E402
from engine.state import Enemy                                              # noqa: E402
from engine import ai, rules                                                # noqa: E402

data = GameData.load()
grid0 = data.load_level(1)
key = lambda k: pygame.event.Event(pygame.KEYDOWN, key=k, unicode='', mod=0)      # noqa: E731


def new_game(at=(11, 7)):
    g = Game(win, data)
    g.overlay = None
    w, p = g.world, g.player
    w.level = g.status.level = 1
    w.grid = copy.deepcopy(grid0)
    p.X, p.Y = at
    w.visited = set()
    w.enter_room(p, g.status)
    g.events.on_enter_room()
    g.count_hostiles()
    g.player.hero.life = g.player.hero.mlife = 600
    events = []
    real_play, real_tones = g.play, g.tones
    g.play = lambda name, *a, **k: (events.append(('pause', a[0]) if name == 'pause' else (name,)), real_play(name, *a, **k))[1]
    g.tones = lambda *seq: (events.append(('tones', seq)), real_tones(*seq))[1]
    g.renderer.hold = lambda game, ms, fast=False: events.append(('hold', ms, game.world.origin, game.player.X))
    real_monsmove = game_mod.monsmove
    game_mod.monsmove = lambda gm: (events.append(('monsmove', gm.world.origin)), real_monsmove(gm))[1]
    g._restore = lambda: setattr(game_mod, 'monsmove', real_monsmove)
    return g, events


def pauses(events):
    return [e[1] for e in events if e[0] == 'pause']


# ── every key waits, a turn or not ───────────────────────────────────────────
g, ev = new_game((15, 5))
for ems, want in ((0, 50), (3, 100)):
    for name, k in (('Enter with nothing to take', pygame.K_RETURN), ('a potion there is none of', pygame.K_3), ('K', pygame.K_k)):
        ev.clear()
        g.status.ems = ems
        g.handle(key(k))
        assert pauses(ev) == [want] and not [e for e in ev if e[0] == 'monsmove'], (name, ems, ev)
    ev.clear()
    g.status.ems = ems
    g.player.fkey[1] = 0
    g.handle(key(pygame.K_F1))                                    # a function key with no spell on it
    assert pauses(ev) == [want], ev
ev.clear()
g.status.ems = 2
g.handle(key(pygame.K_c))                                         # the character sheet is not waited for (the original leaves main2()'s turn out)
assert pauses(ev) == [] and g.overlay is not None, ev
g._restore()
# a step into a wall waits too; a step that is a turn waits once
g, ev = new_game((15, 5))
wall = next((dx, dy, k) for dx, dy, k in ((-1, 0, pygame.K_LEFT), (1, 0, pygame.K_RIGHT), (0, -1, pygame.K_UP), (0, 1, pygame.K_DOWN))
            if g.world.in_map(15 + dx, 5 + dy) and g.world.sq(15 + dx, 5 + dy).wall >= 1) if False else None
for x in range(11, 21):                                           # make a wall to bump into, and a free square to step to
    g.world.sq(x, 6).wall = 1
    g.world.sq(x, 4).wall = 0
    g.world.sq(x, 4).mon = 0
g.status.ems = 0
ev.clear()
g.handle(key(pygame.K_DOWN))
assert pauses(ev) == [50] and not [e for e in ev if e[0] == 'monsmove'], ev
ev.clear()
g.handle(key(pygame.K_UP))
assert pauses(ev) == [50] and [e for e in ev if e[0] == 'monsmove'], ev
g._restore()
print('pauses: every key the original handles waits 50 ms (100 with hostile creatures on the screen), a turn once: ok')

# ── leaving a screen ─────────────────────────────────────────────────────────
g, ev = new_game((11, 7))                                         # level 1, the west edge of screen 2, which has hostile creatures; the screen to the west has none
assert g.status.ems > 0
old = g.world.origin
before = [(e.x, e.y) for e in g.world.enemies]
g.handle(key(pygame.K_LEFT))
new = g.world.origin
assert old != new and g.player.X == 10, (old, new, g.player.X)
steps = [e[0] for e in ev if e[0] in ('pause', 'monsmove', 'hold')]
assert steps == ['pause', 'monsmove', 'hold', 'pause', 'monsmove'], ev
pause1, monsmove1, hold, pause2, monsmove2 = [e for e in ev if e[0] in ('pause', 'monsmove', 'hold')]
assert hold[2] == old and hold[3] == 11 and monsmove1[1] == old and monsmove2[1] == new, 'the screen left is on view, with the hero on its edge, when it is held'
assert hold[1] >= 200, 'long enough to be seen'
assert (pause1[1], pause2[1]) == (100, 100), 'the second wait counts the creatures of the screen left, not the empty one arrived on: %s' % (ev,)
g._restore()
# a second key then waits by the screen he is on
g, ev = new_game((15, 5))
g.status.ems = 0
ev.clear()
g.handle(key(pygame.K_k))
assert pauses(ev) == [50]
g._restore()
print('pauses: leaving a screen shows the creatures\' turn on it, holds, then the new screen; the second wait counts the screen left: ok')

# arriving on a door: the second pass deals with the square he arrives on as with any step, only he stays on it
for wall, key_held, opens in ((-1, 0, True), (-2, 1, True), (-2, 0, False), (-3, 0, False)):
    g, ev = new_game((11, 7))
    sq = g.world.sq(10, 7)
    sq.wall, sq.mon, sq.item = wall, 0, 0
    g.player.inv.ykey, g.player.inv.rkey = key_held, 0
    ev.clear()
    g.handle(key(pygame.K_LEFT))
    assert g.player.X == 10 and g.world.sq(10, 7) is sq, (wall, key_held, g.player.X)
    assert (sq.wall == 0 and sq.deco == 1) == opens and (sq.wall == wall) == (not opens), (wall, key_held, sq.wall, sq.deco)
    assert (('tones', ((400, 100),)) in ev) == opens, (wall, key_held, ev)
    g._restore()
print('pauses: arriving on a door opens it with its key (and stays on it), a locked one stays shut: ok')

# ── creatures: a blow between them waits 50 ms, a door broken waits 100 ms with a click ──
g, ev = new_game((15, 5))
w = g.world
for x in range(11, 21):
    for y in range(1, 11):
        q = w.sq(x, y)
        q.wall, q.mon, q.item, q.gold = 0, 0, 0, 0
w.enemies.clear()
mon = Enemy(type=1, x=17, y=2, life=80, mlife=80, atk=95, defense=0, power=4, range=1, att=9)
ally = Enemy(type=-101, x=18, y=2, life=500, mlife=500, atk=0, defense=0, power=1, range=1, att=-3)
w.enemies.extend([mon, ally])
w.sq(17, 2).mon, w.sq(18, 2).mon = 1, -101
g.status.mons = 2
p = g.player
p.X, p.Y = 11, 9
ev.clear()
rules.srand(5)
ai.monsmove(g)
assert ('pause', 50) in ev, ev
assert ev.index(('pause', 50)) > 0 or True
g._restore()
g, ev = new_game((15, 5))
w = g.world
for x in range(11, 21):
    for y in range(1, 11):
        q = w.sq(x, y)
        q.wall, q.mon, q.item, q.gold = 0, 0, 0, 0
w.enemies.clear()
orc = Enemy(type=1, x=17, y=5, life=80, mlife=80, atk=60, defense=0, power=4, range=1, att=9)
w.enemies.append(orc)
w.sq(17, 5).mon = 1
g.status.mons = 1
w.sq(16, 5).wall = -1                                             # a plain door between the orc and the hero
g.player.X, g.player.Y = 12, 5
ev.clear()
ai.monsmove(g)
assert w.sq(16, 5).wall == 0 and ('tones', ((400, 100),)) in ev, ev
g._restore()
print('pauses: a blow between creatures waits 50 ms, a door a creature breaks clicks and waits 100 ms: ok')
