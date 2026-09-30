"""Runs every place the game plays one of the original's animations or sounds (engine/anim.py), in
the dummy video mode (animations run instantly but in full, including their rand() draws).
Each check prints a line; an exception fails the run. The drawing itself is checked against the exe
by tools/re/verify_anims.py."""
import os
import sys

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame  # noqa: E402

pygame.init()
win = pygame.display.set_mode((640, 480))
from engine.game import Game  # noqa: E402
from engine.state import KNIGHT, MAGE, ROGUE, SLOT_WEAPON, SLOT_OFFHAND  # noqa: E402
from engine import anim, ui  # noqa: E402

played = []
_orig = Game.play


def spy(self, name, *args, **kw):
    played.append(name)
    return _orig(self, name, *args, **kw)


Game.play = spy


def key(g, k, n=1):
    for _ in range(n):
        g.handle(pygame.event.Event(pygame.KEYDOWN, key=k))


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
    for x in range(2, 99):
        for y in range(2, 99):
            if pred(x, y, g.world.grid[x][y]):
                return x, y


def near_monster(g, t, dx):
    """A monster of type t with a free floor square dx to its left, on the same screen."""
    return find(g, lambda x, y, q: q.mon == t and (x - 1) // 10 == (x - 1 - dx) // 10
                and g.world.sq(x - dx, y).wall == 0 and g.world.sq(x - dx, y).mon == 0
                and g.world.sq(x - dx, y).item == 0)


def check(label):
    print(f'{label:34s} played {sorted(set(played))}')
    played.clear()


# every spell, cast at an imp or on the hero
g = new(MAGE)
x, y = near_monster(g, 1, 2)
warp(g, x - 2, y)
for s in range(1, 21):
    g.player.spells[s] = 1
g.player.hero.intl = g.player.hero.bintl = 99
free = next((fx, fy) for fx, fy in ((x - 1, y + 1), (x - 1, y - 1), (x - 2, y + 1), (x - 2, y - 1), (x - 1, y))
            if g.world.in_room(fx, fy) and g.world.sq(fx, fy).wall == 0 and g.world.sq(fx, fy).item == 0)
for s in range(1, 21):
    for e in list(g.world.enemies):                  # a fresh imp at (x, y), nobody else
        g.world.sq(e.x, e.y).mon = 0
    g.world.enemies.clear()
    g.spawn(1, x, y)
    rng = g.spells.tell(s, 3)
    warp(g, x - (1 if rng == 1 else 2), y)
    g.overlay = None
    g.player.hero.mana = g.player.hero.mmana = 200
    g.player.hero.life = g.player.hero.mlife
    g.player.hero.invisible = -1
    g.status.ems = 0
    g.begin_cast(s)
    if isinstance(g.overlay, ui.Cursor):
        tx, ty = free if s in (3, 8, 15, 18) else (x, y)
        if rng == 1 and (tx, ty) == free:
            tx, ty = x - 1, y + (1 if g.world.sq(x - 1, y + 1).wall == 0 else -1)
        assert g.magic.valid_target(s, tx, ty) and g.magic.in_range(s, tx, ty), s
        g.overlay.on_pick(tx, ty)
check('spells 1-20')

# melee, the enemies' turn, a kill (Knight vs orc)
g = new(KNIGHT)
x, y = near_monster(g, 2, 1)
warp(g, x - 1, y)
for _ in range(12):
    if not g.world.enemy_at(x, y):
        break
    key(g, pygame.K_RIGHT)
    g.player.hero.life = g.player.hero.mlife
check('melee until the orc dies')

# shields on the hero while enemies attack
g.status.Shield = 5
g.status.fShield = 5
g.spawn(2, g.player.X + 1, g.player.Y) if g.world.in_room(g.player.X + 1, g.player.Y) else None
key(g, pygame.K_UP)
key(g, pygame.K_DOWN)
check('shielded turns')

# every monster spell at the hero
for t in (5, 8, 11, 31, 33, 42, 43, 45, 38, 32, 44):
    g = new(KNIGHT)
    x, y = near_monster(g, 2, 2)
    warp(g, x - 2, y)
    e = g.world.enemy_at(x, y)
    e.type, e.att, e.range, e.atk, e.power = t, 9, 9, 0, 5
    g.player.hero.life = g.player.hero.mlife = 500
    g.combat.enemy_cast(e, 'x')
check('monster spells')

# ranged: a Rogue shoots until out of ammo
g = new(ROGUE)
x, y = near_monster(g, 2, 3)
warp(g, x - 3, y)
g.player.bag[SLOT_WEAPON], g.player.bag[SLOT_OFFHAND] = 230, 603
for _ in range(6):
    key(g, pygame.K_SPACE)
    g.player.hero.life = g.player.hero.mlife
check('shooting, then no ammo')

# potions, poison, dying, death and the answer No
g = new(KNIGHT)
g.player.inv.rose = g.player.inv.cyan = 1
g.player.hero.poisoned = 1
key(g, pygame.K_1)
key(g, pygame.K_7)
g.player.hero.life = 0
g.end_turn()
g.player.hero.life = -9
g.end_turn()
assert isinstance(g.overlay, ui.YesNo), g.overlay
key(g, pygame.K_n)
assert isinstance(g.overlay, ui.TitleScreen), g.overlay
check('potions, bleeding, death')

# level 5 teleporter pad, reputation, honour, leaving levels (with and without the jingle)
g = new(KNIGHT, 5)
pad = find(g, lambda x, y, q: q.item == 999)
g.world.leave_room()
g.player.X, g.player.Y = pad[0] - 1, pad[1]
g.world.enter_room(g.player, g.status)
before = g.player.X
g.try_move(1, 0)
print('   teleporter moved the hero', g.player.X - before, 'squares east')
g.change_rep(-1)
g.change_rep(1)
edge = find(g, lambda x, y, q: (x - 1) % 10 == 0 and x > 1 and q.wall == 0 and q.mon == 0 and q.item == 0
            and g.world.sq(x - 1, y).wall == 0 and g.world.sq(x - 1, y).mon == 0)
warp(g, *edge)
g.player.skill.hon, g.status.ems = 2, 1
assert not g.try_move(-1, 0) and g.player.X == edge[0]      # "It is not honorable to flee..."
g.next_level()
check('level 5: pad, reputation, leaving')
g = new(KNIGHT, 1)
g.next_level()
check('leaving level 1')

# level up and the key jingle
g = new(KNIGHT)
g.player.hero.exper = 0
g.end_turn()
g.overlay = None
g.world.sq(g.player.X, g.player.Y).item = 12
g.pick_up()
check('level up, key')

# script effects (level 6 flash, level 7 boss spells)
g = new(KNIGHT, 6)
for name, args in (('screen_flash', (2,)), ('ainvisibility', (10, 5)), ('ashield', (4, 4, 2)),
                   ('asskeleton', (1, 4, 3)), ('dcast2', (3, 3)), ('tones', ((100, 300),)), ('pause', (500,))):
    g.events.f_effect(name, *args)
g.events.f_poison()
check('script effects')

missing = [n for n in ('dcast2', 'ahit', 'bhit', 'aflame', 'athunder', 'ainferno', 'adeaths', 'adeteriorate',
                       'adrain', 'asskeleton', 'asscorpion', 'astoneknight', 'ateleport', 'aicering', 'aearthq',
                       'aheal', 'arestore', 'acure', 'ainvisibility', 'ashield', 'ablackward', 'adarkhour')
           if not hasattr(anim, n)]
assert not missing, missing
print('all animation paths ran')
