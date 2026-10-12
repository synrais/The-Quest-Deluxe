"""The game's speed (1x, 2x, 4x, 8x): + and - change it, settings.ini sets where it starts, the animations and waits take that much less time,
and nothing else changes (the dice, the turns).

Run:  xvfb-run -a python tests/test_speed.py     (or SDL_VIDEODRIVER=dummy python tests/test_speed.py)
"""
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame                                                               # noqa: E402
pygame.init()
window = pygame.display.set_mode((640, 480))
from engine import settings, speed                                          # noqa: E402
from engine.game import Game                                                # noqa: E402

key = lambda k: pygame.event.Event(pygame.KEYDOWN, key=k, unicode='', mod=0)      # noqa: E731

# ── the steps and the clock ───────────────────────────────────────────────────
real_ticks = pygame.time.get_ticks
pygame.time.get_ticks = lambda: 12345
assert speed.get() == 1 and speed.ticks() == 12345, 'at 1x, never changed, the game clock is pygame\'s own (the tests that fake the time rely on it)'
pygame.time.get_ticks = real_ticks
assert speed.use(1) == 1
assert [speed.faster() for _ in range(5)] == [2, 4, 8, 8, 8]
assert [speed.slower() for _ in range(5)] == [4, 2, 1, 1, 1]
assert speed.use(3) in (2, 4) and speed.use('8') == 8 and speed.use('x') == 1 and speed.use(100) == 8 and speed.use(0) == 1
speed.use(1)
t0 = speed.ticks()
time.sleep(0.2)
t1 = speed.ticks()
assert 150 <= t1 - t0 <= 400, t1 - t0                                       # 1x: the clock is pygame's
speed.use(8)
time.sleep(0.2)
t2 = speed.ticks()
assert 1300 <= t2 - t1 <= 2400, t2 - t1                                     # 8x: it runs 8 times as fast
speed.use(1)                                                                # (and going back to 1x does not jump)
t3 = speed.ticks()
assert 0 <= t3 - t2 <= 50, t3 - t2
assert speed.real_ms(800) == 800
speed.use(8)
assert speed.real_ms(800) == 100 and speed.silent()
speed.use(2)
assert not speed.silent()
speed.use(1)

# ── settings.ini ──────────────────────────────────────────────────────────────
tmp = tempfile.mkdtemp()
for text, want in (('', '1'), ('[play]\nspeed = 4\n', '4'), ('[play]\nspeed = 8 ; the fastest\n', '8'), ('[play]\nspeed = 3\n', '1'),
                   ('[play]\nspeed = fast\n', '1')):
    path = os.path.join(tmp, 'settings.ini')
    with open(path, 'w') as fh:
        fh.write(text)
    got = settings.load(path)['speed']
    assert got == want, (text, got)
shipped = settings.load()['speed']
assert shipped == '1', 'the shipped settings.ini plays at the original\'s pace'

# ── the keys ──────────────────────────────────────────────────────────────────
g = Game(window, settings={'fixes': 'off', 'sound': 'off'})
assert speed.get() == 1
g.overlay = None
g.goto_level(1)
before = (g.player.X, g.player.Y, g.world.level, len(g.world.enemies))
for k, want in ((pygame.K_EQUALS, 2), (pygame.K_PLUS, 4), (pygame.K_KP_PLUS, 8), (pygame.K_EQUALS, 8), (pygame.K_MINUS, 4),
                (pygame.K_KP_MINUS, 2), (pygame.K_MINUS, 1), (pygame.K_MINUS, 1)):
    g.handle(key(k))
    assert speed.get() == want, (k, speed.get(), want)
    assert g.messages and g.messages[-1].startswith(f'Speed {want}x'), g.messages
assert before == (g.player.X, g.player.Y, g.world.level, len(g.world.enemies)), 'the speed keys are not a turn'

speed.use(1)
g2 = Game(window, settings={'fixes': 'off', 'sound': 'off', 'speed': '4'})
assert speed.get() == 4, 'a game starts at the speed settings.ini asks'
g3 = Game(window)
assert speed.get() == 1, 'a game made without settings (the tests) plays at 1x'

# ── an animation takes that much less time ───────────────────────────────────
g = Game(window, settings={'fixes': 'off', 'sound': 'off'})
g.overlay = None
g.goto_level(1)
g.fast = False                                                              # (the dummy driver plays animations instantly: this one is timed)


def pause(ms=100, n=6):
    for _ in range(n):
        yield ms


took = {}
for n in (1, 2, 4, 8):
    speed.use(n)
    start = time.time()
    g.renderer.play(g, pause(), fast=False)
    took[n] = time.time() - start
speed.use(1)
assert 0.55 <= took[1] <= 1.6, took                                         # 6 x 100 ms
assert took[2] < took[1] * 0.7 and took[4] < took[2] * 0.7 and took[8] < took[4] * 0.8, took
assert took[8] < 0.3, took
start = time.time()
g.renderer.wait(pygame.Surface((640, 480)), 400)
slow = time.time() - start
speed.use(8)
start = time.time()
g.renderer.wait(pygame.Surface((640, 480)), 400)
quick = time.time() - start
speed.use(1)
assert slow >= 0.35 and quick < 0.15, (slow, quick)

# ── the same game at every speed ──────────────────────────────────────────────
import random                                                               # noqa: E402
from engine import rules                                                    # noqa: E402


def play(n):
    speed.use(n)
    g = Game(window, settings={'fixes': 'off', 'sound': 'off', 'speed': str(n)})
    g.overlay = None
    g.fast = True
    g.goto_level(1)
    rules.srand(7)                                                          # (the game's own rand())
    rng = random.Random(3)
    for _ in range(80):
        g.handle(key(rng.choice([pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN, pygame.K_SPACE])))
    return (g.player.X, g.player.Y, g.player.hero.life, g.status.__dict__.copy(), [(e.x, e.y, e.life) for e in g.world.enemies], rules.rand())


a, b = play(1), play(8)
speed.use(1)
assert a == b, 'the same keys give the same game at 1x and 8x'
print('speed: + and - (1x 2x 4x 8x), settings.ini, animations and waits take 1/n of the time, the game itself is the same: ok')
