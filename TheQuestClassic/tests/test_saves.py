"""The original's save system in play: newgame() takes a slot, the silent save after creation,
'Want to save?', 'Want to load?', the Available Games list, 'Want to quit?', and loading after
death. Saves go to a temporary folder. The file format itself is checked against the exe by
tools/re/verify_saves.py."""
import os
import sys
import tempfile

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame  # noqa: E402

pygame.init()
win = pygame.display.set_mode((640, 480))
from engine.game import Game  # noqa: E402
from engine.savefile import Slots  # noqa: E402
from engine import ui  # noqa: E402

tmp = tempfile.mkdtemp()


def key(g, k, n=1):
    for _ in range(n):
        g.handle(pygame.event.Event(pygame.KEYDOWN, key=k))


def game():
    g = Game(win)
    g.slots = Slots(tmp)
    return g


def new_game(g, cls_keys=0):
    """Title -> New Game -> story 0 -> choose a class -> skill -> fault -> story 1 -> level 1."""
    assert isinstance(g.overlay, ui.TitleScreen)
    key(g, pygame.K_RETURN)                   # New Game
    for _ in range(40):
        if isinstance(g.overlay, ui.TextScreen):
            key(g, pygame.K_RETURN)
        elif g.overlay is None:
            return
        else:
            before = g.overlay
            key(g, pygame.K_DOWN, cls_keys if type(before).__name__ == 'ClassSelect' else 0)
            key(g, pygame.K_RETURN)
            if g.overlay is before:              # a refused choice (a class's spared fault): move on
                key(g, pygame.K_DOWN)
    raise AssertionError(f'new game stuck at {g.overlay}')


# a new game takes slot 1 and saves itself once play starts
g = game()
new_game(g)
assert g.status.saveslot == 1 and g.world.level == 1, (g.status.saveslot, g.world.level)
assert g.slots.header(1) == (1, g.player.hero.type)
print('new game: slot', g.status.saveslot, 'class', g.player.hero.type, 'saved', g.slots.header(1))

# Want to save? (Y)es (N)o, then change things and Want to load? restores them
x0, coins0 = g.player.X, g.player.inv.coins
g.player.inv.coins = 777
key(g, pygame.K_v)
assert isinstance(g.overlay, ui.YesNo) and g.overlay.q == 'Want to save? (Y)es (N)o'
key(g, pygame.K_y)
g.player.inv.coins = 5
g.world.sq(g.player.X, g.player.Y).gold = 12
key(g, pygame.K_l)
assert g.overlay.q == 'Want to load? (Y)es (N)o'
key(g, pygame.K_n)
assert g.player.inv.coins == 5                     # No: nothing happens
key(g, pygame.K_l)
key(g, pygame.K_y)
assert g.player.inv.coins == 777 and g.player.X == x0, (g.player.inv.coins, g.player.X)
assert g.world.sq(g.player.X, g.player.Y).gold == 0
print('save / load: restored coins', g.player.inv.coins)

# a second game takes slot 2; the Available Games list shows both
g2 = game()
new_game(g2, cls_keys=1)
assert g2.status.saveslot == 2
g2.player.hero.level = 12
g2.save_game()
assert g2.slots.listing() == [(1, 1, g.player.hero.type), (2, 12, g2.player.hero.type)], g2.slots.listing()

# Want to quit? -> the title; Load Game -> pick game 1
key(g2, pygame.K_ESCAPE)
assert g2.overlay.q == 'Want to quit? (Y)es (N)o'
key(g2, pygame.K_y)
assert isinstance(g2.overlay, ui.TitleScreen)
key(g2, pygame.K_DOWN)
key(g2, pygame.K_RETURN)
assert isinstance(g2.overlay, ui.LoadScreen)
g2.renderer.draw(g2)
key(g2, pygame.K_DOWN)
key(g2, pygame.K_UP)
key(g2, pygame.K_RETURN)
assert g2.overlay is None and g2.status.saveslot == 1 and g2.player.inv.coins == 777
print('title -> Load Game -> game 1: coins', g2.player.inv.coins, 'level', g2.world.level)

# death: Want to load? Yes reloads the game's own save
g2.player.hero.life = -9
g2.end_turn()
assert g2.overlay.q == 'Want to load? (Y)es (N)o'
key(g2, pygame.K_y)
assert g2.player.hero.life > 0
print('death -> load: life', g2.player.hero.life)

# a reserved slot (a new game abandoned in the first story) is reused, and ends the list
g3 = game()
key(g3, pygame.K_RETURN)
key(g3, pygame.K_ESCAPE)
assert isinstance(g3.overlay, ui.TitleScreen)
assert open(g3.slots.path(3), 'rb').read() == b'-1' and len(g3.slots.listing()) == 2
assert g3.slots.new() == 3
print('reserved slot reused; all save checks passed')
