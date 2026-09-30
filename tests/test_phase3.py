import os, sys, random
os.environ['SDL_VIDEODRIVER'] = 'dummy'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
pygame.init()
win = pygame.display.set_mode((640, 480))
from quest2.game import Game
from quest2.state import MAGE, ROGUE, KNIGHT, SLOT_WEAPON, SLOT_OFFHAND
from quest2 import ui

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
os.makedirs(OUT, exist_ok=True)
random.seed(1)


def key(g, k, n=1):
    for _ in range(n):
        g.handle(pygame.event.Event(pygame.KEYDOWN, key=k))


def shot(g, name):
    g.renderer.draw(g)
    pygame.image.save(g.renderer.screen, os.path.join(OUT, name))


def new(cls, level=1):
    g = Game(win)
    g.overlay = None
    g.start_new(cls)
    g.overlay = None
    g.goto_level(level)
    return g


def warp(g, x, y):
    g.world.leave_room()
    g.player.X, g.player.Y = x, y
    g.world.enter_room(g.player, g.status)
    g.count_hostiles()


def find(g, pred):
    m = g.world.grid
    for x in range(2, 99):
        for y in range(2, 99):
            if pred(x, y, m[x][y]):
                return x, y


# 1. AI: monsters chase the hero
g = new(KNIGHT)
x, y = find(g, lambda x, y, q: q.mon == 2 and g.world.sq(x - 3, y).wall == 0 and g.world.sq(x - 3, y).mon == 0
            and (x - 4) % 10 not in (0,) and (x - 1) // 10 == (x - 4) // 10)
warp(g, x - 3, y)
e = g.world.enemy_at(x, y)
print('AI: orc at', (e.x, e.y), 'att', e.att, 'hero', (g.player.X, g.player.Y))
for i in range(4):
    key(g, pygame.K_UP) if i % 2 else key(g, pygame.K_DOWN)
    print('   turn', i, 'orc at', (e.x, e.y) if e in g.world.enemies else 'dead', 'life', g.player.hero.life, g.messages)

# 2. Mage casts flame on a monster
g = new(MAGE)
x, y = find(g, lambda x, y, q: q.mon == 1 and (x - 1) // 10 == (x - 3) // 10 and g.world.sq(x - 2, y).wall == 0
            and g.world.sq(x - 2, y).mon == 0)
warp(g, x - 2, y)
imp = g.world.enemy_at(x, y)
print('Mage mana', g.player.hero.mana, 'fkeys', g.player.fkey, 'imp life', imp.life)
key(g, pygame.K_s)
print('overlay', type(g.overlay).__name__)
key(g, pygame.K_DOWN)          # slot 1 = flame
key(g, pygame.K_F2)            # bind flame to F2
key(g, pygame.K_ESCAPE)
print('fkeys', g.player.fkey)
key(g, pygame.K_F2)
print('overlay', type(g.overlay).__name__, 'cursor', g.cursor)
key(g, pygame.K_RIGHT, 2)
shot(g, 't_cast.png')
key(g, pygame.K_RETURN)
print('after flame: mana', g.player.hero.mana, 'imp', imp.life if imp in g.world.enemies else 'dead', g.messages)

# 3. Rogue ranged
g = new(ROGUE)
key(g, pygame.K_i)                  # the cursor starts on the first backpack cell: the sling
key(g, pygame.K_RETURN)
key(g, pygame.K_RIGHT)              # the pebbles
key(g, pygame.K_RETURN)
print('rogue equip', g.player.bag, type(g.overlay).__name__)
shot(g, 't_inventory.png')
key(g, pygame.K_ESCAPE)
x, y = find(g, lambda x, y, q: q.mon == 2 and (x - 1) // 10 == (x - 5) // 10 and g.world.sq(x - 4, y).wall == 0
            and g.world.sq(x - 4, y).mon == 0)
warp(g, x - 4, y)
for i in range(6):
    key(g, pygame.K_SPACE)
    print('   shoot', g.messages, 'ammo', g.player.bag.get(SLOT_OFFHAND))

# 4. Shop on level 1
g = new(KNIGHT)
g.player.inv.coins = 500
x, y = find(g, lambda x, y, q: q.mon == -5)
nx = x - 1 if g.world.sq(x - 1, y).wall == 0 else x + 1
warp(g, nx, y)
key(g, pygame.K_RIGHT if nx < x else pygame.K_LEFT)
print('shop overlay', type(g.overlay).__name__)
key(g, pygame.K_RIGHT)
key(g, pygame.K_RETURN)
print('bought: coins', g.player.inv.coins, 'bag', g.player.bag, 'potions', g.player.inv)
shot(g, 't_shop.png')
key(g, pygame.K_ESCAPE)

# 5. Level up
g.player.hero.exper = 0
key(g, pygame.K_1)   # drink (no potion, no turn)
g.end_turn()
print('levelup overlay', type(g.overlay).__name__)
shot(g, 't_levelup.png')
key(g, pygame.K_RETURN)
print('level', g.player.hero.level, 'exp', g.player.hero.exper, 'str', g.player.hero.bstr, 'overlay', type(g.overlay).__name__)

# 6. save / load (the original's save file, in a temporary folder)
import tempfile
from quest2.savefile import Slots
g.overlay = None
g.slots = Slots(tempfile.mkdtemp())
g.status.saveslot = g.slots.new()
g.save_game()
x0 = g.player.X
g.player.X += 1
g.load_game()
key(g, pygame.K_y)
print('save/load pos restored', g.player.X == x0, 'slot', g.status.saveslot)
