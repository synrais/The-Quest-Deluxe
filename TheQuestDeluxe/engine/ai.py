"""Monster movement: port of monsmove() (RPG.CPP 0a45:a480).

Each turn, for every creature on the screen:
  1. frozen creatures thaw one step
  2. melee creatures fight adjacent enemies of theirs (monsters vs NPCs / summons)
  3. hostile creatures that can see the hero chase him, larger axis first, opening doors
  4. otherwise some wander at random (neutral animals, blinded monsters, casters, archers)
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .rules import random, spread
from .state import Enemy

if TYPE_CHECKING:
    from .game import Game


def monster_vs_monster(att: Enemy, dfn: Enemy, pack) -> int:
    """monshitmons(): same formula as the hero's melee, magic armour vs wraiths/oculi."""
    if dfn.att < -10:
        dfn.att = 9
    if random(100) + 1 > att.atk - dfn.defense:
        return 0
    power = spread(att.power)
    power -= dfn.marm if pack.trait(att.type, 'magic_attack') else dfn.warm
    return power


def wants_to_fight(e: Enemy, o: Enemy, g: 'Game') -> bool:
    t, trait = e.type, g.pack.trait
    if e.range == 1 and not trait(t, 'explodes') and e.att != -4 and o.type < 0:
        if t > 0 and not trait(t, 'animal'):
            return True                         # monsters attack NPCs and summons
        if t < -99 and o.att > -1:
            return True                         # summons attack hostile NPCs
        if o.type < -99 and e.att > -1:
            return True                         # hostile NPCs attack summons
    if o.type > 0 and (o.att > -1 or o.att < -3) and t < 0:
        # NPCs and summons attack hostile monsters (except on the level's peaceful screens)
        if t >= -99 and ((g.player.X - 1) // 10 + 1, (g.player.Y - 1) // 10 + 1) in \
                g.events.meta(g.world.level, 'PEACEFUL_SCREENS', ()):
            return False
        return True
    return False


def monsmove(g: 'Game') -> None:
    w, p, h = g.world, g.player, g.player.hero
    ox, oy = w.origin
    x0, x1, y0, y1 = ox, ox + 9, oy, oy + 9

    mover = [None]                                  # the creature being moved (a big one needs room for all of it)

    def free(x, y):
        e = mover[0]
        n = w.size_of(e.type) if e else 1
        own = set(w.cells(e)) if n > 1 else ()
        for cx, cy in w.footprint(x, y, n):
            if not (x0 <= cx <= x1 and y0 <= cy <= y1):
                return False
            q = w.sq(cx, cy)
            if not (q.wall == 0 and g.pack.item_type(q.item) not in ('teleporter', 'exit')
                    and (q.mon == 0 or (cx, cy) in own) and (cx, cy) != (p.X, p.Y)):
                return False
        return True

    def step(e, nx, ny):
        cells = w.cells(e)
        for cx, cy in cells:
            w.sq(cx, cy).mon = 0
        e.x, e.y = nx, ny
        for cx, cy in w.cells(e):
            w.sq(cx, cy).mon = e.type

    for e in list(w.enemies):
        if e not in w.enemies or e.life <= 0:
            continue
        mover[0] = e
        if e.att < -10:
            e.att += 1
        if e.att == -10:
            e.att = 9
        ranok = False
        if not e.moved and e.range > 1 and e.atk != 0:
            ranok = True
            e.moved = True

        tx, ty = p.X, p.Y
        fought = False
        if not e.moved or ranok:
            # ── fight a neighbouring creature ───────────────────────────────
            for o in list(w.enemies):
                if o is e or o.life <= 0 or not wants_to_fight(e, o, g):
                    continue
                ddx, ddy = (w.gap(e, o.x, o.y) if w.size_of(e.type) > 1 else
                            w.gap(o, e.x, e.y) if w.size_of(o.type) > 1 else (abs(e.x - o.x), abs(e.y - o.y)))
                if not ((ddx == 1 and ddy == 0) or (ddy == 1 and ddx == 0)) or g.pack.trait(o.type, 'invisible'):
                    continue
                g.combat.reveal(e)
                dmg = monster_vs_monster(e, o, g.pack)
                mw = 1 if e.x > o.x else 3 if e.x < o.x else 4 if o.y > e.y else 2
                if dmg > 0:
                    g.play_at('ahit', o.x, o.y, g.fps_creature_side(mw) if g.renderer.in_3d(g) else mw, 1)
                    o.life -= dmg
                    g.report(f'The {g.monster_name(e.type)} hits the {g.monster_name(o.type)} for {dmg}.', 11,
                             (o.x, o.y), dmg)
                    g.combat.check_dead(e)
                else:
                    g.play_at('bhit', o.x, o.y, g.fps_creature_side(mw) if g.renderer.in_3d(g) else mw)
                    g.report(f'The {g.monster_name(e.type)} misses the {g.monster_name(o.type)}.', 7, (o.x, o.y), 'miss')
                e.moved = True
                fought = not ranok
                break
            if fought:
                continue                                  # attacked this turn: no chase, no wandering
            if not ranok:
                # ── chase ───────────────────────────────────────────────────
                if e.type < -99 and e.att == -3:          # summons hunt the nearest hostile
                    best, bestd = None, 20
                    for o in w.enemies:
                        if o is e or g.pack.trait(o.type, 'invisible'):
                            continue
                        d = abs(o.x - e.x) + abs(o.y - e.y)
                        if d < bestd and (o.att > -1 or o.att in (-4, -5) or o.att < -10):
                            best, bestd = o, d
                    if best:
                        tx, ty = best.x, best.y
                chase(g, e, tx, ty, x0, x1, y0, y1, free, step)

        # ── wander ──────────────────────────────────────────────────────────
        if e not in w.enemies:
            continue
        wander = False
        if ranok and e.range > 1 and e.atk != 0 and e.att > -10:
            wander = True
        elif e.att == -1:
            wander = True
        elif not e.moved and h.invisible != -1 and e.att not in (8, -2, -3) and e.att > -10:
            wander = True
        elif e.att == -5:
            wander = True
        elif e.att == -4 and (not e.moved or ranok):
            wander = True
        if not wander:
            continue
        ran = random(16)
        if e.att == -4:
            ran = random(4)
        if e.att == 9 and e.range == 9:
            ran = random(6)
        for want, dx, dy, edge in ((0, -1, 0, e.x == x0), (1, 0, -1, e.y == y0), (2, 1, 0, e.x == x1),
                                   (3, 0, 1, e.y == y1)):
            if ran == want and not edge:
                nx, ny = e.x + dx, e.y + dy
                if free(nx, ny) and (nx, ny) != (tx, ty):
                    step(e, nx, ny)
                break


def chase(g, e, tx, ty, x0, x1, y0, y1, free, step):
    h = g.player.hero
    x, y = e.x, e.y
    n = g.world.size_of(e.type)
    if n > 1:                                         # a big creature's top left aims short, so it all arrives
        tx, ty = tx - (n - 1) if tx > x else tx, ty - (n - 1) if ty > y else ty
    dx, dy = abs(x - tx), abs(y - ty)
    wflag = random(2) + 1 if dx == dy else 0
    saved = e.att
    if e.att > 0:
        e.att = e.att + e.range - 1
    sees = e.att >= dx and e.att >= dy and (h.invisible == -1 or e.att == 8)
    if not (sees or e.att == -3):
        e.att = saved
        return
    blocked, spins = 0, 0
    w = g.world

    def attempt(nx, ny):
        nonlocal blocked
        if free(nx, ny):
            step(e, nx, ny)
            blocked = 2
            return
        blocked = 1
        if g.pack.wall(w.sq(nx, ny).wall).get('door') == 'plain':     # monsters open plain doors
            q = w.sq(nx, ny)
            q.wall, q.deco = 0, g.pack.deco('open_door')
            blocked = 2

    while True:
        if blocked != 2 and (dx > dy or blocked == 1 or wflag == 1):
            if (x > tx or (x == tx and spins == 1)) and x != x0:
                attempt(x - 1, y)
            if blocked != 2 and (x < tx or (x == tx and spins == 1)) and x != x1:
                attempt(x + 1, y)
            if blocked != 2:
                wflag = 2
        if blocked != 2 and (dx < dy or blocked == 1 or wflag == 2):
            if (y > ty or (y == ty and spins == 1)) and y != y0:
                attempt(x, y - 1)
            if blocked != 2 and (y < ty or (y == ty and spins == 1)) and y != y1:
                attempt(x, y + 1)
        spins += 1
        if blocked != 2:
            wflag = 1
        e.att = saved
        if blocked == 2 or spins != 1:
            return
